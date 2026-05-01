"""ChromaDB-backed vector store utilities for the Samajh platform."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from backend.utils.config import config


class SamajhVectorStore:
    """Manage persistent ChromaDB collections for domain-aware document retrieval."""

    SUPPORTED_DOMAINS: tuple[str, ...] = (
        "law",
        "health",
        "finance",
        "news",
        "schemes",
        "environment",
        "career",
        "rights",
        "general",
    )

    def __init__(
        self,
        persist_dir: str | None = None,
        *,
        use_fallback_only: bool = False,
        persist_fallback: bool = True,
    ) -> None:
        """Initialize the persistent ChromaDB client and domain collections.

        Args:
            persist_dir: Optional override for the ChromaDB persistence directory.

        Raises:
            ValueError: If persistence directory configuration is invalid.
            RuntimeError: If the ChromaDB client or collections cannot be created.
        """
        selected_dir = persist_dir or config.chroma_persist_dir
        if not selected_dir or not str(selected_dir).strip():
            raise ValueError("A valid ChromaDB persistence directory is required.")

        self.persist_dir = str(Path(selected_dir).resolve())
        self._collections: dict[str, Any] = {}
        self._fallback_store: dict[str, list[tuple[Document, list[float]]]] = {
            domain: [] for domain in self.SUPPORTED_DOMAINS
        }
        self._use_fallback = False
        self._persist_fallback = bool(persist_fallback)

        if use_fallback_only:
            # Explicitly skip Chroma initialization (useful for ephemeral, privacy-sensitive stores).
            self._use_fallback = True
            self._init_error = "forced_fallback_only"
            if self._persist_fallback:
                self._load_fallback_store()
            return

        try:
            import chromadb

            Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            self._collections = {
                domain: self._client.get_or_create_collection(
                    name=f"samajh_{domain}",
                    metadata={"domain": domain, "platform": "samajh"},
                )
                for domain in self.SUPPORTED_DOMAINS
            }
        except Exception as exc:
            self._use_fallback = True
            self._init_error = str(exc)
            if self._persist_fallback:
                self._load_fallback_store()

    def _load_fallback_store(self) -> None:
        """Load fallback store from JSON."""
        import json
        import os
        fallback_file = Path(self.persist_dir) / "fallback_store.json"
        if fallback_file.exists():
            try:
                with open(fallback_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for domain, items in data.items():
                    if domain in self.SUPPORTED_DOMAINS:
                        for item in items:
                            doc = Document(page_content=item["content"], metadata=item["metadata"])
                            self._fallback_store[domain].append((doc, item["embedding"]))
            except Exception as e:
                print(f"Error loading fallback store: {e}")

    def _save_fallback_store(self) -> None:
        """Save fallback store to JSON."""
        if not getattr(self, "_persist_fallback", True):
            return
        import json
        fallback_file = Path(self.persist_dir) / "fallback_store.json"
        try:
            fallback_file.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            for domain, items in self._fallback_store.items():
                data[domain] = [
                    {
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "embedding": emb
                    }
                    for doc, emb in items
                ]
            with open(fallback_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving fallback store: {e}")

    def add_chunks(self, chunks: list[Document], embeddings: list[list[float]]) -> int:
        """Add embedded chunks into their domain collections with deduplication.

        Chunks are deduplicated using a stable identifier derived from source and
        chunk_index. Existing ids are upserted to keep the latest metadata/content.

        Args:
            chunks: LangChain documents to store.
            embeddings: Vector embeddings aligned one-to-one with chunks.

        Returns:
            Number of chunks successfully processed and upserted.

        Raises:
            ValueError: If inputs are empty or lengths do not match.
            RuntimeError: If storage in ChromaDB fails.
        """
        if not chunks:
            return 0

        if len(chunks) != len(embeddings):
            raise ValueError("Chunks and embeddings must have the same length.")

        if self._use_fallback:
            processed_count = 0
            for chunk, embedding in zip(chunks, embeddings):
                if not isinstance(chunk, Document):
                    continue
                if not chunk.page_content or not chunk.page_content.strip() or not embedding:
                    continue

                metadata = self._sanitize_metadata(chunk.metadata)
                domain = self._normalize_domain(metadata.get("domain"))
                chunk_id = self._build_chunk_id(metadata, chunk.page_content)
                metadata["domain"] = domain
                metadata["chunk_id"] = chunk_id

                stored_doc = Document(page_content=chunk.page_content, metadata=metadata)
                self._fallback_store[domain].append((stored_doc, [float(value) for value in embedding]))
                processed_count += 1
            if processed_count > 0:
                self._save_fallback_store()
            return processed_count

        grouped_payloads: dict[str, dict[str, list[Any]]] = {
            domain: {"ids": [], "documents": [], "metadatas": [], "embeddings": []}
            for domain in self.SUPPORTED_DOMAINS
        }

        processed_count = 0

        for chunk, embedding in zip(chunks, embeddings):
            if not isinstance(chunk, Document):
                continue
            if not chunk.page_content or not chunk.page_content.strip():
                continue
            if not embedding:
                continue

            metadata = self._sanitize_metadata(chunk.metadata)
            domain = self._normalize_domain(metadata.get("domain"))
            chunk_id = self._build_chunk_id(metadata, chunk.page_content)

            metadata["domain"] = domain
            metadata["chunk_id"] = chunk_id

            payload = grouped_payloads[domain]
            payload["ids"].append(chunk_id)
            payload["documents"].append(chunk.page_content)
            payload["metadatas"].append(metadata)
            payload["embeddings"].append([float(value) for value in embedding])
            processed_count += 1

        try:
            for domain, payload in grouped_payloads.items():
                if not payload["ids"]:
                    continue
                self._collections[domain].upsert(
                    ids=payload["ids"],
                    documents=payload["documents"],
                    metadatas=payload["metadatas"],
                    embeddings=payload["embeddings"],
                )
        except Exception as exc:
            raise RuntimeError(f"Failed to add chunks to ChromaDB: {exc}") from exc

        return processed_count

    def search(
        self,
        query_embedding: list[float],
        domain: str | None = None,
        language: str | None = None,
        top_k: int = 5,
    ) -> list[Document]:
        """Search ChromaDB collections by vector similarity.

        Args:
            query_embedding: Query vector embedding.
            domain: Optional domain-restricted search target.
            language: Optional lowercase language filter.
            top_k: Number of results to return.

        Returns:
            Ranked LangChain documents containing similarity_score in metadata.

        Raises:
            ValueError: If query embedding is empty or top_k is invalid.
            RuntimeError: If ChromaDB querying fails.
        """
        if not query_embedding:
            raise ValueError("Query embedding cannot be empty.")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0.")

        target_domains = (
            [self._normalize_domain(domain)] if domain else list(self.SUPPORTED_DOMAINS)
        )
        where_filter = self._build_where_filter(language=language)

        if self._use_fallback:
            scored_docs: list[Document] = []
            query_vector = [float(value) for value in query_embedding]

            for target_domain in target_domains:
                for stored_doc, emb in self._fallback_store.get(target_domain, []):
                    if where_filter and stored_doc.metadata.get("language") != where_filter.get("language"):
                        continue
                    score = self._cosine_similarity(query_vector, emb)
                    metadata = dict(stored_doc.metadata)
                    metadata["similarity_score"] = round(score, 6)
                    scored_docs.append(Document(page_content=stored_doc.page_content, metadata=metadata))

            return self._rank_and_limit(scored_docs, top_k)

        raw_results: list[Document] = []

        try:
            for target_domain in target_domains:
                collection = self._collections[target_domain]
                result = collection.query(
                    query_embeddings=[[float(value) for value in query_embedding]],
                    n_results=top_k,
                    where=where_filter,
                    include=["documents", "metadatas", "distances"],
                )
                raw_results.extend(self._convert_query_result(result))
        except Exception as exc:
            raise RuntimeError(f"Failed to search ChromaDB: {exc}") from exc

        return self._rank_and_limit(raw_results, top_k)

    def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        domain: str | None = None,
        language: str | None = None,
        top_k: int = 5,
    ) -> list[Document]:
        """Perform hybrid retrieval using vector similarity and simple keyword boosts.

        The keyword component is implemented locally to avoid extra dependencies. It
        boosts documents whose content overlaps with normalized query terms.

        Args:
            query: Raw user query text.
            query_embedding: Query vector embedding.
            domain: Optional domain restriction.
            language: Optional lowercase language filter.
            top_k: Number of final results to return.

        Returns:
            Ranked LangChain documents with similarity_score metadata.
        """
        initial_results = self.search(
            query_embedding=query_embedding,
            domain=domain,
            language=language,
            top_k=max(top_k * 3, top_k),
        )

        query_terms = self._tokenize(query)
        if not query_terms:
            return initial_results[:top_k]

        rescored_documents: list[tuple[float, Document]] = []

        for document in initial_results:
            metadata = dict(document.metadata)
            base_score = self._safe_float(metadata.get("similarity_score"), default=0.0)
            keyword_overlap = self._keyword_overlap_ratio(
                query_terms=query_terms,
                text=document.page_content,
            )
            combined_score = (base_score * 0.8) + (keyword_overlap * 0.2)
            metadata["similarity_score"] = round(combined_score, 6)
            rescored_documents.append(
                (combined_score, Document(page_content=document.page_content, metadata=metadata))
            )

        rescored_documents.sort(
            key=lambda item: (
                item[0],
                self._safe_int(item[1].metadata.get("chunk_index"), default=0) * -1,
            ),
            reverse=True,
        )

        deduplicated: list[Document] = []
        seen_ids: set[str] = set()

        for _, document in rescored_documents:
            chunk_id = str(document.metadata.get("chunk_id", "")).strip()
            if chunk_id and chunk_id in seen_ids:
                continue
            if chunk_id:
                seen_ids.add(chunk_id)
            deduplicated.append(document)
            if len(deduplicated) >= top_k:
                break

        return deduplicated

    def get_stats(self) -> dict:
        """Return high-level statistics for all supported ChromaDB collections.

        Returns:
            Dictionary containing persistence path, total chunks, and per-domain counts.
        """
        domain_counts: dict[str, int] = {}
        total_chunks = 0

        if self._use_fallback:
            for domain in self.SUPPORTED_DOMAINS:
                count = len(self._fallback_store.get(domain, []))
                domain_counts[domain] = count
                total_chunks += count

            return {
                "persist_dir": self.persist_dir,
                "total_chunks": total_chunks,
                "collections": domain_counts,
                "supported_domains": list(self.SUPPORTED_DOMAINS),
                "backend": "in_memory_fallback",
                "init_error": getattr(self, "_init_error", ""),
            }

        for domain in self.SUPPORTED_DOMAINS:
            try:
                count = int(self._collections[domain].count())
            except Exception:
                count = 0
            domain_counts[domain] = count
            total_chunks += count

        return {
            "persist_dir": self.persist_dir,
            "total_chunks": total_chunks,
            "collections": domain_counts,
            "supported_domains": list(self.SUPPORTED_DOMAINS),
        }

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _build_chunk_id(self, metadata: dict[str, Any], content: str) -> str:
        """Build a stable chunk id from source and chunk index."""
        source = str(
            metadata.get("source")
            or metadata.get("source_id")
            or metadata.get("url")
            or "unknown_source"
        ).strip()
        chunk_index = self._safe_int(metadata.get("chunk_index"), default=0)
        base = f"{source}::{chunk_index}"
        digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]

        if source:
            safe_source = hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]
            return f"{safe_source}_{chunk_index}_{digest}"

        content_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:24]
        return f"content_{chunk_index}_{content_digest}"

    def _normalize_domain(self, domain: Any) -> str:
        """Validate and normalize a domain value."""
        normalized = str(domain or "general").strip().lower()
        if normalized not in self.SUPPORTED_DOMAINS:
            return "general"
        return normalized

    def _sanitize_metadata(self, metadata: dict[str, Any] | None) -> dict[str, Any]:
        """Convert metadata values into JSON-serializable primitive values."""
        if not metadata:
            return {}

        sanitized: dict[str, Any] = {}
        for key, value in metadata.items():
            key_str = str(key)
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                sanitized[key_str] = value
            elif isinstance(value, Path):
                sanitized[key_str] = str(value)
            elif isinstance(value, (list, tuple, set)):
                sanitized[key_str] = [self._serialize_scalar(item) for item in value]
            elif isinstance(value, dict):
                sanitized[key_str] = {
                    str(sub_key): self._serialize_scalar(sub_value)
                    for sub_key, sub_value in value.items()
                }
            else:
                sanitized[key_str] = str(value)
        return sanitized

    def _serialize_scalar(self, value: Any) -> Any:
        """Serialize a scalar or nested value into a JSON-compatible representation."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, (list, tuple, set)):
            return [self._serialize_scalar(item) for item in value]
        if isinstance(value, dict):
            return {
                str(sub_key): self._serialize_scalar(sub_value)
                for sub_key, sub_value in value.items()
            }
        return str(value)

    def _build_where_filter(self, language: str | None = None) -> dict[str, Any] | None:
        """Build a Chroma metadata filter for optional language restriction."""
        normalized_language = str(language or "").strip().lower()
        if not normalized_language:
            return None
        return {"language": normalized_language}

    def _convert_query_result(self, result: dict[str, Any]) -> list[Document]:
        """Convert Chroma query results into LangChain documents."""
        documents = result.get("documents", [[]])
        metadatas = result.get("metadatas", [[]])
        distances = result.get("distances", [[]])

        if not documents:
            return []

        first_documents = documents[0] if documents and isinstance(documents[0], list) else []
        first_metadatas = metadatas[0] if metadatas and isinstance(metadatas[0], list) else []
        first_distances = distances[0] if distances and isinstance(distances[0], list) else []

        converted: list[Document] = []

        for index, page_content in enumerate(first_documents):
            if not page_content:
                continue
            metadata = dict(first_metadatas[index] or {}) if index < len(first_metadatas) else {}
            distance = first_distances[index] if index < len(first_distances) else None
            metadata["similarity_score"] = self._distance_to_similarity(distance)
            converted.append(Document(page_content=page_content, metadata=metadata))

        return converted

    def _distance_to_similarity(self, distance: Any) -> float:
        """Convert a Chroma distance value into a bounded similarity score."""
        numeric_distance = self._safe_float(distance, default=1.0)
        similarity = 1.0 / (1.0 + max(numeric_distance, 0.0))
        return round(similarity, 6)

    def _rank_and_limit(self, documents: list[Document], top_k: int) -> list[Document]:
        """Sort documents by similarity, deduplicate, and limit result count."""
        scored_items: list[tuple[float, Document]] = []
        for document in documents:
            score = self._safe_float(document.metadata.get("similarity_score"), default=0.0)
            scored_items.append((score, document))

        scored_items.sort(
            key=lambda item: (
                item[0],
                self._safe_int(item[1].metadata.get("chunk_index"), default=0) * -1,
            ),
            reverse=True,
        )

        deduplicated: list[Document] = []
        seen_ids: set[str] = set()

        for _, document in scored_items:
            chunk_id = str(document.metadata.get("chunk_id", "")).strip()
            if chunk_id and chunk_id in seen_ids:
                continue
            if chunk_id:
                seen_ids.add(chunk_id)
            deduplicated.append(document)
            if len(deduplicated) >= top_k:
                break

        return deduplicated

    def _tokenize(self, text: str) -> set[str]:
        """Tokenize text into lowercase alphanumeric terms."""
        normalized = "".join(
            character.lower() if character.isalnum() else " " for character in text or ""
        )
        return {token for token in normalized.split() if len(token) > 1}

    def _keyword_overlap_ratio(self, query_terms: set[str], text: str) -> float:
        """Compute a lightweight keyword overlap score between query and document."""
        if not query_terms:
            return 0.0
        document_terms = self._tokenize(text)
        if not document_terms:
            return 0.0
        overlap = len(query_terms.intersection(document_terms))
        return round(overlap / max(len(query_terms), 1), 6)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """Safely convert values to float."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _safe_int(self, value: Any, default: int = 0) -> int:
        """Safely convert values to int."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def get_sample_documents(self, limit: int = 100) -> list[Document]:
        """Get sample documents from all collections for question generation.
        
        Args:
            limit: Maximum number of documents to retrieve.
            
        Returns:
            List of sample Document objects from the vectorstore.
        """
        all_documents: list[Document] = []
        
        if self._use_fallback:
            # Fallback mode: get documents from fallback store
            for domain, items in self._fallback_store.items():
                for doc, _ in items[:limit]:
                    all_documents.append(doc)
                    if len(all_documents) >= limit:
                        return all_documents
            return all_documents
        
        # ChromaDB mode: get documents from each collection
        for domain, collection in self._collections.items():
            try:
                # Get all documents from this collection (no filtering)
                result = collection.get(include=["documents", "metadatas"])
                documents = result.get("documents", [])
                metadatas = result.get("metadatas", [])
                
                for doc_text, metadata in zip(documents, metadatas):
                    if doc_text and doc_text.strip():
                        all_documents.append(
                            Document(
                                page_content=doc_text,
                                metadata=dict(metadata or {})
                            )
                        )
                    if len(all_documents) >= limit:
                        return all_documents
            except Exception as e:
                # Skip this collection if there's an error
                continue
        
        return all_documents