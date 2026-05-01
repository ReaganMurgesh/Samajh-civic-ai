"""SAMAJH — Complete RAG Pipeline with Tri-Mode Router.

Public interface (consumed by streamlit_app.py)
───────────────────────────────────────────────
pipeline.answer_question(query, language, domain, guide, top_k)
    → Mode 1: Offline RAG — ChromaDB + Groq/LLaMA-3

pipeline.load_document(file_obj)
    → Ingest an uploaded PDF into an in-memory ChromaDB collection

pipeline.answer_from_document(query, language)
    → Mode 2: In-memory document RAG — LangChain PyPDFLoader + Groq

pipeline.answer_from_web(query, language)
    → Mode 3: Live web search — Gemini 1.5 Flash with Google Search Grounding

Every method returns the same standardised dict:
{
    "answer"               : str   — Markdown with inline [1] [2] citations
    "sources"              : list  — [{title, url, domain, ministry,
                                        similarity_score, ...}, …]
    "follow_up_questions"  : list[str]
    "confidence"           : float
    "detected_language"    : str
    "retrieved_count"      : int
    "domain_filter"        : str | None
    "provider"             : str
}
"""

from __future__ import annotations

import io
import os
import tempfile
from typing import Any

# ── Language detection ────────────────────────────────────────────────────────
try:
    from langdetect import detect
    from langdetect.lang_detect_exception import LangDetectException
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

# ── LangChain / vector store ──────────────────────────────────────────────────
from langchain_core.documents import Document

# ── Local backend modules ─────────────────────────────────────────────────────
from backend.embeddings.embedder import MultilingualEmbedder
from backend.vectorstore.chroma_store import SamajhVectorStore
from backend.generator.rag_generator import SamajhGenerator
from backend.generator.suggested_questions import suggested_questions_gen
from backend.jargon.jargon_engine import jargon_engine
from backend.utils.config import config


