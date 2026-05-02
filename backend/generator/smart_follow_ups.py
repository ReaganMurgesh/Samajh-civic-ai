"""
Smart Follow-Up Question Generator for SAMAJH.

Generates contextual, action-oriented follow-up questions based on:
1. The original user question
2. The answer provided
3. The type of document/issue
4. Available sources and information

This replaces generic "Tell me more" and ok with specific next steps.
"""

from typing import List, Dict, Any
import re


class SmartFollowUpGenerator:
    """Generate context-aware, action-oriented follow-up questions."""
    
    # Action-oriented follow-up templates by category
    FOLLOW_UP_TEMPLATES = {
        "rti": [
            "Where can I find my local PIO (Public Information Officer)?",
            "What should I do if my RTI request is rejected?",
            "Can I appeal if the information is delayed beyond 30 days?",
            "What happens if I don't get a response within 30 days?",
            "How do I know if my PIO is legitimate?",
            "What if the PIO asks for extra fees?",
        ],
        "rights": [
            "How do I file a complaint if my rights are violated?",
            "What are my appeal options?",
            "Where do I go if this doesn't help?",
            "How long does the process usually take?",
            "Do I need a lawyer for this?",
            "Are there free legal aid options?",
        ],
        "schemes": [
            "How do I check if I'm eligible for this scheme?",
            "What documents do I need to apply?",
            "How do I submit my application?",
            "When will I receive the benefits?",
            "What should I do if my application is rejected?",
            "How do I check my application status?",
        ],
        "labor": [
            "How do I file a formal complaint about this?",
            "Can I file anonymously?",
            "What are the penalties for violation?",
            "How long does the investigation take?",
            "Can I get back wages and compensation?",
            "Where is my nearest labor office?",
        ],
        "consumer": [
            "How do I file a consumer complaint?",
            "What compensation can I claim?",
            "What if the seller refuses to help?",
            "How long will the legal process take?",
            "Do I need to hire a lawyer?",
            "Where is my nearest consumer court?",
        ],
        "tax": [
            "How do I file an appeal against this assessment?",
            "What is the deadline for the appeal?",
            "Can I get refund interest if I'm right?",
            "What documents do I need for the appeal?",
            "Should I hire a tax consultant?",
            "Where do I submit my appeal?",
        ],
        "pension": [
            "How do I check my pension eligibility?",
            "What documents do I need to submit?",
            "How long does the approval process take?",
            "What if my application is rejected?",
            "Can I appeal a rejection?",
            "How is my pension calculated?",
        ],
        "crime": [
            "How do I file an FIR (First Information Report)?",
            "What happens after I file an FIR?",
            "Can I get copies of the FIR?",
            "What protection do I get as a witness?",
            "Where can I get legal help?",
            "How long does a criminal case take?",
        ],
        "default": [
            "What are my next steps?",
            "How much will this cost?",
            "How long will this take?",
            "Where do I submit my application?",
            "What if I face issues?",
            "Is there legal help available?",
        ]
    }
    
    # Keywords to detect document/issue type
    KEYWORD_PATTERNS = {
        "rti": ["rti", "right to information", "information request", "public information"],
        "rights": ["right", "freedom", "constitution", "fundamental", "violation", "harassment", "discrimination"],
        "schemes": ["scheme", "benefit", "grant", "pm-kisan", "ayushman", "awas", "pension", "subsidy"],
        "labor": ["salary", "wage", "minimum wage", "overtime", "workplace", "employer", "labor", "worker", "employee", "hours"],
        "consumer": ["product", "seller", "shop", "defective", "complaint", "service", "quality", "consumer"],
        "tax": ["tax", "income tax", "assessment", "appeal", "refund"],
        "pension": ["pension", "retirement", "allowance", "benefit", "elderly"],
        "crime": ["crime", "police", "fir", "theft", "assault", "sexual", "harassment", "criminal"],
    }
    
    def __init__(self):
        """Initialize the smart follow-up generator."""
        pass
    
    def generate(
        self,
        query: str,
        answer: str,
        sources: List[Dict[str, Any]] = None,
        detected_type: str = None
    ) -> List[str]:
        """
        Generate 3 action-oriented follow-up questions.
        
        Args:
            query: Original user question
            answer: The answer provided
            sources: List of sources used
            detected_type: Document/scheme type (rti, labor, consumer, etc.)
        
        Returns:
            List of 3 follow-up questions (action-oriented)
        """
        
        # Detect the issue type if not provided
        issue_type = detected_type or self._detect_issue_type(query, answer)
        
        # Get relevant follow-up templates for this type
        templates = self.FOLLOW_UP_TEMPLATES.get(issue_type, self.FOLLOW_UP_TEMPLATES["default"])
        
        # Generate 3 diverse, contextual follow-ups
        follow_ups = self._select_best_follow_ups(
            query=query,
            answer=answer,
            templates=templates,
            issue_type=issue_type
        )
        
        return follow_ups[:3] if len(follow_ups) >= 3 else follow_ups + self.FOLLOW_UP_TEMPLATES["default"][:3]
    
    def _detect_issue_type(self, query: str, answer: str) -> str:
        """Detect the issue type from query and answer."""
        combined_text = f"{query} {answer}".lower()
        
        # Score each category
        scores = {}
        for category, keywords in self.KEYWORD_PATTERNS.items():
            score = sum(1 for keyword in keywords if keyword in combined_text)
            scores[category] = score
        
        # Return highest scoring category
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        return "default"
    
    def _select_best_follow_ups(
        self,
        query: str,
        answer: str,
        templates: List[str],
        issue_type: str
    ) -> List[str]:
        """
        Select the 3 most relevant follow-ups from templates.
        
        Tries to match follow-ups to specific details in the answer.
        """
        combined_text = f"{query} {answer}".lower()
        scored_follow_ups = []
        
        # Score each template
        for template in templates:
            template_lower = template.lower()
            score = 0
            
            # Boost score if template addresses common next steps
            if "is rejected" in template_lower and "reject" in combined_text:
                score += 10
            if "deadline" in template_lower and ("day" in combined_text or "date" in combined_text):
                score += 8
            if "apply" in template_lower or "application" in template_lower:
                score += 5
            if "where" in template_lower and "office" not in combined_text:
                score += 3
            if "document" in template_lower:
                score += 2
            
            scored_follow_ups.append((score, template))
        
        # Sort by score and return top 3
        scored_follow_ups.sort(key=lambda x: x[0], reverse=True)
        return [t[1] for t in scored_follow_ups[:3]]
    
    @staticmethod
    def _extract_key_concepts(text: str) -> List[str]:
        """Extract key concepts from text for context."""
        concepts = []
        
        # Extract numbers (often relevant: deadlines, fees, percentages)
        numbers = re.findall(r'\b(\d+)\s*(days?|years?|months?|rs|%|hours?|percent|rupees?)\b', text.lower())
        concepts.extend([f"{n[0]} {n[1]}" for n in numbers])
        
        # Extract organization names
        orgs = re.findall(r'\b(PIO|RTI|FIR|NGO|ministry|department|commission|court)\b', text, re.IGNORECASE)
        concepts.extend(orgs)
        
        return concepts[:5]  # Return top 5 concepts
