"""Document loading utilities for PDFs, RSS feeds, web pages, and CSV files."""

from __future__ import annotations

import os
from datetime import timezone, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import feedparser
import pandas as pd
import requests
from bs4 import BeautifulSoup
from langchain_core.documents import Document
from pypdf import PdfReader
from pypdf.errors import PdfReadError


REQUEST_TIMEOUT_SECONDS = 15
USER_AGENT = (
    "SamajhDocumentLoader/1.0 (+https://samajh.local; civic-intelligence-ingestion)"
)


def _utc_timestamp() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    """Normalize arbitrary values into cleaned text."""
    if value is None:
        return ""

    if isinstance(value, float) and pd.isna(value):
        return ""

    text = str(value).replace("\x00", " ")
    text = " ".join(text.split())
    return text.strip()


def _base_metadata(source: str, content_type: str) -> dict[str, Any]:
    """Create common metadata for all loaded documents."""
    return {
        "source": source,
        "content_type": content_type,
        "loaded_at": _utc_timestamp(),
    }


def load_pdf(file_path: str) -> list[Document]:
    """Load a PDF file into page-level LangChain documents.

    Args:
        file_path: Path to the PDF file on disk.

    Returns:
        A list of LangChain Document objects, one per non-empty page.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is empty or cannot be parsed into usable text.
    """
    pdf_path = Path(file_path)

    if not pdf_path.exists() or not pdf_path.is_file():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    if pdf_path.stat().st_size == 0:
        raise ValueError(f"PDF file is empty: {file_path}")

    documents: list[Document] = []
    source = str(pdf_path.resolve())

    try:
        reader = PdfReader(str(pdf_path))
    except (PdfReadError, ValueError, OSError) as exc:
        raise ValueError(f"Failed to read PDF file '{file_path}': {exc}") from exc

    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ValueError(f"PDF contains no pages: {file_path}")

    for index, page in enumerate(reader.pages, start=1):
        try:
            page_text = _clean_text(page.extract_text())
        except Exception as exc:
            raise ValueError(
                f"Failed to extract text from page {index} in '{file_path}': {exc}"
            ) from exc

        if not page_text:
            continue

        metadata = _base_metadata(source=source, content_type="pdf")
        metadata.update(
            {
                "title": pdf_path.stem,
                "source_filename": pdf_path.name,
                "page_number": index,
                "total_pages": total_pages,
            }
        )
        documents.append(Document(page_content=page_text, metadata=metadata))

    if not documents:
        raise ValueError(f"No extractable text found in PDF: {file_path}")

    return documents


def load_rss_feed(url: str, source_name: str) -> list[Document]:
    """Load entries from an RSS or Atom feed into LangChain documents.

    Args:
        url: RSS/Atom feed URL.
        source_name: Human-readable source label for the feed.

    Returns:
        A list of LangChain Document objects, one per non-empty feed entry.

    Raises:
        ValueError: If the feed cannot be fetched, parsed, or contains no usable entries.
    """
    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"Failed to fetch RSS feed '{url}': {exc}") from exc

    parsed = feedparser.parse(response.content)

    if getattr(parsed, "bozo", 0):
        parse_exception = getattr(parsed, "bozo_exception", None)
        if not getattr(parsed, "entries", []):
            raise ValueError(
                f"Failed to parse RSS feed '{url}': {parse_exception or 'unknown error'}"
            )

    documents: list[Document] = []
    feed_title = _clean_text(parsed.feed.get("title")) or _clean_text(source_name)

    for index, entry in enumerate(parsed.entries):
        title = _clean_text(entry.get("title"))
        summary = _clean_text(entry.get("summary") or entry.get("description"))
        content_blocks = entry.get("content", [])
        content_text = " ".join(
            _clean_text(block.get("value")) for block in content_blocks if isinstance(block, dict)
        )
        body = _clean_text(" ".join(part for part in [title, summary, content_text] if part))

        if not body:
            continue

        published_date = _clean_text(
            entry.get("published")
            or entry.get("updated")
            or entry.get("pubDate")
        )
        entry_url = _clean_text(entry.get("link")) or url

        metadata = _base_metadata(source=entry_url, content_type="rss")
        metadata.update(
            {
                "title": title or feed_title or f"{source_name} entry {index + 1}",
                "feed_url": url,
                "feed_title": feed_title or source_name,
                "source_name": source_name,
                "published_date": published_date,
                "entry_index": index,
            }
        )
        documents.append(Document(page_content=body, metadata=metadata))

    if not documents:
        raise ValueError(f"No usable entries found in RSS feed: {url}")

    return documents


