# SAMAJH RAG-based Civic QA System — Changelog

## Latest Work Session (May 2026)

### ✅ Completed Enhancements

#### 1. **Document Upload Mode — Follow-Up Questions UI** 
- **File**: `frontend/streamlit_omni_app_v2.py`
- **What Changed**: Added contextual follow-up question buttons in document analysis mode (parity with official DB mode).
- **Implementation**:
  - Display follow-ups in a 2-column grid below each answer.
  - Support queued follow-ups via `execute_doc_query` session state (allows form-less processing).
  - Show document sources expander with citation info.
  - Proper key hashing to avoid Streamlit button key collision warnings.
- **User Impact**: Users can now seamlessly iterate through document-related questions without manual typing.

#### 2. **Document Analysis Vectorstore — Ephemeral In-Memory Mode**
- **File**: `backend/vectorstore/chroma_store.py`
- **What Changed**: Added `use_fallback_only` and `persist_fallback` parameters for document upload privacy.
- **Why**: Uploaded documents are indexed into an ephemeral, non-persistent in-memory vectorstore to avoid writing user data to disk.
- **Result**: Document uploads are analyzed in real-time without creating persistent storage artifacts.

#### 3. **Document Indexing Pipeline Integration**
- **File**: `backend/pipeline.py`
- **What Changed**:
  - Added `load_document_chunks()` method to accept pre-extracted document chunks and index them.
  - Fixed `answer_from_document()` to properly retrieve and use follow-up generation.
  - Enhanced document follow-up generation to be contextual (grounded in actual answers).
- **Result**: Full end-to-end document RAG: upload → chunk → index → query → answer with follow-ups.

#### 4. **Robust PDF Extraction with Multi-Level Fallback**
- **File**: `backend/document_handler.py`
- **What Changed**:
  - Primary: `pdfplumber` (0.11.8) for fast, accurate text extraction.
  - Secondary: `pypdf` for fallback if pdfplumber fails.
  - Tertiary: `pdfminer.six` (20251107) as final fallback.
  - Added `pypdfium2` (5.7.1) for additional robustness.
- **Coverage**: Handles corrupted PDFs, encrypted PDFs, image-only PDFs gracefully.

#### 5. **Chunk Metadata Uniqueness Fix**
- **File**: `backend/document_handler.py`
- **What Changed**: 
  - Set `source` metadata to include filename for uniqueness.
  - Added `chunk_index` and `total_chunks` for tracking.
  - Prevents ChromaDB from collapsing similar chunks across multiple documents.
- **Result**: Accurate retrieval when multiple documents are uploaded (no deduplication issues).

#### 6. **Enhanced Suggested Questions System**
- **File**: `backend/generator/suggested_questions.py`
- **What Changed**:
  - Added `answer_context` parameter to `generate_contextual()`.
  - Follow-ups are now grounded in the actual answer text.
  - Improved fallback questions for document analysis mode.
- **Result**: Better, more relevant follow-up suggestions tailored to document content.

#### 7. **Unit Tests Passing**
- **File**: `tests/test_pipeline.py` & `tests/test_rag_quality.py`
- **Result**: `pytest -q` → **8 passed** ✅
- **Coverage**: Document loading, Q&A, relevance gating, fallback generation.

---

## Technical Achievements

### Core Features Validated
- ✅ **Official DB Mode**: Query 1,403+ government documents with multi-language support.
- ✅ **Document Upload Mode**: Upload & analyze user files with proper RAG indexing.
- ✅ **Web Search Mode**: Real-time Gemini 1.5 Flash with Google Search grounding.
- ✅ **Follow-Up Questions**: Contextual, answer-grounded suggestions across all modes.
- ✅ **Multi-Language**: English, Hindi, Mixed language detection & response generation.
- ✅ **Jargon Annotation**: Automatic legal/domain terminology explanation.

### Infrastructure
- **LLM**: Groq `llama-3.3-70b-versatile` (fast, free API).
- **Vectorstore**: ChromaDB with fallback in-memory storage.
- **UI**: Streamlit with custom CSS styling.
- **Frontend**: Document upload, chat history, source citation, guide personas.

### Known Observations
- **Browser Warning**: "Skipped STREAMLIT_MIME_TYPE because it is not a valid MIME type" 
  - **Analysis**: Not in repo code; likely Streamlit internal or browser extension artifact.
  - **Impact**: Harmless—does not affect functionality.
  - **Recommendation**: Monitor in production; no action needed for v1.

---

## File Structure & Key Modules

