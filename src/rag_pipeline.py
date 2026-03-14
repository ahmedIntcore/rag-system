# =============================================================
# src/rag_pipeline.py
#
# PURPOSE:
#   This is the main brain of the system. It combines:
#   1. Google Sheets (the knowledge source)
#   2. Vector Store (the search engine)
#   3. Claude AI (the answer generator)
#
#   Together they form a RAG (Retrieval-Augmented Generation) system.
#
# WHAT IS RAG? — A Simple Explanation:
#
#   Imagine you have a huge spreadsheet with company information,
#   product data, or FAQs. A user asks: "What is the return policy?"
#
#   WITHOUT RAG:
#     You send the ENTIRE spreadsheet to Claude + the question.
#     Problem: Spreadsheets can be huge — too many tokens, too slow, too expensive.
#
#   WITH RAG:
#     Step 1 (RETRIEVAL): Search the spreadsheet for chunks most
#                         similar to "return policy" → find 3-5 relevant rows
#     Step 2 (AUGMENTED): Add those 3-5 rows as context to Claude's prompt
#     Step 3 (GENERATION): Claude generates an answer using only relevant info
#
#   Result: Fast, cheap, accurate answers grounded in YOUR data!
#
# THE FULL RAG PIPELINE:
#   ┌────────────────┐      ┌──────────────────┐      ┌─────────────┐
#   │  Google Sheets │─────▶│   Vector Store   │─────▶│   Claude    │
#   │  (knowledge)   │      │  (search index)  │      │  (answers)  │
#   └────────────────┘      └──────────────────┘      └─────────────┘
#        at startup              at query time             answer!
# =============================================================

import os
import logging
from dotenv import load_dotenv
from groq import Groq

from src.google_sheets import GoogleSheetsConnector
from src.google_drive import GoogleDriveConnector
from src.vector_store import VectorStore
from src.embeddings import chunk_text

load_dotenv()
logger = logging.getLogger(__name__)