def load_web_page(url: str) -> Document:
    """Load a web page into a single LangChain document.

    Args:
        url: Public URL of the web page.

    Returns:
        A LangChain Document containing the cleaned page text.

    Raises:
        ValueError: If the page cannot be fetched or has no extractable text.
    """
    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"Failed to fetch web page '{url}': {exc}") from exc

    content_type_header = response.headers.get("Content-Type", "").lower()
    if not response.text.strip():
        raise ValueError(f"Web page response was empty: {url}")

    try:
        soup = BeautifulSoup(response.text, "lxml")
    except Exception as exc:
        raise ValueError(f"Failed to parse web page '{url}': {exc}") from exc

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    title = _clean_text(soup.title.string if soup.title and soup.title.string else "")
    main_content = soup.find("main") or soup.find("article") or soup.body or soup
    page_text = _clean_text(main_content.get_text(separator=" ", strip=True))

    if not page_text:
        raise ValueError(f"No extractable text found on web page: {url}")

    parsed_url = urlparse(url)
    fallback_title = parsed_url.path.strip("/").split("/")[-1] or parsed_url.netloc

    metadata = _base_metadata(source=url, content_type="web_page")
    metadata.update(
        {
            "title": title or fallback_title,
            "url": url,
            "scraped_at": _utc_timestamp(),
            "mime_type": content_type_header or "text/html",
        }
    )

    return Document(page_content=page_text, metadata=metadata)


def load_csv(file_path: str, text_columns: list[str]) -> list[Document]:
    """Load a CSV file into row-level LangChain documents.

    Args:
        file_path: Path to the CSV file on disk.
        text_columns: Column names whose values should be combined into document text.

    Returns:
        A list of LangChain Document objects, one per non-empty row.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If text columns are missing, the CSV is unreadable, or no usable rows exist.
    """
    csv_path = Path(file_path)

    if not csv_path.exists() or not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    if csv_path.stat().st_size == 0:
        raise ValueError(f"CSV file is empty: {file_path}")

    cleaned_columns = [_clean_text(column) for column in text_columns if _clean_text(column)]
    if not cleaned_columns:
        raise ValueError("At least one valid text column must be provided for CSV loading.")

    try:
        dataframe = pd.read_csv(csv_path)
    except Exception as exc:
        raise ValueError(f"Failed to read CSV file '{file_path}': {exc}") from exc

    if dataframe.empty:
        raise ValueError(f"CSV contains no rows: {file_path}")

    missing_columns = [column for column in cleaned_columns if column not in dataframe.columns]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"Missing required CSV columns in '{file_path}': {missing}")

    documents: list[Document] = []
    source = str(csv_path.resolve())

    for row_index, row in dataframe.iterrows():
        text_parts = [_clean_text(row[column]) for column in cleaned_columns]
        page_content = _clean_text(" ".join(part for part in text_parts if part))

        if not page_content:
            continue

        title = ""
        for candidate in ("title", "name", "headline"):
            if candidate in dataframe.columns:
                title = _clean_text(row.get(candidate))
                if title:
                    break

        published_date = ""
        for candidate in ("published_date", "published", "date", "created_at", "updated_at"):
            if candidate in dataframe.columns:
                published_date = _clean_text(row.get(candidate))
                if published_date:
                    break

        row_metadata = {
            column: _clean_text(row[column])
            for column in dataframe.columns
            if column not in cleaned_columns and _clean_text(row[column])
        }

        metadata = _base_metadata(source=source, content_type="csv")
        metadata.update(
            {
                "title": title or f"{csv_path.stem} row {int(row_index) + 1}",
                "source_filename": csv_path.name,
                "row_index": int(row_index),
                "text_columns": cleaned_columns,
                "published_date": published_date,
            }
        )
        metadata.update(row_metadata)

        documents.append(Document(page_content=page_content, metadata=metadata))

    if not documents:
        raise ValueError(f"No usable text rows found in CSV: {file_path}")

    return documents