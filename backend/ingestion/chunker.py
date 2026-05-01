"""Utilities for splitting LangChain documents into retrieval-friendly chunks."""

from __future__ import annotations

import copy
import re
from typing import Iterable

from langchain_core.documents import Document

from backend.utils.config import config


def _validate_chunk_params(chunk_size: int, overlap: int) -> None:
    """Validate chunking parameters.

    Args:
        chunk_size: Maximum approximate size of each chunk in characters.
        overlap: Number of overlapping characters between consecutive chunks.

    Raises:
        ValueError: If chunking parameters are invalid.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0.")
    if overlap < 0:
        raise ValueError("overlap must be greater than or equal to 0.")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size.")


def _clean_text(text: str) -> str:
    """Normalize text before chunking.

    Args:
        text: Raw text content.

    Returns:
        Cleaned text with normalized whitespace.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _normalize_metadata(metadata: dict | None) -> dict:
    """Return a safe JSON-serializable metadata dictionary.

    Args:
        metadata: Input metadata.

    Returns:
        A shallow-copied metadata dictionary.
    """
    if not metadata:
        return {}
    return copy.deepcopy(metadata)


def _split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks using paragraph-aware heuristics.

    Args:
        text: Clean text to split.
        chunk_size: Target maximum chunk size in characters.
        overlap: Overlap size in characters.

    Returns:
        List of text chunks.
    """
    if not text:
        return []

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current.strip())
            current = ""

        if len(paragraph) <= chunk_size:
            current = paragraph
            continue

        start = 0
        while start < len(paragraph):
            end = min(start + chunk_size, len(paragraph))
            if end < len(paragraph):
                split_at = max(
                    paragraph.rfind(". ", start, end),
                    paragraph.rfind("! ", start, end),
                    paragraph.rfind("? ", start, end),
                    paragraph.rfind("\n", start, end),
                    paragraph.rfind(" ", start, end),
                )
                if split_at > start + max(chunk_size // 3, 1):
                    end = split_at + 1

            piece = paragraph[start:end].strip()
            if piece:
                chunks.append(piece)

            if end >= len(paragraph):
                break

            start = max(end - overlap, start + 1)

    if current:
        chunks.append(current.strip())

    return [chunk for chunk in chunks if chunk]


def _extract_sections(text: str) -> list[str]:
    """Extract structure-aware sections from text.

    Args:
        text: Document content.

    Returns:
        List of candidate sections preserving headings where possible.
    """
    cleaned = _clean_text(text)
    if not cleaned:
        return []

    lines = [line.strip() for line in cleaned.split("\n")]
    sections: list[str] = []
    current_section: list[str] = []

    heading_pattern = re.compile(
        r"^([A-Z][A-Za-z0-9 ,:/()\-]{2,}|#{1,6}\s+.+|\d+(\.\d+)*\s+.+)$"
    )

    for line in lines:
        if not line:
            if current_section and current_section[-1] != "":
                current_section.append("")
            continue

        is_heading = bool(heading_pattern.match(line)) and len(line) <= 120

        if is_heading and current_section:
            section_text = "\n".join(current_section).strip()
            if section_text:
                sections.append(section_text)
            current_section = [line]
        else:
            current_section.append(line)

    if current_section:
        section_text = "\n".join(current_section).strip()
        if section_text:
            sections.append(section_text)

    return sections or [cleaned]


def _build_chunk_documents(
    docs: Iterable[Document],
    splitter: callable,
    chunk_size: int,
    overlap: int,
) -> list[Document]:
    """Create chunk documents from source documents.

    Args:
        docs: Input LangChain documents.
        splitter: Callable returning string chunks for a document.
        chunk_size: Target chunk size.
        overlap: Overlap size.

    Returns:
        A list of chunked documents.
    """
    chunked_documents: list[Document] = []

    for doc in docs:
        if not isinstance(doc, Document):
            continue

        cleaned_text = _clean_text(doc.page_content)
        if not cleaned_text:
            continue

        raw_chunks = splitter(cleaned_text, chunk_size, overlap)
        if not raw_chunks:
            continue

        total_chunks = len(raw_chunks)
        base_metadata = _normalize_metadata(doc.metadata)

        for index, chunk_text in enumerate(raw_chunks):
            metadata = _normalize_metadata(base_metadata)
            metadata["chunk_index"] = index
            metadata["total_chunks"] = total_chunks
            chunked_documents.append(Document(page_content=chunk_text, metadata=metadata))

    return chunked_documents


def chunk_documents(
    docs: list[Document],
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[Document]:
    """Chunk documents using paragraph-aware text splitting.

    Args:
        docs: Source documents.
        chunk_size: Target maximum chunk size in characters.
        overlap: Number of overlapping characters.

    Returns:
        Chunked LangChain documents preserving source metadata.
    """
    _validate_chunk_params(chunk_size, overlap)
    return _build_chunk_documents(docs, _split_long_text, chunk_size, overlap)


def chunk_with_structure(
    docs: list[Document],
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[Document]:
    """Chunk documents while attempting to preserve structural sections.

    This function first breaks documents into heading-aware sections and then
    applies paragraph-aware chunking to sections that exceed the target size.

    Args:
        docs: Source documents.
        chunk_size: Target maximum chunk size in characters.
        overlap: Number of overlapping characters.

    Returns:
        Structure-aware chunked documents.
    """
    _validate_chunk_params(chunk_size, overlap)

    def structured_splitter(text: str, size: int, ov: int) -> list[str]:
        final_chunks: list[str] = []
        for section in _extract_sections(text):
            if len(section) <= size:
                final_chunks.append(section)
            else:
                final_chunks.extend(_split_long_text(section, size, ov))
        return [chunk for chunk in final_chunks if chunk.strip()]

    return _build_chunk_documents(docs, structured_splitter, chunk_size, overlap)


def add_domain_tag(
    chunks: list[Document],
    domain: str,
    language: str,
    confidence: float = 1.0,
) -> list[Document]:
    """Add domain and language annotations to chunk metadata.

    Args:
        chunks: Chunked documents to annotate.
        domain: Domain label to assign.
        language: Human-readable lowercase language label.
        confidence: Confidence score for the applied tag.

    Returns:
        Updated chunk documents with enriched metadata.

    Raises:
        ValueError: If domain or language values are invalid.
    """
    normalized_domain = domain.strip().lower()
    normalized_language = language.strip().lower()

    if normalized_domain not in config.supported_domains:
        raise ValueError(
            f"Unsupported domain '{domain}'. Supported domains: {config.supported_domains}"
        )
    if not normalized_language:
        raise ValueError("language must be a non-empty string.")
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError("confidence must be between 0.0 and 1.0.")

    tagged_chunks: list[Document] = []

    for chunk in chunks:
        if not isinstance(chunk, Document):
            continue

        metadata = _normalize_metadata(chunk.metadata)
        metadata["domain"] = normalized_domain
        metadata["language"] = normalized_language
        metadata["tag_confidence"] = float(confidence)
        metadata.setdefault("chunk_index", 0)
        metadata.setdefault("total_chunks", 1)

        tagged_chunks.append(
            Document(page_content=_clean_text(chunk.page_content), metadata=metadata)
        )

    return tagged_chunks