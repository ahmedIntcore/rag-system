# =============================================================
# main.py — FastAPI Web Application
#
# PURPOSE:
#   This file creates a REST API using FastAPI.
#   Instead of a terminal chat, users can now send HTTP requests
#   (from a browser, mobile app, Postman, or any frontend).
#
# WHAT IS FastAPI?
#   FastAPI is a modern Python web framework for building APIs.
#   Key features:
#   - Fast to write (less code than Flask/Django)
#   - Automatic docs at /docs (Swagger UI) — try it!
#   - Automatic validation (it checks request data for you)
#   - Type hints drive everything — Python types = API schema
#
# WHAT IS A REST API?
#   A REST API is a way for programs to talk to each other over HTTP.
#   Just like a browser visits URLs to get web pages,
#   your app calls URLs (endpoints) to get/send data.
#
#   Example HTTP request:
#     POST /ask
#     Body: {"question": "What products are available?"}
#
#   Example HTTP response:
#     {"answer": "The available products are...", "sources": [...]}
#
# HOW TO RUN:
#   uvicorn main:app --reload
#
#   --reload: restarts server when you change code (great for development)
#
# HOW TO TEST:
#   Open your browser at: http://localhost:8000/docs
#   FastAPI creates interactive documentation automatically!
# =============================================================

import logging
import os
from contextlib import asynccontextmanager  # For startup/shutdown events

# --- FastAPI imports ---
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# --- Pydantic: data validation (built into FastAPI) ---
# Pydantic models define the shape of request/response data
# FastAPI uses them to validate input and generate API docs automatically
from pydantic import BaseModel, Field

# --- Our modules ---
from src.rag_pipeline import RAGPipeline
from dotenv import load_dotenv

load_dotenv()

# =============================================================
# LOGGING SETUP
# =============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# =============================================================
# GLOBAL STATE
# =============================================================
# We store the RAG pipeline as a global variable so all requests
# share the same loaded model and index (expensive to reload each time).
#
# WHAT IS A GLOBAL VARIABLE?
#   A variable defined at the top level of a module, accessible
#   from any function. Use sparingly — here it makes sense because
#   the pipeline is expensive to initialize and must be shared.

rag_pipeline: RAGPipeline | None = None