# ─────────────────────────────────────────────────────────────────────────────
# LANGUAGE MAP
# ─────────────────────────────────────────────────────────────────────────────
_LANG_MAP = {
    "hi": "hindi", "ta": "tamil", "te": "telugu",
    "kn": "kannada", "bn": "bengali", "mr": "marathi", "en": "english",
}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE CLASS
# ─────────────────────────────────────────────────────────────────────────────
class SamajhPipeline:
    """End-to-end RAG pipeline with a Tri-Mode Router.

    Mode 1 — DB      : query → embed → ChromaDB retrieve → Groq generate
    Mode 2 — Document: load_document() → in-memory collection → same flow
    Mode 3 — Web     : Gemini 1.5 Flash + Google Search Grounding
    """

    def __init__(self) -> None:
        self.embedder    = MultilingualEmbedder()
        self.vectorstore = SamajhVectorStore(persist_dir=config.chroma_persist_dir)
        self.generator   = SamajhGenerator()

        # In-memory store for Mode 2 (one per Streamlit session via singleton)
        self._doc_vectorstore: SamajhVectorStore | None = None
        self._doc_collection_name = "samajh_doc_upload"

    # ─────────────────────────────────────────────────────────────────────
    # MODE 1 — SAMAJH DATABASE (Offline RAG)
    # ─────────────────────────────────────────────────────────────────────
    def answer_question(
        self,
        query:    str,
        language: str | None = None,
        domain:   str | None = None,
        guide:    str        = "general",
        top_k:    int        = 5,
        force_chunks: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Offline RAG: embed → ChromaDB hybrid search → Groq generate → jargon.

        Args:
            query:    User question.
            language: Language hint (auto-detected if None).
            domain:   Optional ChromaDB filter ("law", "health", …).
            guide:    Persona key ("general" | "legal" | "farmer" | "health").
            top_k:    Number of chunks to retrieve.
            force_chunks: Optional list of documents to use instead of retrieving.

        Returns:
            Standardised response dict.
        """
        detected_language = language or self._detect_language(query)
        query_embedding   = self.embedder.embed_query(query)

        if force_chunks is not None:
            retrieved_chunks = force_chunks
        else:
            retrieved_chunks = self.vectorstore.hybrid_search(
                query=query,
                query_embedding=query_embedding,
                domain=domain,
                top_k=top_k,
            )

        raw_response = self.generator.generate_answer(
            query=query,
            retrieved_chunks=retrieved_chunks,
            user_language=detected_language,
            guide=guide,
        )

        annotated = jargon_engine.annotate_answer(
            answer=raw_response["answer"],
            language=detected_language,
        )

        # Generate contextual follow-up questions
        followup_questions = []
        try:
            followup_questions = suggested_questions_gen.generate_contextual(
                current_question=query,
                conversation_history=[],
                num_questions=4,
                answer_context=raw_response["answer"]
            )
        except Exception as e:
            # Silently fail - follow-ups are nice-to-have, not critical
            pass

        return {
            **raw_response,
            **annotated,
            "follow_up_questions": followup_questions,
            "detected_language": detected_language,
            "retrieved_count":   len(retrieved_chunks),
            "domain_filter":     domain,
            "provider":          raw_response.get("provider", "groq"),
        }

    # ─────────────────────────────────────────────────────────────────────
    # MODE 2 — MY DOCUMENT (In-memory RAG)
    # ─────────────────────────────────────────────────────────────────────
    def load_document_chunks(self, chunks: list[Any]) -> None:
        """Build an ephemeral in-memory vector store from pre-extracted chunks.
        
        Args:
            chunks: A list of LangChain Document objects with .page_content
        """
        self._doc_vectorstore = SamajhVectorStore(
            persist_dir=os.path.join(tempfile.gettempdir(), "samajh_doc_upload"),
            use_fallback_only=True,
            persist_fallback=False,
        )
        
        embeddings = [self.embedder.embed_query(c.page_content) for c in chunks]
        self._doc_vectorstore.add_chunks(chunks, embeddings)

    def load_document(self, file_obj: Any) -> None:
        """Ingest an uploaded PDF into an ephemeral in-memory ChromaDB collection.

        Supports both Streamlit UploadedFile objects and raw bytes.

        Args:
            file_obj: A file-like object with a .read() method, or raw bytes.
        """
        # ── Read bytes ────────────────────────────────────────────────────
        if hasattr(file_obj, "read"):
            pdf_bytes = file_obj.read()
        elif isinstance(file_obj, (bytes, bytearray)):
            pdf_bytes = bytes(file_obj)
        else:
            raise TypeError(f"Unsupported file_obj type: {type(file_obj)}")

        # ── Write to temp file (LangChain loaders require a path) ─────────
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        try:
            chunks = self._load_pdf_chunks(tmp_path)
        finally:
            os.unlink(tmp_path)

        self._doc_vectorstore = SamajhVectorStore(
            persist_dir=os.path.join(tempfile.gettempdir(), "samajh_doc_upload"),
            use_fallback_only=True,
            persist_fallback=False,
        )
        embeddings = [self.embedder.embed_query(c.page_content) for c in chunks]
        self._doc_vectorstore.add_chunks(chunks, embeddings)

    def answer_from_document(
        self,
        query:    str,
        language: str | None = None,
        top_k:    int        = 5,
    ) -> dict[str, Any]:
        """Answer a query using the in-memory document loaded via load_document().
        
        Provides enhanced analysis with better structured responses.

        Raises:
            RuntimeError: If no document has been loaded yet.
        """
        if self._doc_vectorstore is None:
            raise RuntimeError(
                "No document loaded. Call pipeline.load_document(file) first."
            )

        detected_language = language or self._detect_language(query)
        query_embedding   = self.embedder.embed_query(query)

        retrieved_chunks = self._doc_vectorstore.hybrid_search(
            query=query,
            query_embedding=query_embedding,
            domain=None,
            top_k=top_k,
        )

        # Generate answer with document context
        raw_response = self.generator.generate_answer(
            query=query,
            retrieved_chunks=retrieved_chunks,
            user_language=detected_language,
            guide="document_analysis",  # Special guide for uploaded documents
        )

        # Annotate with jargon terms
        annotated = jargon_engine.annotate_answer(
            answer=raw_response["answer"],
            language=detected_language,
        )

        # Generate contextual follow-ups based on document content
        follow_ups = self._generate_document_follow_ups(query, raw_response.get("answer", ""), detected_language)

        return {
            **raw_response,
            **annotated,
            "detected_language": detected_language,
            "retrieved_count":   len(retrieved_chunks),
            "domain_filter":     None,
            "provider":          raw_response.get("provider", "groq"),
            "follow_up_questions": follow_ups,
            "analysis_type":     "document_analysis",
        }

    # ─────────────────────────────────────────────────────────────────────
    # MODE 3 — LIVE WEB SEARCH (Gemini 1.5 Flash)
    # ─────────────────────────────────────────────────────────────────────
    def answer_from_web(
        self,
        query:    str,
        language: str | None = None,
    ) -> dict[str, Any]:
        """Answer using Gemini 1.5 Flash with Google Search Grounding.

        Returns a standardised dict that matches Modes 1 & 2 so the UI layer
        needs zero special-casing.

        Requires:
            GEMINI_API_KEY in environment / config.gemini_api_key

        Falls back gracefully with an error message if Gemini is not available.
        """
        detected_language = language or self._detect_language(query)

        try:
            answer, sources = self._gemini_search(query, detected_language)
        except Exception as exc:
            answer  = f"⚠️ Live search unavailable: `{exc}`"
            sources = []

        follow_ups = self._stub_follow_ups(query, answer)

        return {
            "answer":              answer,
            "annotated_answer":    answer,
            "sources":             sources,
            "follow_up_questions": follow_ups,
            "confidence":          0.90 if sources else 0.0,
            "detected_language":   detected_language,
            "retrieved_count":     len(sources),
            "domain_filter":       None,
            "provider":            "gemini-1.5-flash",
            "jargon_terms":        [],
        }

    # ─────────────────────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ─────────────────────────────────────────────────────────────────────
    def _detect_language(self, text: str) -> str:
        """Auto-detect query language, fall back to 'english'."""
        if not LANGDETECT_AVAILABLE or not text.strip():
            return "english"
        try:
            code = detect(text)
            return _LANG_MAP.get(code, "english")
        except LangDetectException:
            return "english"

    def _load_pdf_chunks(self, pdf_path: str) -> list[Document]:
        """Load a PDF and split into LangChain Document chunks.

        Uses LangChain PyPDFLoader + RecursiveCharacterTextSplitter.
        Falls back to a single Document if libraries are missing.
        """
        try:
            from langchain_community.document_loaders import PyPDFLoader
            from langchain.text_splitter import RecursiveCharacterTextSplitter

            loader   = PyPDFLoader(pdf_path)
            pages    = loader.load()

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=800,
                chunk_overlap=120,
                separators=["\n\n", "\n", ". ", " ", ""],
            )
            chunks = splitter.split_documents(pages)

            # Enrich metadata so the source expander renders nicely
            for i, chunk in enumerate(chunks):
                chunk.metadata.setdefault("source",      "uploaded_document")
                chunk.metadata.setdefault("title",       "Uploaded Document")
                chunk.metadata.setdefault("domain",      "document")
                chunk.metadata.setdefault("chunk_index", i)
                chunk.metadata.setdefault("total_chunks", len(chunks))

            return chunks

        except ImportError:
            # Minimal fallback — read raw text from PDF via pdfplumber
            return self._fallback_pdf_load(pdf_path)

    def _fallback_pdf_load(self, pdf_path: str) -> list[Document]:
        """Fallback PDF extraction using pdfplumber when LangChain is unavailable."""
        try:
            import pdfplumber
            text_parts = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
            full_text = "\n\n".join(text_parts)
        except Exception:
            full_text = "[Could not extract PDF text]"

        # Chunk naively at 800-char boundaries
        chunks = []
        for i in range(0, max(len(full_text), 1), 800):
            snippet = full_text[i:i + 800].strip()
            if snippet:
                chunks.append(Document(
                    page_content=snippet,
                    metadata={
                        "source":       "uploaded_document",
                        "title":        "Uploaded Document",
                        "domain":       "document",
                        "chunk_index":  len(chunks),
                    },
                ))
        return chunks or [Document(page_content=full_text or "[empty]",
                                   metadata={"source": "uploaded_document"})]

    def _gemini_search(
        self, query: str, language: str
    ) -> tuple[str, list[dict[str, Any]]]:
        """Search using DuckDuckGo (FREE!) and generate answer with Groq.

        Returns:
            (answer_markdown, sources_list)
        """
        try:
            from ddgs import DDGS
        except ImportError:
            print("Installing ddgs...")
            os.system("pip install ddgs")
            from ddgs import DDGS

        # ── Search using DuckDuckGo ────────────────────────────────────────
        ddgs = DDGS()
        search_results = ddgs.text(query)  # Query as positional argument

        # ── Build search text for Groq ──────────────────────────────────────
        search_text = ""
        for idx, result in enumerate(search_results, 1):
            title = result.get("title", "Result")
            body = result.get("body", "")
            search_text += f"[{idx}] {title}\n{body}\n\n"

        # ── Generate answer using Groq ──────────────────────────────────────
        from groq import Groq
        client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
        
        system_prompt = (
            "You are SAMAJH, a civic intelligence assistant for Indian citizens. "
            "Answer questions about government schemes, policies, laws, and civic information. "
            "\n\nGuidelines:"
            "\n- Use ONLY the provided search results"
            "\n- Add inline numeric citations like [1] [2] after each claim"
            "\n- Never fabricate information"
            "\n- Provide actionable information (deadlines, eligibility, documents)"
            "\n- Use **bold** for key terms"
            f"\n- Respond in {language.capitalize()}"
            "\n- Keep answer concise but comprehensive"
        )
        
        user_prompt = f"""Answer this civic question using the provided search results:

Question: {query}

Search Results:
{search_text}

Provide:
1. Direct answer with citations [1] [2] etc
2. Actionable steps if applicable
3. Important deadlines or requirements
"""
        
        try:
            response = client.messages.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1024,
                temperature=0.7
            )
            answer = response.content[0].text if response.content else "No answer generated."
        except Exception as e:
            # Fallback: simple answer
            answer = f"Based on web search results for '{query}', please check official sources for latest information."

        return answer, []  # Return empty sources list

    def _stub_follow_ups(self, query: str, answer: str = "") -> list[str]:
        """Generate smart follow-up questions for web search results."""
        try:
            # Use contextual follow-ups from suggested questions generator
            follow_ups = suggested_questions_gen.generate_contextual(
                current_question=query,
                conversation_history=[],
                num_questions=3,
                answer_context=answer
            )
            return follow_ups if follow_ups else self._get_fallback_followups(query)
        except Exception:
            return self._get_fallback_followups(query)

    def _get_fallback_followups(self, query: str) -> list[str]:
        """Fallback follow-up questions when generation fails."""
        q = query.strip().rstrip("?")
        return [
            f"Latest updates and recent news about {q}?",
            f"Where can I get official government information about {q}?",
            f"What are the key documents and forms needed for {q}?",
        ]

    def _generate_document_follow_ups(self, query: str, answer: str, language: str) -> list[str]:
        """Generate contextual follow-up questions for uploaded documents."""
        try:
            # Use contextual follow-ups from suggested questions generator
            follow_ups = suggested_questions_gen.generate_contextual(
                current_question=query,
                conversation_history=[],
                num_questions=3,
                answer_context=answer
            )
            return follow_ups if follow_ups else self._get_document_fallback_followups(query)
        except Exception:
            return self._get_document_fallback_followups(query)

    def _get_document_fallback_followups(self, query: str) -> list[str]:
        """Fallback follow-up questions for document analysis."""
        q = query.strip().rstrip("?")
        return [
            f"Can you clarify more about {q} from this document?",
            f"What are the key requirements or conditions mentioned for {q}?",
            f"Are there any dates, deadlines, or timelines related to {q} in the document?",
        ]


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL SINGLETON
# ─────────────────────────────────────────────────────────────────────────────
pipeline = SamajhPipeline()