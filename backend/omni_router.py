"""
SAMAJH Omni-Platform Router
Intelligently routes queries to the appropriate mode:
- Mode 1: Official Database (ChromaDB + Groq)
- Mode 2: Document Upload (In-Memory RAG)
- Mode 3: Live Web Search (Gemini)
"""

from typing import Dict, List, Any, Optional
import tempfile
import os
from pathlib import Path


class SamajhOmniRouter:
    """Routes queries to the appropriate mode based on user selection."""
    
    MODE_OFFICIAL_DB = "Official Database"
    MODE_UPLOAD_DOC = "Upload My Document"
    MODE_LIVE_WEB = "Live Web Search"
    
    ALL_MODES = [MODE_OFFICIAL_DB, MODE_UPLOAD_DOC, MODE_LIVE_WEB]
    
    def __init__(self):
        """Initialize the router with mode configurations."""
        self.current_mode = self.MODE_OFFICIAL_DB
        self.temp_doc_vectors = None  # For Mode 2
        self.uploaded_filename = None  # For Mode 2
        
        # Mode configurations for UI display
        self.mode_config = {
            self.MODE_OFFICIAL_DB: {
                "emoji": "🏛️",
                "title": "SAMAJH Official Database",
                "description": "Official government documents (Laws, Policies, Schemes)",
                "source_color": "#6366f1",  # Indigo
                "icon": "📚",
            },
            self.MODE_UPLOAD_DOC: {
                "emoji": "📄",
                "title": "Upload My Document",
                "description": "Analyze your private documents (Bank notices, contracts, etc.)",
                "source_color": "#f59e0b",  # Amber
                "icon": "📋",
            },
            self.MODE_LIVE_WEB: {
                "emoji": "🌐",
                "title": "Live Web Search",
                "description": "Latest news & announcements (Real-time government updates)",
                "source_color": "#10b981",  # Green
                "icon": "🔍",
            }
        }
    
    def set_mode(self, mode: str) -> None:
        """Set the current query mode."""
        if mode not in self.ALL_MODES:
            raise ValueError(f"Invalid mode. Must be one of: {self.ALL_MODES}")
        self.current_mode = mode
    
    def get_mode(self) -> str:
        """Get the current mode."""
        return self.current_mode
    
    def get_mode_config(self, mode: Optional[str] = None) -> Dict[str, Any]:
        """Get configuration for a mode."""
        m = mode or self.current_mode
        return self.mode_config.get(m, {})
    
    def set_uploaded_document(self, file_path: str, filename: str) -> Dict[str, Any]:
        """
        Store uploaded document info for Mode 2.
        
        Args:
            file_path: Path to temporary file
            filename: Original filename
            
        Returns:
            Status dict with success flag and metadata
        """
        if not os.path.exists(file_path):
            return {"success": False, "error": "File not found"}
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Store info
        self.uploaded_filename = filename
        self.temp_doc_path = file_path
        
        return {
            "success": True,
            "filename": filename,
            "file_size": file_size,
            "path": file_path,
            "message": f"✅ Ready to analyze: {filename}"
        }
    
    def clear_uploaded_document(self) -> None:
        """Clear the uploaded document from memory."""
        if self.temp_doc_path and os.path.exists(self.temp_doc_path):
            try:
                os.remove(self.temp_doc_path)
            except:
                pass  # Cleanup may fail, but that's okay
        
        self.temp_doc_path = None
        self.uploaded_filename = None
        self.temp_doc_vectors = None
    
    def route_query(
        self,
        query: str,
        mode: Optional[str] = None,
        uploaded_doc_vectors: Optional[List] = None
    ) -> Dict[str, Any]:
        """
        Route a query to the appropriate handler.
        
        Args:
            query: User's question
            mode: Optional mode override
            uploaded_doc_vectors: Retrieved chunks from uploaded doc
            
        Returns:
            Routing info with handler details
        """
        active_mode = mode or self.current_mode
        
        routing_info = {
            "mode": active_mode,
            "query": query,
            "config": self.get_mode_config(active_mode),
            "handler": self._get_handler(active_mode),
            "requires_upload": active_mode == self.MODE_UPLOAD_DOC,
            "has_upload": self.uploaded_filename is not None if active_mode == self.MODE_UPLOAD_DOC else True,
        }
        
        # Warn if upload document mode is selected but no doc uploaded
        if active_mode == self.MODE_UPLOAD_DOC and not self.uploaded_filename:
            routing_info["warning"] = "⚠️ Please upload a document first"
        
        return routing_info
    
    def _get_handler(self, mode: str) -> str:
        """Get the handler function name for a mode."""
        handlers = {
            self.MODE_OFFICIAL_DB: "generate_from_chromadb",
            self.MODE_UPLOAD_DOC: "generate_from_uploaded_doc",
            self.MODE_LIVE_WEB: "generate_from_live_web",
        }
        return handlers.get(mode, "generate_from_chromadb")
    
    def get_all_modes_info(self) -> List[Dict[str, Any]]:
        """Get info about all available modes."""
        return [
            {
                "mode": mode,
                **self.mode_config[mode]
            }
            for mode in self.ALL_MODES
        ]


# ============================================
# Backend Router - Query Handler Dispatcher
# ============================================

