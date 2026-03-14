# =============================================================
# src/embeddings.py
#
# PURPOSE:
#   This module converts text into "embeddings" (number vectors).
#   Embeddings are the mathematical heart of RAG systems.
#
# WHAT IS AN EMBEDDING?
#   An embedding is a list of numbers (a vector) that represents
#   the MEANING of a piece of text.
#
#   Example:
#       "The cat sat on the mat"  → [0.12, -0.45, 0.88, 0.03, ...]
#       "A kitten rested on rug"  → [0.11, -0.43, 0.85, 0.05, ...]
#       "Python is a language"    → [-0.78, 0.21, -0.34, 0.91, ...]
#
#   Notice: the cat/kitten sentences have SIMILAR numbers because
#   they mean similar things. The Python sentence has DIFFERENT
#   numbers because it means something different.
#
#   This lets us find texts that are semantically similar using
#   simple math (dot product / cosine similarity).
#
# WHAT IS COSINE SIMILARITY?
#   A way to measure how similar two vectors are.
#   - Score of 1.0 = identical meaning
#   - Score of 0.0 = completely unrelated
#   - Score of -1.0 = opposite meaning
# =============================================================

import logging
import os
import numpy as np  # NumPy: the math library for Python
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """
    Wraps a sentence-transformers model to create text embeddings.

    WHAT IS sentence-transformers?
        It's a library of pre-trained AI models that convert text
        to vectors. These models were trained on millions of text
        pairs to understand language meaning.

    THE MODEL WE USE: 'all-MiniLM-L6-v2'
        - Small and fast (good for learning/testing)
        - Downloads automatically on first use (~90 MB)
        - Creates 384-dimensional vectors
        - Good English language understanding
    """

    def __init__(self, model_name: str = None):
        """
        Load the embedding model.

        PARAMETERS:
            model_name (str): Which sentence-transformers model to use.
                              Falls back to EMBEDDING_MODEL env var, then all-MiniLM-L6-v2.
        """
        model_name = model_name or os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        logger.info(f"Loading embedding model: {model_name}")
        logger.info("(This may take a moment on first run — the model downloads ~90MB)")

        # SentenceTransformer loads the model from HuggingFace
        # or from local cache if already downloaded
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name

        # Get the size of vectors this model produces
        # encode() returns a 2D array; shape[1] is the number of dimensions
        test_embedding = self.model.encode(["test"])
        self.embedding_dim = test_embedding.shape[1]

        logger.info(f"Model loaded! Creates {self.embedding_dim}-dimensional vectors")

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """
        Convert a list of text strings into a matrix of embeddings.

        PARAMETERS:
            texts (list[str]): e.g., ["Hello world", "Python is fun"]

        RETURNS:
            np.ndarray: A 2D array of shape (num_texts, embedding_dim)
                        Each row is one text's embedding vector.

        WHAT IS np.ndarray?
            A numpy array — think of it as a very efficient list of numbers.
            A 2D array is like a grid/matrix:
                Row 0: [0.12, -0.45, 0.88, ...] ← embedding for texts[0]
                Row 1: [0.31, 0.07, -0.22, ...]  ← embedding for texts[1]
        """
        if not texts:
            # If empty list, return empty array with correct shape
            return np.array([]).reshape(0, self.embedding_dim)

        logger.info(f"Creating embeddings for {len(texts)} texts...")

        # encode() processes all texts and returns a numpy array
        # show_progress_bar=True shows a loading bar in the terminal
        embeddings = self.model.encode(
            texts,
            show_progress_bar=len(texts) > 10,  # Only show bar for many texts
            convert_to_numpy=True                 # Return numpy array (not tensor)
        )

        logger.info(f"Created embeddings with shape: {embeddings.shape}")
        return embeddings

    def embed_query(self, query: str) -> np.ndarray:
        """
        Convert a single query string into an embedding vector.

        WHY SEPARATE FROM embed_texts?
            When searching, we have ONE query but MANY documents.
            This method handles the single-query case cleanly.

        PARAMETERS:
            query (str): The user's question, e.g., "What is the price of X?"

        RETURNS:
            np.ndarray: A 1D array of shape (embedding_dim,)
                        e.g., [0.12, -0.45, 0.88, ...]
        """
        # encode() on a single string returns a 1D array
        embedding = self.model.encode(query, convert_to_numpy=True)
        return embedding


