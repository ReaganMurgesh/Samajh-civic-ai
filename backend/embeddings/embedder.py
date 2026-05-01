"""Embedding utilities for multilingual document and query encoding."""

from __future__ import annotations

import logging
import re
from typing import Any
import hashlib

from langchain_core.documents import Document
from langdetect import DetectorFactory, LangDetectException, detect
from tqdm import tqdm

DetectorFactory.seed = 0

LOGGER = logging.getLogger(__name__)

LANGUAGE_CODE_MAP: dict[str, str] = {
    "en": "english",
    "hi": "hindi",
    "ta": "tamil",
    "te": "telugu",
    "kn": "kannada",
    "bn": "bengali",
    "mr": "marathi",
}


class MultilingualEmbedder:
    """Sentence-transformer based embedder for multilingual civic content."""

    MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(self) -> None:
        """Initialize the embedder with lazy model loading."""
        self._model: Any | None = None
        self._use_fallback = False

    @property
    def model(self) -> Any:
        """Return a cached sentence-transformer model instance."""
        if self._model is None and not self._use_fallback:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.MODEL_NAME)
            except Exception as exc:
                LOGGER.warning("Falling back to deterministic embeddings: %s", exc)
                self._use_fallback = True
        return self._model

    def _fallback_embedding(self, text: str, dims: int = 384) -> list[float]:
        """Generate deterministic lightweight embeddings when model loading fails."""
        vector = [0.0] * dims
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            idx = int(digest[:8], 16) % dims
            vector[idx] += 1.0
        norm = sum(v * v for v in vector) ** 0.5
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text before language detection or embedding.

        Args:
            text: Raw text.

        Returns:
            Cleaned text with normalized spacing.
        """
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"[ \t]+", " ", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    @staticmethod
    def _detect_language_name(text: str) -> str:
        """Detect a human-readable language name for input text.

        Args:
            text: Input text.

        Returns:
            Lowercase human-readable language name.
        """
        try:
            code = detect(text)
            return LANGUAGE_CODE_MAP.get(code, code.lower())
        except LangDetectException:
            return "unknown"

    def _encode(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Encode text batch into normalized embeddings.

        Args:
            texts: List of input texts.
            batch_size: Sentence-transformers batch size.

        Returns:
            List of embedding vectors as Python floats.
        """
        if not texts:
            return []

        model = self.model
        if self._use_fallback or model is None:
            return [self._fallback_embedding(text) for text in texts]

        try:
            vectors = model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return [vector.astype(float).tolist() for vector in vectors]
        except Exception as exc:
            LOGGER.warning("Embedding model failed at runtime, switching to fallback: %s", exc)
            self._use_fallback = True
            return [self._fallback_embedding(text) for text in texts]

    def embed_chunks(
        self,
        chunks: list[Document],
        batch_size: int = 32,
    ) -> list[tuple[Document, list[float]]]:
        """Embed document chunks and return paired documents with vectors.

        Args:
            chunks: Chunked LangChain documents.
            batch_size: Encoding batch size.

        Returns:
            Tuples of original chunk documents and embedding vectors.

        Raises:
            ValueError: If batch_size is invalid.
        """
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than 0.")

        valid_chunks: list[Document] = []
        texts: list[str] = []

        for chunk in chunks:
            if not isinstance(chunk, Document):
                continue

            normalized_text = self._normalize_text(chunk.page_content)
            if not normalized_text:
                continue

            metadata = dict(chunk.metadata or {})
            metadata.setdefault("language", self._detect_language_name(normalized_text))
            valid_chunks.append(Document(page_content=normalized_text, metadata=metadata))
            texts.append(normalized_text)

        if not texts:
            return []

        embeddings: list[list[float]] = []
        total_batches = (len(texts) + batch_size - 1) // batch_size

        for start in tqdm(
            range(0, len(texts), batch_size),
            total=total_batches,
            desc="Embedding chunks",
        ):
            batch_texts = texts[start : start + batch_size]
            embeddings.extend(self._encode(batch_texts, batch_size=batch_size))

        return list(zip(valid_chunks, embeddings))

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string.

        Args:
            query: User query text.

        Returns:
            A normalized embedding vector for the query.

        Raises:
            ValueError: If the query is empty after normalization.
        """
        normalized_query = self._normalize_text(query)
        if not normalized_query:
            raise ValueError("query must not be empty.")

        return self._encode([normalized_query], batch_size=1)[0]

    def detect_and_embed(self, text: str) -> dict[str, Any]:
        """Detect language and embed an arbitrary text input.

        Args:
            text: Text to analyze.

        Returns:
            Dictionary containing normalized text, detected language, and embedding.

        Raises:
            ValueError: If input text is empty after normalization.
        """
        normalized_text = self._normalize_text(text)
        if not normalized_text:
            raise ValueError("text must not be empty.")

        language = self._detect_language_name(normalized_text)
        embedding = self.embed_query(normalized_text)

        return {
            "text": normalized_text,
            "language": language,
            "embedding": embedding,
        }