class QueryDispatcher:
    """Dispatches queries to the appropriate backend based on mode."""
    
    def __init__(self, router: SamajhOmniRouter):
        """Initialize dispatcher with router."""
        self.router = router
    
    async def dispatch(
        self,
        query: str,
        mode: str,
        language: str = "english",
        guide: str = "general",
        uploaded_chunks: Optional[List] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Main dispatcher - routes to appropriate handler.
        
        Args:
            query: User's question
            mode: Which mode to use
            language: Response language
            guide: Guide persona (general, legal, farmer, health)
            uploaded_chunks: Retrieved chunks from uploaded document
            
        Returns:
            Complete response with answer, sources, metadata
        """
        
        # Validate mode
        routing_info = self.router.route_query(query, mode)
        
        if not routing_info["has_upload"] and mode == SamajhOmniRouter.MODE_UPLOAD_DOC:
            return {
                "error": "❌ Please upload a document first",
                "mode": mode,
                "answer": "I can only help with Mode 2 if you upload a document. Please upload a PDF, image, or text file."
            }
        
        # Route to appropriate handler
        if mode == SamajhOmniRouter.MODE_OFFICIAL_DB:
            return await self._handle_official_db(query, language, guide, **kwargs)
        
        elif mode == SamajhOmniRouter.MODE_UPLOAD_DOC:
            return await self._handle_upload_doc(query, language, guide, uploaded_chunks, **kwargs)
        
        elif mode == SamajhOmniRouter.MODE_LIVE_WEB:
            return await self._handle_live_web(query, language, guide, **kwargs)
        
        else:
            return {
                "error": "Unknown mode",
                "answer": "Invalid mode selected. Please choose from Official Database, Upload Document, or Live Web."
            }
    
    async def _handle_official_db(
        self,
        query: str,
        language: str,
        guide: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Handle Mode 1: Official Database queries."""
        # This will use the existing RAG pipeline
        from backend.pipeline import RAGPipeline
        
        pipeline = RAGPipeline()
        response = pipeline.answer_question(
            query=query,
            language=language,
            guide=guide
        )
        
        # Enhance response with mode info
        response["mode"] = SamajhOmniRouter.MODE_OFFICIAL_DB
        response["source_type"] = "🏛️ Official Government Database"
        response["source_color"] = "#6366f1"
        
        return response
    
    async def _handle_upload_doc(
        self,
        query: str,
        language: str,
        guide: str,
        uploaded_chunks: Optional[List],
        **kwargs
    ) -> Dict[str, Any]:
        """Handle Mode 2: Upload Document queries."""
        from backend.generator.rag_generator import SamajhGenerator
        from langchain_core.documents import Document
        
        if not uploaded_chunks:
            return {
                "error": "No chunks retrieved from document",
                "answer": "Could not find relevant content in your document for this question."
            }
        
        # Convert chunks to Document objects if needed
        docs = []
        for chunk in uploaded_chunks:
            if isinstance(chunk, Document):
                docs.append(chunk)
            else:
                docs.append(Document(page_content=str(chunk)))
        
        # Generate answer using the uploaded document only
        generator = SamajhGenerator()
        response = generator.generate_answer(
            query=query,
            retrieved_chunks=docs,
            user_language=language,
            guide=guide
        )
        
        # Enhance response with mode info
        response["mode"] = SamajhOmniRouter.MODE_UPLOAD_DOC
        response["source_type"] = "📄 Your Uploaded Document"
        response["source_color"] = "#f59e0b"
        response["warning"] = "⚠️ This analysis is based only on your uploaded document, not government databases."
        
        return response
    
    async def _handle_live_web(
        self,
        query: str,
        language: str,
        guide: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Handle Mode 3: Live Web Search queries."""
        # This will use Gemini API with Google Search
        try:
            import google.generativeai as genai
            from backend.utils.config import config
            
            if not config.gemini_api_key:
                return {
                    "error": "Gemini API not configured",
                    "answer": "Live Web Search requires Gemini API key. Please add it to .env file."
                }
            
            genai.configure(api_key=config.gemini_api_key)
            
            # Create system prompt for live web search
            system_prompt = f"""You are Samajh, a civic information assistant providing live information.
Your guide persona: {guide}
Response language: {language}

Search the web for:
1. Latest government announcements and schemes
2. Recent policy changes
3. Current event-related civic information

IMPORTANT:
- Cite the exact URLs you found information from
- Prioritize .gov.in, .nic.in, and official Indian sources
- For each source, show the URL clearly
- Add timestamps if available
- Focus on accuracy - use official sources only

Format your response as:
**Answer**: [Your answer]
**Sources Found**:
- [Title]: [URL]
- [Title]: [URL]
"""
            
            # Query Gemini with search enabled
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Note: Google Search integration requires proper setup
            # For now, use standard generation with instruction to search
            response_text = model.generate_content(
                f"{system_prompt}\n\nQuestion: {query}"
            )
            
            return {
                "mode": SamajhOmniRouter.MODE_LIVE_WEB,
                "answer": response_text.text if response_text else "No response generated",
                "source_type": "🌐 Live Web Search",
                "source_color": "#10b981",
                "sources": [],  # Will be extracted from response
                "confidence": 0.75,  # Web search has moderate confidence
                "timestamp": str(Path.cwd())  # Placeholder for actual search timestamp
            }
        
        except ImportError:
            return {
                "error": "Gemini API not available",
                "answer": "Live Web Search requires the 'google-generativeai' library. Install with: pip install google-generativeai"
            }
        except Exception as e:
            return {
                "error": str(e),
                "answer": f"Error during live web search: {str(e)}"
            }


# ============================================
# Initialization Helper
# ============================================

def create_omni_router() -> SamajhOmniRouter:
    """Create and initialize the OmniRouter."""
    return SamajhOmniRouter()


def create_dispatcher(router: SamajhOmniRouter) -> QueryDispatcher:
    """Create and initialize the QueryDispatcher."""
    return QueryDispatcher(router)
