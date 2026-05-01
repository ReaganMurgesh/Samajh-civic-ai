"""Hallucination detection and guardrails for Samajh generation."""

from typing import List, Dict, Any
from langchain_core.documents import Document

class HallucinationGuard:
    """Provides mechanisms to verify that an answer is rooted in its sources."""

    def __init__(self, strictness: float = 0.5):
        """Initialize the guard.
        
        Args:
            strictness: Required ratio of answer terms that must be present in chunks.
        """
        self.strictness = strictness

    def verify_grounding(self, answer: str, chunks: List[Document]) -> Dict[str, Any]:
        """Verify if the generated answer is grounded in the provided chunks.
        
        Returns:
            Dict containing 'is_grounded' boolean and 'confidence' score.
        """
        if not answer or not answer.strip():
            return {"is_grounded": True, "confidence": 1.0}
            
        if not chunks:
            return {"is_grounded": False, "confidence": 0.0}

        # Combine all chunk text
        context_text = " ".join([c.page_content.lower() for c in chunks])
        
        # Super simple lexical overlap for the MVP
        # In a production scenario, we would use an LLM or an NLI model
        answer_words = set(w.strip('.,!?()[]{}"\'') for w in answer.lower().split() if len(w) > 4)
        
        if not answer_words:
            return {"is_grounded": True, "confidence": 1.0}

        matched_words = sum(1 for w in answer_words if w in context_text)
        grounding_score = matched_words / len(answer_words)

        return {
            "is_grounded": grounding_score >= self.strictness,
            "score": round(grounding_score, 2),
            "details": f"{matched_words} of {len(answer_words)} significant words found in sources."
        }

guard = HallucinationGuard()