class RAGPipeline:
    """
    The complete RAG pipeline: connects Google Sheets, Vector Store, and Claude.

    USAGE EXAMPLE:
        # Create the pipeline
        rag = RAGPipeline()

        # Load data from Google Sheets into the vector store
        rag.index_spreadsheet()

        # Ask questions!
        answer = rag.ask("What are the available product categories?")
        print(answer)
    """

    def __init__(
        self,
        vector_store_path: str = "data/vector_store/store.pkl",
        top_k: int = None,
        chunk_size: int = None,
        chunk_overlap: int = None,
    ):
        """
        Initialize all components of the RAG pipeline.

        PARAMETERS:
            vector_store_path (str): Where to save/load the vector store on disk
            top_k (int): How many chunks to retrieve per query (overrides .env)
            chunk_size (int): Max characters per text chunk (overrides .env)
            chunk_overlap (int): Character overlap between chunks (overrides .env)
        """
        # --- Load configuration (from .env or parameters) ---
        # int() converts string to integer
        # The "or" operator returns the right side if the left side is falsy (None/0/"")
        self.top_k = top_k or int(os.environ.get("RAG_TOP_K", "5"))
        self.chunk_size = chunk_size or int(os.environ.get("CHUNK_SIZE", "500"))
        self.chunk_overlap = chunk_overlap or int(os.environ.get("CHUNK_OVERLAP", "50"))
        self.vector_store_path = vector_store_path

        logger.info("Initializing RAG Pipeline...")
        logger.info(f"  top_k={self.top_k}, chunk_size={self.chunk_size}, chunk_overlap={self.chunk_overlap}")

        # --- Initialize components ---

        # 1. Google Sheets connector
        logger.info("Connecting to Google Sheets...")
        self.sheets = GoogleSheetsConnector()

        # 1b. Google Drive connector
        logger.info("Connecting to Google Drive...")
        self.drive = GoogleDriveConnector()

        # 2. Vector store (search engine)
        logger.info("Initializing vector store...")
        self.vector_store = VectorStore()

        # 3. Groq API client
        logger.info("Initializing Groq API client...")
        self.claude = Groq(
            api_key=os.environ.get("GROQ_API_KEY")
        )

        # Track conversation history for multi-turn conversations
        # Each message is a dict: {"role": "user" or "assistant", "content": "..."}
        self.conversation_history: list[dict] = []

        logger.info("RAG Pipeline ready!")

    def index_spreadsheet(
        self,
        sheet_name: str = None,
        force_reindex: bool = False
    ) -> int:
        """
        Load data from Google Sheets and build the vector search index.

        WHAT IS INDEXING?
            Indexing means processing all our data ONCE upfront:
            - Read text from Google Sheets
            - Split into chunks
            - Create embeddings for each chunk
            - Store in the vector store

            After indexing, searches are very fast because the
            embeddings are already computed and stored.

        PARAMETERS:
            sheet_name (str): Worksheet name (None = first sheet)
            force_reindex (bool): If True, always reindex even if saved store exists.
                                  If False, load saved store if available.

        RETURNS:
            int: Number of chunks indexed
        """
        # --- Try to load existing index from disk first ---
        if not force_reindex:
            if self.vector_store.load(self.vector_store_path):
                logger.info(f"Loaded existing index ({self.vector_store.size} chunks)")
                return self.vector_store.size

        # --- Build a fresh index from Google Sheets ---
        logger.info("Building fresh index from Google Sheets...")

        all_chunks = []
        all_metadata = []

        # Determine which sheets to index
        if sheet_name:
            sheets_to_index = [sheet_name]
        else:
            sheets_to_index = self.sheets.get_sheet_names()

        for sname in sheets_to_index:
            row_texts = self.sheets.get_all_text(sname)
            row_metadata = self.sheets.get_metadata(sname)

            if not row_texts:
                logger.warning(f"No text found in sheet '{sname}', skipping.")
                continue

            logger.info(f"Retrieved {len(row_texts)} rows from sheet '{sname}'")

            for i, (text, meta) in enumerate(zip(row_texts, row_metadata)):
                chunks = chunk_text(text, self.chunk_size, self.chunk_overlap)
                for chunk_num, chunk in enumerate(chunks):
                    all_chunks.append(chunk)
                    all_metadata.append({
                        **meta,
                        "_sheet": sname,
                        "_row_index": i,
                        "_chunk_index": chunk_num,
                        "_total_chunks": len(chunks),
                    })

        # ── Also index Google Drive files (PDFs + Docs) ──────────────────────
        drive_files = self.drive.get_all_texts_with_metadata()
        if drive_files:
            logger.info(f"Indexing {len(drive_files)} file(s) from Google Drive...")
        for text, meta in drive_files:
            chunks = chunk_text(text, self.chunk_size, self.chunk_overlap)
            for chunk_num, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metadata.append({
                    **meta,
                    "_chunk_index":  chunk_num,
                    "_total_chunks": len(chunks),
                })

        if not all_chunks:
            logger.warning("No text found in Sheets or Drive!")
            return 0

        logger.info(f"Split into {len(all_chunks)} chunks total")

        # Step 3: Add all chunks to the vector store (creates embeddings)
        self.vector_store.add_texts(all_chunks, all_metadata)

        # Step 4: Save to disk for faster loading next time
        self.vector_store.save(self.vector_store_path)

        logger.info(f"Indexing complete! {self.vector_store.size} chunks indexed")
        return self.vector_store.size

    def retrieve(self, query: str) -> list[dict]:
        """
        The RETRIEVAL step of RAG — find relevant chunks for a query.

        PARAMETERS:
            query (str): The user's question

        RETURNS:
            list[dict]: Retrieved chunks with text, score, and metadata
        """
        results = self.vector_store.search(query, top_k=self.top_k)

        # Convert SearchResult objects to plain dicts for easier use
        retrieved = []
        for result in results:
            retrieved.append({
                "text": result.text,
                "score": result.score,
                "metadata": result.metadata,
            })

        return retrieved

    def _build_context(self, retrieved_chunks: list[dict]) -> str:
        """
        Format retrieved chunks into a context string for Claude.

        WHAT IS CONTEXT?
            Context is the information we give Claude to help it answer.
            We format our retrieved chunks into a clear, structured string
            that Claude can easily read and reference.

        PARAMETERS:
            retrieved_chunks (list[dict]): Output from retrieve()

        RETURNS:
            str: Formatted context string
        """
        if not retrieved_chunks:
            return "No relevant information found in the spreadsheet."

        # Build a nicely formatted context block
        context_parts = []
        context_parts.append("Here is the relevant information from the spreadsheet:\n")

        for i, chunk in enumerate(retrieved_chunks, start=1):
            # start=1 makes enumerate start counting from 1 instead of 0
            score_percent = chunk["score"] * 100
            context_parts.append(
                f"[Source {i}] (Relevance: {score_percent:.1f}%)\n"
                f"{chunk['text']}\n"
            )

        return "\n".join(context_parts)

    def _build_system_prompt(self) -> str:
        """
        Create the system prompt that defines Claude's behavior.

        WHAT IS A SYSTEM PROMPT?
            The system prompt is a set of instructions given to Claude
            BEFORE the conversation starts. It defines:
            - Claude's role and personality
            - What it should/shouldn't do
            - How it should format its answers

        A good system prompt is crucial for useful RAG systems!
        """
        return """You are a helpful assistant that answers questions based on data from a Google Spreadsheet.

Your job:
1. Read the provided spreadsheet context carefully
2. Answer the user's question using ONLY information from the context
3. If the answer is not in the context, clearly say so — don't make things up
4. Keep answers concise and factual
5. If relevant, mention which source number contains the information

Rules:
- Only use information from the provided context
- Do not hallucinate or add information not in the context
- Be friendly and professional
- If asked about something outside the spreadsheet data, politely redirect"""

    def ask(
        self,
        question: str,
        remember_history: bool = True,
        show_sources: bool = True
    ) -> dict:
        """
        The main method — ask a question and get an answer!

        This is the complete RAG loop:
            1. Retrieve relevant chunks from the vector store
            2. Build a prompt with the context + question
            3. Send to Claude
            4. Return the answer

        PARAMETERS:
            question (str): The user's question
            remember_history (bool): If True, Claude remembers previous turns
                                     (multi-turn conversation mode)
            show_sources (bool): If True, include retrieved sources in response

        RETURNS:
            dict: {
                "answer": str,           # Claude's answer
                "sources": list[dict],   # Retrieved chunks used as context
                "question": str,         # The original question
            }
        """
        logger.info(f"Processing question: '{question[:80]}...'")

        # STEP 1: RETRIEVE — find relevant chunks
        retrieved = self.retrieve(question)
        logger.info(f"Retrieved {len(retrieved)} relevant chunks")

        # STEP 2: BUILD CONTEXT — format chunks for Claude
        context = self._build_context(retrieved)

        # STEP 3: BUILD MESSAGE — combine context + question
        # We add the context to the user's message so Claude sees it
        user_message = f"""Context from spreadsheet:
{context}

---

Question: {question}"""

        # STEP 4: MANAGE CONVERSATION HISTORY
        if remember_history:
            # Add user message to history
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })
            messages_to_send = self.conversation_history
        else:
            # Single-turn: don't use conversation history
            messages_to_send = [{"role": "user", "content": user_message}]

        # STEP 5: CALL CLAUDE API
        logger.info("Sending to Claude...")

        # anthropic.messages.create() sends a request to Claude
        # and returns a response object
        response = self.claude.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=1024,
            messages=[{"role": "system", "content": self._build_system_prompt()}] + messages_to_send
        )

        answer_text = response.choices[0].message.content

        # STEP 6: UPDATE HISTORY
        if remember_history:
            # Add Claude's response to history for next turn
            self.conversation_history.append({
                "role": "assistant",
                "content": answer_text
            })

        # STEP 7: RETURN RESULTS
        result = {
            "answer": answer_text,
            "question": question,
            "sources": retrieved if show_sources else [],
        }

        logger.info("Answer generated successfully")
        return result

    def clear_history(self):
        """
        Clear the conversation history to start a fresh conversation.

        Useful when the topic changes or you want to reset context.
        """
        self.conversation_history = []
        logger.info("Conversation history cleared")

    def reindex(self, sheet_name: str = None) -> int:
        """
        Force a complete reindex from Google Sheets.

        Use this when:
        - You've updated the spreadsheet
        - You want to refresh the data

        PARAMETERS:
            sheet_name (str): Worksheet to reindex (None = first sheet)

        RETURNS:
            int: Number of chunks after reindexing
        """
        logger.info("Force reindexing from Google Sheets...")
        self.vector_store.clear()
        return self.index_spreadsheet(sheet_name=sheet_name, force_reindex=True)
