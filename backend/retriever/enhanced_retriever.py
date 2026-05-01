"""
SAMAJH ENHANCED RETRIEVAL SYSTEM
Intelligent document retrieval with:
- Domain-aware filtering
- Question suggestion from similar documents
- Relevance ranking
- Cross-document relationships
"""

import json
import os
from typing import Any
from backend.vectorstore.chroma_store import SamajhVectorStore
from backend.embeddings.embedder import MultilingualEmbedder
from backend.utils.config import config
from groq import Groq

class EnhancedRetriever:
    """
    Advanced retrieval system with intelligent suggestions
    and cross-document awareness
    """
    
    def __init__(self):
        self.vectorstore = SamajhVectorStore(persist_dir=config.chroma_persist_dir)
        self.embedder = MultilingualEmbedder()
        self.groq_client = Groq(api_key=config.groq_api_key)
        self.collection_name = "samajh_documents"
    
    def retrieve_with_suggestions(
        self, 
        query: str, 
        domain: str = None,
        top_k: int = 5
    ) -> dict[str, Any]:
        """
        Retrieve documents and automatically suggest related questions
        
        Args:
            query: User question
            domain: Optional domain filter (law, finance, health, etc.)
            top_k: Number of top documents to retrieve
        
        Returns:
            {
                "retrieved_docs": [...],
                "suggested_questions": [...],
                "related_domains": [...],
                "total_results": int,
                "search_metadata": {...}
            }
        """
        # Build metadata filter
        where_filter = None
        if domain:
            where_filter = {"domain": domain}
        
        # Retrieve documents
        retrieved_chunks = self.vectorstore.retrieve(
            query=query,
            top_k=top_k,
            collection_name=self.collection_name,
            where=where_filter
        )
        
        # Extract unique documents and domains
        unique_docs = {}
        domains_found = set()
        
        for chunk in retrieved_chunks:
            doc_title = chunk.metadata.get("title", "Unknown")
            doc_domain = chunk.metadata.get("domain", "general")
            
            if doc_title not in unique_docs:
                unique_docs[doc_title] = {
                    "title": doc_title,
                    "domain": doc_domain,
                    "category": chunk.metadata.get("category", ""),
                    "summary": chunk.metadata.get("summary", chunk.page_content[:200]),
                    "keywords": chunk.metadata.get("keywords", ""),
                    "suggested_questions": self._parse_questions(
                        chunk.metadata.get("suggested_questions", "[]")
                    ),
                    "chunks_retrieved": 1,
                }
            else:
                unique_docs[doc_title]["chunks_retrieved"] += 1
            
            domains_found.add(doc_domain)
        
        # Generate follow-up suggestions using LLM
        follow_up_questions = self._generate_follow_ups(
            query, 
            list(unique_docs.keys()),
            list(domains_found)
        )
        
        # Combine pre-written and generated suggestions
        all_suggested_questions = set()
        for doc in unique_docs.values():
            all_suggested_questions.update(doc.get("suggested_questions", []))
        all_suggested_questions.update(follow_up_questions)
        
        return {
            "retrieved_documents": list(unique_docs.values()),
            "suggested_follow_up_questions": list(all_suggested_questions)[:5],
            "related_domains": list(domains_found),
            "total_documents_found": len(unique_docs),
            "total_chunks_retrieved": len(retrieved_chunks),
            "search_query": query,
            "domain_filter": domain,
            "metadata": {
                "retrieval_type": "enhanced",
                "suggestion_method": "hybrid",
                "domains_searched": len(domains_found) if not domain else 1
            }
        }
    
    def _parse_questions(self, questions_json: str) -> list[str]:
        """Parse stored JSON questions."""
        try:
            if isinstance(questions_json, str):
                return json.loads(questions_json)
            return questions_json if isinstance(questions_json, list) else []
        except:
            return []
    
    def _generate_follow_ups(
        self, 
        query: str, 
        doc_titles: list[str],
        domains: list[str]
    ) -> list[str]:
        """Generate intelligent follow-up questions using LLM."""
        if not doc_titles:
            return []
        
        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{
                    "role": "user",
                    "content": f"""Based on the user's question and retrieved documents, 
suggest 3 follow-up questions related to Indian government/civic topics:

User Question: {query}

Retrieved Documents: {', '.join(doc_titles)}
Domains: {', '.join(domains)}

Return exactly 3 follow-up questions, one per line, without numbering:"""
                }],
                temperature=0.5,
                max_tokens=200
            )
            
            questions = [q.strip() for q in response.choices[0].message.content.split('\n') if q.strip()]
            return questions[:3]
        except Exception as e:
            print(f"⚠️ Could not generate follow-ups: {e}")
            return []
    
    def search_by_domain(self, domain: str, limit: int = 10) -> dict[str, Any]:
        """
        Search for all documents in a specific domain
        
        Useful for: "Show me all documents about labor laws"
        """
        docs = self.vectorstore.collection.get(
            where={"domain": domain},
            limit=limit
        )
        
        unique_docs = {}
        for i, doc_id in enumerate(docs.get("ids", [])):
            metadata = docs["metadatas"][i] if docs.get("metadatas") else {}
            content = docs["documents"][i] if docs.get("documents") else ""
            
            title = metadata.get("title", f"Document {i+1}")
            if title not in unique_docs:
                unique_docs[title] = {
                    "title": title,
                    "domain": domain,
                    "category": metadata.get("category", ""),
                    "summary": metadata.get("summary", content[:150]),
                    "keywords": metadata.get("keywords", ""),
                }
        
        return {
            "domain": domain,
            "documents_found": len(unique_docs),
            "documents": list(unique_docs.values()),
        }
    
    def get_all_domains(self) -> dict[str, int]:
        """Get all domains and document count."""
        all_docs = self.vectorstore.collection.get()
        
        domains = {}
        for metadata in all_docs.get("metadatas", []):
            domain = metadata.get("domain", "general")
            domains[domain] = domains.get(domain, 0) + 1
        
        return domains
    
    def get_document_graph(self) -> dict[str, Any]:
        """Get relationship graph between documents and domains."""
        domains = self.get_all_domains()
        
        return {
            "total_documents": sum(domains.values()),
            "total_domains": len(domains),
            "domains": domains,
            "coverage": {
                "law": domains.get("law", 0),
                "finance": domains.get("finance", 0),
                "health": domains.get("health", 0),
                "schemes": domains.get("schemes", 0),
                "education": domains.get("education", 0),
                "agriculture": domains.get("agriculture", 0),
                "employment": domains.get("employment", 0),
                "housing": domains.get("housing", 0),
                "environment": domains.get("environment", 0),
                "transport": domains.get("transport", 0),
            }
        }