```
backend/
  ├── pipeline.py              # Orchestrates all three modes (Official, Document, Web)
  ├── document_handler.py      # Uploads & PDF extraction (3-level fallback)
  ├── embeddings/embedder.py   # Multilingual embedding (sentence-transformers)
  ├── vectorstore/chroma_store.py  # ChromaDB + ephemeral fallback
  ├── generator/
  │   ├── rag_generator.py      # Answer generation with relevance gating
  │   ├── suggested_questions.py # Context-aware follow-up generation
  │   ├── hallucination_guard.py # Safety checks
  │   └── guide_personas.py      # Domain-specific prompt tuning
  └── retriever/enhanced_retriever.py  # Hybrid search (semantic + BM25)

frontend/
  └── streamlit_omni_app_v2.py  # Main UI with 3 modes + chat history

tests/
  ├── test_pipeline.py           # End-to-end pipeline tests
  └── test_rag_quality.py        # Relevance & generation quality checks

data/
  ├── raw/                       # User uploads (ephemeral)
  ├── processed/                 # Document metadata
  └── jargon_dict/               # Domain terminology
```

---

## Recent Debugging & Problem Solving

### Issue 1: PDF Parsing Failures
- **Symptom**: "❌ Error reading PDF: EOF marker not found"
- **Root Cause**: `pypdf` alone unreliable for varied PDF formats.
- **Solution**: Switched to `pdfplumber` (primary) with `pypdf` + `pdfminer.six` fallback.
- **Status**: ✅ Fixed — tested with `mini_doc.txt` and real government PDFs.

### Issue 2: Document Mode No Answers
- **Symptom**: Upload showed "Ready to analyze" but no answer returned.
- **Root Cause**: Document chunks not indexed into `_doc_vectorstore`.
- **Solution**: Integrated `pipeline.load_document_chunks()` into Streamlit upload handler.
- **Status**: ✅ Fixed — document Q&A now works end-to-end.

### Issue 3: Vectorstore API Mismatch
- **Symptom**: `TypeError: __init__() got an unexpected keyword argument 'collection_name'`
- **Root Cause**: Using deprecated ChromaDB API.
- **Solution**: Updated to `add_chunks()` and proper metadata handling.
- **Status**: ✅ Fixed — vectorstore operations standardized.

### Issue 4: Missing Follow-Up Buttons in Doc Mode
- **Symptom**: Official DB mode had follow-ups; document mode didn't.
- **Root Cause**: `answer_from_document()` had follow-ups but UI didn't render them.
- **Solution**: Enhanced UI to display follow-ups with clickable buttons + queued execution.
- **Status**: ✅ Fixed — doc mode now has full parity with official mode.

---

## Next Steps (Future Work)

### High Priority
1. **MIME Type Warning Investigation** — Document root cause if impacting user experience.
2. **Performance Tuning** — Optimize embedding model for faster response times.
3. **Analytics Dashboard** — Track user queries, modes used, document types.

### Medium Priority
1. **Fine-Tuning Groq Prompts** — Domain-specific instruction tuning for better answers.
2. **Document Upload Size Limits** — Graceful handling of large files (>200MB).
3. **Conversation Export** — Allow users to save/download chat history.

### Long-Term
1. **Mobile UI** — Responsive design for mobile citizens.
2. **Offline Mode** — Local vectorstore fallback for connectivity issues.
3. **User Authentication** — Track conversation history per user.

---

## Testing & Validation Commands

```bash
# Run unit tests
pytest -q

# Start Streamlit UI
powershell -ExecutionPolicy Bypass -File scripts/restart_streamlit.ps1

# Test document upload
# 1. Navigate to http://localhost:8501
# 2. Select "📄 Upload Document" mode
# 3. Upload data/mini_doc.txt (or your own PDF/TXT)
# 4. Ask a question (e.g., "What are the anti-fraud guidelines?")
# 5. Verify answer appears with sources and follow-up buttons
# 6. Click a follow-up button and verify it executes

# Check environment
Get-ChildItem Env:STREAMLIT*
```

---

## Commits & Version Control

- **Initial Commit**: Snapshot of fully integrated SAMAJH system (52 files, 11,421 insertions).
- **Branch**: `main`
- **Remote**: `https://github.com/ReaganMurgesh/RAG-based-system.git`

---

## Credits & Acknowledgments

**SAMAJH** (समझ) = "Understand" in Hindi

A civic information RAG system designed to empower Indian citizens with instant, verified, multi-language access to government schemes, policies, and procedures—all powered by open-source tech (Groq, ChromaDB, Streamlit).

**Made with ❤️ for transparent, accessible governance.**