def cosine_similarity(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
    """
    Calculate how similar two vectors are using cosine similarity.

    MATH EXPLANATION:
        cosine_similarity(A, B) = (A · B) / (||A|| × ||B||)

        Where:
        - A · B  = dot product (sum of element-wise products)
        - ||A||  = magnitude/length of vector A (Euclidean norm)
        - ||B||  = magnitude/length of vector B

        By dividing by the magnitudes, we make it scale-independent.
        Only the DIRECTION of the vector matters, not its length.

    PARAMETERS:
        vector_a, vector_b (np.ndarray): Two embedding vectors of same size

    RETURNS:
        float: Similarity score between -1.0 and 1.0
               (in practice for text, usually between 0.0 and 1.0)
    """
    # np.dot() = dot product
    # np.linalg.norm() = vector length (Euclidean norm = sqrt(sum of squares))
    dot_product = np.dot(vector_a, vector_b)
    magnitude_a = np.linalg.norm(vector_a)
    magnitude_b = np.linalg.norm(vector_b)

    # Avoid division by zero if a vector is all zeros
    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return float(dot_product / (magnitude_a * magnitude_b))


def batch_cosine_similarity(query_vector: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """
    Calculate cosine similarity between one query and MANY documents at once.

    WHY BATCH?
        Doing this in one matrix operation is MUCH faster than
        calling cosine_similarity() in a loop for each document.
        This is the power of NumPy — vectorized operations.

    PARAMETERS:
        query_vector (np.ndarray): Shape (dim,) — the query embedding
        matrix (np.ndarray): Shape (num_docs, dim) — all document embeddings

    RETURNS:
        np.ndarray: Shape (num_docs,) — similarity score for each document
    """
    # matrix @ query_vector = dot product of each row with the query
    # The @ operator in Python means matrix multiplication
    dot_products = matrix @ query_vector

    # Calculate the magnitude (length) of each document vector
    # np.linalg.norm(axis=1) = norm of each row
    doc_magnitudes = np.linalg.norm(matrix, axis=1)

    # Calculate the magnitude of the query vector
    query_magnitude = np.linalg.norm(query_vector)

    # Avoid division by zero
    denominator = doc_magnitudes * query_magnitude

    # np.where(condition, value_if_true, value_if_false)
    # If denominator is 0, return 0.0 to avoid division error
    similarities = np.where(denominator != 0, dot_products / denominator, 0.0)

    return similarities


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Split a long text into smaller overlapping chunks.

    WHY CHUNK TEXT?
        Embedding models have a maximum input size.
        Also, smaller chunks = more precise retrieval.
        When a user asks a question, we want to retrieve
        the SPECIFIC part of a document that answers it,
        not the whole document.

    WHY OVERLAP?
        If we split text at exact boundaries, important
        information might be split across two chunks.
        Overlap ensures context near boundaries is preserved.

    EXAMPLE (chunk_size=20, overlap=5):
        Text: "The quick brown fox jumps over the lazy dog"
        Chunk 1: "The quick brown fox "
        Chunk 2: "fox jumps over the l"    ← starts 5 chars before chunk 1 ended
        Chunk 3: "the lazy dog"

    PARAMETERS:
        text (str): The text to split
        chunk_size (int): Max characters per chunk
        overlap (int): Characters of overlap between consecutive chunks

    RETURNS:
        list[str]: List of text chunks
    """
    # If text is shorter than chunk_size, no need to split
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0  # Where the current chunk starts

    # Loop until we've processed the entire text
    while start < len(text):
        # Calculate where this chunk ends
        end = start + chunk_size

        # If we're not at the end of the text, try to break at a space
        # so we don't cut in the middle of a word
        if end < len(text):
            # Find the last space before the end point
            # rfind() searches backward from position `end`
            last_space = text.rfind(" ", start, end)
            if last_space > start:
                end = last_space  # Break at word boundary

        # Add this chunk (strip removes leading/trailing whitespace)
        chunk = text[start:end].strip()
        if chunk:  # Don't add empty chunks
            chunks.append(chunk)

        # Move start forward, but back up by `overlap` characters
        # to create the overlap with the next chunk
        start = end - overlap

        # Safety check: if start didn't advance (very long word), force advance
        if start <= 0:
            start = end

    return chunks