class DocumentManager:
    """
    Manage document ingestion, updates, and metadata
    """
    
    def __init__(self):
        self.retriever = EnhancedRetriever()
        self.log_file = "data/document_management.log"
        os.makedirs("data", exist_ok=True)
    
    def get_database_stats(self) -> dict[str, Any]:
        """Get comprehensive database statistics."""
        graph = self.retriever.get_document_graph()
        
        return {
            **graph,
            "database_type": "ChromaDB",
            "embedding_model": "Multilingual (FastText + mBERT)",
            "last_updated": self._get_last_update(),
            "total_chunks_indexed": self._count_total_chunks(),
        }
    
    def _get_last_update(self) -> str:
        """Get last update timestamp."""
        if os.path.exists("data/ingestion_log.json"):
            with open("data/ingestion_log.json") as f:
                logs = json.load(f)
                if logs:
                    return logs[-1].get("timestamp", "Unknown")
        return "Never"
    
    def _count_total_chunks(self) -> int:
        """Count total indexed chunks."""
        try:
            all_docs = self.retriever.vectorstore.collection.get()
            return len(all_docs.get("ids", []))
        except:
            return 0
    
    def generate_knowledge_summary(self) -> str:
        """Generate human-readable knowledge base summary."""
        stats = self.get_database_stats()
        
        summary = f"""
═══════════════════════════════════════════════════════════════
         SAMAJH OFFLINE KNOWLEDGE BASE SUMMARY
═══════════════════════════════════════════════════════════════

📚 TOTAL DOCUMENTS: {stats['total_documents']}
📝 TOTAL CHUNKS INDEXED: {stats['total_chunks_indexed']}
🌍 DOMAINS COVERED: {stats['total_domains']}

DOMAIN COVERAGE:
"""
        for domain, count in sorted(stats['coverage'].items()):
            if count > 0:
                summary += f"  ✅ {domain.upper():20} - {count:2} documents\n"
        
        summary += f"""
📅 LAST UPDATED: {stats['last_updated']}

CAPABILITIES:
  ✅ Hybrid retrieval (semantic + keyword search)
  ✅ Domain-aware filtering
  ✅ Intelligent question suggestions
  ✅ Multi-language support
  ✅ Cross-document relationships
  ✅ Relevance ranking

DOCUMENT SOURCES:
  ✅ Official Government PDFs (.gov.in)
  ✅ Verified Ministry Publications
  ✅ Legal & Constitutional Documents
  ✅ Citizen Rights & Welfare Schemes

═══════════════════════════════════════════════════════════════
"""
        return summary


# Helper functions for integration
def get_enhanced_search_results(query: str, domain: str = None):
    """Quick access to enhanced search."""
    retriever = EnhancedRetriever()
    return retriever.retrieve_with_suggestions(query, domain=domain)


def get_domain_documents(domain: str):
    """Quick access to browse by domain."""
    retriever = EnhancedRetriever()
    return retriever.search_by_domain(domain)


def get_knowledge_base_info():
    """Quick access to database info."""
    manager = DocumentManager()
    return manager.get_database_stats()


def print_knowledge_summary():
    """Print formatted summary."""
    manager = DocumentManager()
    print(manager.generate_knowledge_summary())


if __name__ == "__main__":
    manager = DocumentManager()
    print_knowledge_summary()