# =============================================================
# LIFESPAN — Startup & Shutdown
# =============================================================
# The lifespan context manager runs code when the server starts
# and when it shuts down. We use it to initialize the RAG pipeline
# ONCE when the server starts, instead of on every request.
#
# WHAT IS @asynccontextmanager?
#   It creates an async context manager — code that runs at the
#   start of a block (startup) and at the end (shutdown).
#   The `yield` keyword separates startup code from shutdown code.

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs at server startup (before yield) and shutdown (after yield).
    """
    # --- STARTUP ---
    global rag_pipeline
    logger.info("Server starting up — initializing RAG pipeline...")

    rag_pipeline = RAGPipeline()

    # Load the index from disk if available, otherwise build from Sheets
    chunk_count = rag_pipeline.index_spreadsheet()
    logger.info(f"Startup complete! Index has {chunk_count} chunks.")

    yield  # Server runs here — handling requests

    # --- SHUTDOWN ---
    logger.info("Server shutting down...")


# =============================================================
# CREATE THE FASTAPI APP
# =============================================================
app = FastAPI(
    title="RAG System — Google Sheets Q&A",
    description=(
        "A Retrieval-Augmented Generation (RAG) API that answers questions "
        "based on data from a Google Sheets spreadsheet, powered by Claude AI.\n\n"
        "## How it works\n"
        "1. Data from your Google Sheet is loaded and indexed at startup\n"
        "2. When you ask a question, the system finds the most relevant rows\n"
        "3. Claude AI generates an answer using those rows as context\n\n"
        "## Quick Start\n"
        "Call `POST /ask` with your question to get started!"
    ),
    version="1.0.0",
    lifespan=lifespan,   # Register our startup/shutdown handler
)

# --- CORS Middleware ---
# CORS (Cross-Origin Resource Sharing) controls which websites can
# call this API. Setting allow_origins=["*"] means any website can
# call it — fine for development, restrict in production.
#
# WHY IS CORS NEEDED?
#   Browsers block JavaScript from calling APIs on different domains
#   for security. CORS headers tell the browser "it's okay, allow it."
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Allow all origins (change in production)
    allow_methods=["*"],       # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],       # Allow all headers
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": str(exc)})


# =============================================================
# PYDANTIC MODELS — Request & Response Schemas
# =============================================================
# These classes define the JSON structure of our API.
# FastAPI uses them to:
#   1. Validate incoming request data
#   2. Serialize (convert) response data to JSON
#   3. Generate the interactive /docs documentation
#
# WHAT IS BaseModel?
#   A Pydantic base class. Any class inheriting from it gets
#   automatic validation, JSON parsing, and serialization.
#
# WHAT IS Field()?
#   Adds metadata to a field: description, example, constraints.
#   This metadata shows up in the /docs UI.

class AskRequest(BaseModel):
    """Schema for the POST /ask request body."""
    question: str = Field(
        ...,  # ... means this field is REQUIRED (no default)
        description="The question to ask about the spreadsheet data",
        examples=["What products are available?"],
        min_length=1,
        max_length=2000,
    )
    remember_history: bool = Field(
        default=True,
        description="If True, Claude remembers previous questions in this session",
    )
    show_sources: bool = Field(
        default=True,
        description="If True, include the retrieved source chunks in the response",
    )


class SourceChunk(BaseModel):
    """Schema for a single retrieved source chunk."""
    text: str = Field(description="The text content of this chunk")
    score: float = Field(description="Similarity score from 0.0 to 1.0 (higher = more relevant)")
    metadata: dict = Field(description="Original row data from the spreadsheet")


class AskResponse(BaseModel):
    """Schema for the POST /ask response."""
    question: str = Field(description="The original question asked")
    answer: str = Field(description="Claude's answer based on the spreadsheet data")
    sources: list[SourceChunk] = Field(
        default=[],
        description="The spreadsheet chunks used as context to generate the answer",
    )


class IndexRequest(BaseModel):
    """Schema for the POST /index request body."""
    sheet_name: str | None = Field(
        default=None,
        description="Worksheet tab name to index. Leave empty to use the first sheet.",
        examples=["Sheet1", "Products", "FAQ"],
    )
    force_reindex: bool = Field(
        default=True,
        description="If True, always rebuild from scratch. If False, load saved index if available.",
    )


class IndexResponse(BaseModel):
    """Schema for the POST /index response."""
    message: str
    chunk_count: int = Field(description="Total number of text chunks now in the index")


class HealthResponse(BaseModel):
    """Schema for the GET /health response."""
    status: str
    index_size: int = Field(description="Number of chunks in the vector store")
    model: str = Field(description="Embedding model being used")


class SheetsResponse(BaseModel):
    """Schema for the GET /sheets response."""
    sheet_names: list[str] = Field(description="Names of all worksheet tabs")


class DriveFile(BaseModel):
    id: str
    name: str
    mimeType: str
    modifiedTime: str = ""


class DriveFilesResponse(BaseModel):
    files: list[DriveFile]


class MessageResponse(BaseModel):
    """Generic response with just a message."""
    message: str


# =============================================================
# HELPER — Get Pipeline or Raise Error
# =============================================================

def get_pipeline() -> RAGPipeline:
    """
    Returns the global RAG pipeline, or raises HTTP 503 if not ready.

    HTTP STATUS CODES (the numbers in HTTP responses):
        200 — OK (success)
        400 — Bad Request (client sent invalid data)
        404 — Not Found
        500 — Internal Server Error (bug in our code)
        503 — Service Unavailable (server not ready yet)

    HTTPException is FastAPI's way to return error responses.
    Raising it immediately stops the current function and sends
    the error response to the client.
    """
    if rag_pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="RAG pipeline is not initialized yet. Please wait and retry."
        )
    return rag_pipeline


# =============================================================
# API ENDPOINTS
# =============================================================
# Each endpoint is a Python function decorated with a route decorator.
# The decorator (@app.get, @app.post, etc.) tells FastAPI:
#   - Which HTTP method (GET, POST, DELETE...)
#   - Which URL path ("/ask", "/health"...)
#
# WHAT IS async def?
#   async functions can be paused while waiting for slow operations
#   (like network requests) and let other requests run in the meantime.
#   This makes the server handle more requests simultaneously.
#   Always use async def for FastAPI endpoints.

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Check server health",
    tags=["System"],
)
async def health_check():
    """
    Check if the server and RAG pipeline are ready.

    Returns the current status, index size, and embedding model name.
    Use this to verify the server started correctly before sending questions.
    """
    pipeline = get_pipeline()
    return HealthResponse(
        status="ok",
        index_size=pipeline.vector_store.size,
        model=pipeline.vector_store.embedding_model.model_name,
    )


@app.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask a question about the spreadsheet data",
    tags=["RAG"],
)
async def ask_question(request: AskRequest):
    """
    Ask a question and get an AI-generated answer based on the spreadsheet.

    **How it works:**
    1. Your question is converted to an embedding vector
    2. The most similar chunks from the spreadsheet are retrieved
    3. Those chunks are sent to Claude as context
    4. Claude generates an answer grounded in your data

    **Conversation history:**
    Set `remember_history=true` to have multi-turn conversations
    where Claude remembers previous questions.
    """
    pipeline = get_pipeline()

    # Call the RAG pipeline — this does all the work
    result = pipeline.ask(
        question=request.question,
        remember_history=request.remember_history,
        show_sources=request.show_sources,
    )

    # Convert source dicts to SourceChunk objects for proper serialization
    sources = [
        SourceChunk(
            text=s["text"],
            score=s["score"],
            metadata=s["metadata"],
        )
        for s in result["sources"]
    ]

    return AskResponse(
        question=result["question"],
        answer=result["answer"],
        sources=sources,
    )


@app.post(
    "/index",
    response_model=IndexResponse,
    summary="Reload and reindex data from Google Sheets",
    tags=["Data"],
)
async def reindex(request: IndexRequest, background_tasks: BackgroundTasks):
    """
    Trigger a reindex of the Google Sheets data.

    Call this endpoint after updating your spreadsheet to make the
    new data available for questions.

    **Note:** Indexing runs in the background. The response returns
    immediately with the previous chunk count. Use `GET /health`
    to check the updated count after indexing completes.
    """
    pipeline = get_pipeline()

    # BACKGROUND TASKS:
    # For slow operations (like indexing), we use BackgroundTasks.
    # This lets FastAPI return a response immediately while the
    # indexing continues running in the background.
    #
    # The client gets a fast response and can poll /health to see
    # when the new index is ready.
    def run_index():
        pipeline.index_spreadsheet(
            sheet_name=request.sheet_name,
            force_reindex=request.force_reindex,
        )

    background_tasks.add_task(run_index)

    return IndexResponse(
        message=(
            f"Indexing started in background"
            + (f" for sheet '{request.sheet_name}'" if request.sheet_name else " for first sheet")
            + ". Use GET /health to check progress."
        ),
        chunk_count=pipeline.vector_store.size,  # Current count (before reindex finishes)
    )


@app.get(
    "/sheets",
    response_model=SheetsResponse,
    summary="List available worksheet tabs",
    tags=["Data"],
)
async def list_sheets():
    """
    Get the names of all worksheet tabs in the connected Google Spreadsheet.

    Use this to discover available sheets before calling `/index` with a specific sheet name.
    """
    pipeline = get_pipeline()
    names = pipeline.sheets.get_sheet_names()
    return SheetsResponse(sheet_names=names)


@app.delete(
    "/history",
    response_model=MessageResponse,
    summary="Clear conversation history",
    tags=["RAG"],
)
async def clear_history():
    """
    Clear the conversation history to start a fresh session.

    Use this when the topic changes or you want Claude to stop
    referencing previous questions in the same session.
    """
    pipeline = get_pipeline()
    pipeline.clear_history()
    return MessageResponse(message="Conversation history cleared.")


@app.get(
    "/drive/files",
    response_model=DriveFilesResponse,
    summary="List PDFs and Docs in Google Drive",
    tags=["Data"],
)
async def list_drive_files():
    """List all PDFs and Google Docs the service account can access in Drive."""
    pipeline = get_pipeline()
    files = pipeline.drive.list_files()
    return DriveFilesResponse(files=[DriveFile(**f) for f in files])


@app.get(
    "/",
    summary="Chat UI",
    tags=["System"],
    include_in_schema=False,
)
async def root():
    """Serve the chat frontend."""
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
