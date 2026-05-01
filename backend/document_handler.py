"""
SAMAJH Document Upload Handler
Handles temporary in-memory RAG for user-uploaded documents.
Provides secure, ephemeral processing without storing user data.
"""

import tempfile
import os
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from langchain_core.documents import Document


class DocumentUploadHandler:
    """Handles uploaded documents with in-memory processing."""
    
    ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.md', '.png', '.jpg', '.jpeg'}
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    
    def __init__(self):
        """Initialize the document handler."""
        self.current_document = None
        self.current_chunks = []
        self.current_filename = None
        self.chunk_size = 1000
        self.chunk_overlap = 200
    
    def validate_upload(self, file_path: str) -> Tuple[bool, str]:
        """
        Validate uploaded file.
        
        Returns:
            (is_valid, message)
        """
        if not os.path.exists(file_path):
            return False, "❌ File not found"
        
        # Check extension
        ext = Path(file_path).suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            return False, f"❌ File type not allowed. Use: {', '.join(self.ALLOWED_EXTENSIONS)}"
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > self.MAX_FILE_SIZE:
            return False, f"❌ File too large ({file_size / 1024 / 1024:.1f}MB). Max: 50MB"
        
        if file_size == 0:
            return False, "❌ File is empty"
        
        return True, f"✅ Valid file: {Path(file_path).name}"
    
    def load_pdf(self, file_path: str) -> Tuple[bool, str, str]:
        """
        Load and extract text from PDF using pdfplumber, falling back to pypdf.
        
        Returns:
            (success, message, text)
        """
        text = ""
        num_pages = 0
        
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                num_pages = len(pdf.pages)
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n--- Page {i + 1} ---\n"
                        text += page_text
            
            if not text.strip():
                raise ValueError("pdfplumber extracted empty text")
                
            return True, f"✅ Extracted {num_pages} pages from PDF", text
        except Exception as e:
            # If pdfplumber throws (e.g. malformed or corrupted), fallback to pypdf
            try:
                import pypdf
                text = ""
                with open(file_path, 'rb') as file:
                    reader = pypdf.PdfReader(file)
                    num_pages = len(reader.pages)
                    
                    for page_num in range(num_pages):
                        page = reader.pages[page_num]
                        text += f"\n--- Page {page_num + 1} ---\n"
                        text += page.extract_text() or ""
                
                return True, f"✅ Extracted {num_pages} pages from PDF (fallback)", text
            
            except Exception as fallback_e:
                try:
                    from pdfminer.high_level import extract_text
                    text = extract_text(file_path)
                    if not text.strip():
                        return False, "❌ Extracted text is empty", ""
                    return True, "✅ Extracted text from PDF (using pdfminer fallback)", text
                except Exception as final_e:
                    return False, f"❌ Error reading PDF: {str(e)} | {str(fallback_e)} | {str(final_e)}", ""
    
    def load_text(self, file_path: str) -> Tuple[bool, str, str]:
        """Load text from .txt or .md file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                text = file.read()
            return True, f"✅ Loaded text file", text
        except Exception as e:
            return False, f"❌ Error reading file: {str(e)}", ""
    
    def load_image(self, file_path: str) -> Tuple[bool, str, str]:
        """
        Load and OCR image (requires pytesseract and tesseract-ocr).
        
        Returns:
            (success, message, extracted_text)
        """
        try:
            from PIL import Image
            import pytesseract
            
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img)
            
            if not text.strip():
                return False, "⚠️ Could not extract text from image (no text detected)", ""
            
            return True, f"✅ Extracted text from image", text
        
        except ImportError:
            return False, "❌ Image OCR requires: pip install pytesseract pillow", ""
        except Exception as e:
            return False, f"❌ Error processing image: {str(e)}", ""
    
    def process_document(
        self,
        file_path: str,
        filename: str
    ) -> Dict[str, Any]:
        """
        Process uploaded document - load, chunk, and prepare for querying.
        
        Args:
            file_path: Path to temp file
            filename: Original filename
            
        Returns:
            Status dict with chunks and metadata
        """
        # Validate
        is_valid, msg = self.validate_upload(file_path)
        if not is_valid:
            return {"success": False, "error": msg, "chunks": []}
        
        # Load based on file type
        ext = Path(file_path).suffix.lower()
        
        if ext == '.pdf':
            success, load_msg, text = self.load_pdf(file_path)
        elif ext in {'.txt', '.md'}:
            success, load_msg, text = self.load_text(file_path)
        elif ext in {'.png', '.jpg', '.jpeg'}:
            success, load_msg, text = self.load_image(file_path)
        else:
            return {
                "success": False,
                "error": "Unsupported file type",
                "chunks": []
            }
        
        if not success:
            return {"success": False, "error": load_msg, "chunks": []}

        # Store base metadata in memory before chunking so chunk metadata is correct
        self.current_filename = filename
        self.current_document = text
        
        # Chunk the document
        chunks = self._chunk_text(text)
        
        # Store in memory
        self.current_chunks = chunks
        
        return {
            "success": True,
            "filename": filename,
            "load_message": load_msg,
            "num_chunks": len(chunks),
            "text_length": len(text),
            "chunks": chunks,
            "summary_message": f"📚 Ready to analyze {filename} ({len(chunks)} chunks, {len(text)} characters)"
        }
    
    def _chunk_text(self, text: str) -> List[Document]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Full document text
            
        Returns:
            List of Document objects (chunks)
        """
        chunks = []
        words = text.split()
        current_chunk = []
        current_length = 0

        source_id = f"uploaded_document::{self.current_filename or 'unknown'}"
        
        for word in words:
            current_chunk.append(word)
            current_length += len(word) + 1
            
            if current_length >= self.chunk_size:
                # Create chunk
                chunk_text = " ".join(current_chunk)
                chunks.append(Document(
                    page_content=chunk_text,
                    metadata={
                        "source": source_id,
                        "filename": self.current_filename,
                        "chunk_index": len(chunks),
                        "domain": "general",
                    }
                ))
                
                # Overlap - keep last 200 chars worth of words
                overlap_words = int(self.chunk_overlap / 6)  # Rough avg word size
                current_chunk = current_chunk[-overlap_words:] if len(current_chunk) > overlap_words else []
                current_length = sum(len(w) + 1 for w in current_chunk)
        
        # Add final chunk
        if current_chunk:
            chunks.append(Document(
                page_content=" ".join(current_chunk),
                metadata={
                    "source": source_id,
                    "filename": self.current_filename,
                    "chunk_index": len(chunks),
                    "domain": "general",
                }
            ))

        total = len(chunks)
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
            chunk.metadata["total_chunks"] = total
        
        return chunks
    
    def retrieve_relevant_chunks(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Document]:
        """
        Retrieve chunks most relevant to query.
        For simplicity, uses keyword matching. Can be enhanced with embeddings.
        
        Args:
            query: User's question
            top_k: Number of chunks to retrieve
            
        Returns:
            Top K relevant chunks
        """
        if not self.current_chunks:
            return []
        
        # Simple keyword matching (can be enhanced with embeddings)
        query_words = set(query.lower().split())
        
        scored_chunks = []
        for chunk in self.current_chunks:
            chunk_words = set(chunk.page_content.lower().split())
            # Score based on keyword overlap
            overlap = len(query_words & chunk_words)
            if overlap > 0:
                scored_chunks.append((overlap, chunk))
        
        # Sort by score and return top K
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored_chunks[:top_k]]
    
    def get_document_summary(self) -> Dict[str, Any]:
        """Get summary of current document."""
        if not self.current_document:
            return {
                "is_loaded": False,
                "filename": None,
                "chunks": 0,
                "length": 0
            }
        
        return {
            "is_loaded": True,
            "filename": self.current_filename,
            "num_chunks": len(self.current_chunks),
            "text_length": len(self.current_document),
            "approx_pages": max(1, len(self.current_document) // 3000),
            "first_100_chars": self.current_document[:100] + "..."
        }
    
    def clear_document(self) -> None:
        """Clear current document from memory (for privacy)."""
        self.current_document = None
        self.current_chunks = []
        self.current_filename = None
    
    def export_chunks(self) -> List[Dict[str, Any]]:
        """Export chunks as serializable format."""
        return [
            {
                "content": chunk.page_content,
                "metadata": chunk.metadata
            }
            for chunk in self.current_chunks
        ]


# ============================================
# Session State Manager for Streamlit
# ============================================

class StreamlitDocumentSession:
    """Manages document upload session in Streamlit."""
    
    def __init__(self, session_state):
        """Initialize with Streamlit session state."""
        self.session_state = session_state
    
    def initialize(self):
        """Initialize session state variables."""
        if 'document_handler' not in self.session_state:
            self.session_state.document_handler = DocumentUploadHandler()
        
        if 'uploaded_file_path' not in self.session_state:
            self.session_state.uploaded_file_path = None
        
        if 'uploaded_file_name' not in self.session_state:
            self.session_state.uploaded_file_name = None
        
        if 'document_processed' not in self.session_state:
            self.session_state.document_processed = False
    
    def process_upload(self, uploaded_file) -> Dict[str, Any]:
        """Process uploaded file from Streamlit."""
        if uploaded_file is None:
            return {"success": False, "error": "No file uploaded"}
        
        try:
            # Save to temp file
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, uploaded_file.name)
            
            with open(temp_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            
            # Process
            handler = self.session_state.document_handler
            result = handler.process_document(temp_path, uploaded_file.name)
            
            if result["success"]:
                self.session_state.uploaded_file_path = temp_path
                self.session_state.uploaded_file_name = uploaded_file.name
                self.session_state.document_processed = True
            
            return result
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Error processing upload: {str(e)}",
                "chunks": []
            }
    
    def clear_upload(self):
        """Clear uploaded document."""
        handler = self.session_state.document_handler
        handler.clear_document()
        
        # Clean up temp file
        if self.session_state.uploaded_file_path:
            try:
                os.remove(self.session_state.uploaded_file_path)
            except:
                pass
        
        self.session_state.uploaded_file_path = None
        self.session_state.uploaded_file_name = None
        self.session_state.document_processed = False
