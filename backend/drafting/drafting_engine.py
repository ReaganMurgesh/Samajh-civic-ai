"""
DraftingEngine — Generates formal Indian official documents from user issues.

This module powers the "Do It For Me" feature of SAMAJH, allowing users to
automatically generate RTI applications, complaint letters, and official
documents ready for submission to government authorities.
"""

from typing import Dict, Optional
from groq import Groq
from backend.utils.config import config


DOCUMENT_TEMPLATES = {
    "rti": {
        "name": "Right to Information (RTI) Application",
        "category": "administration",
        "icon": "📋",
        "description": "File an RTI request to get government information"
    },
    "panchayat_complaint": {
        "name": "Panchayat Complaint Letter",
        "category": "local_governance",
        "icon": "🏛️",
        "description": "Complain to your village panchayat about local issues"
    },
    "consumer_complaint": {
        "name": "Consumer Complaint (National Consumer Redressal)",
        "category": "consumer_rights",
        "icon": "🛡️",
        "description": "File a formal consumer protection complaint"
    },
    "labor_grievance": {
        "name": "Labor Grievance Redressal Application",
        "category": "labor_rights",
        "icon": "⚖️",
        "description": "Report labor violations or workplace issues"
    },
    "income_tax_appeal": {
        "name": "Income Tax Appeal Letter",
        "category": "taxation",
        "icon": "📊",
        "description": "Appeal against income tax assessment orders"
    },
    "pension_claim": {
        "name": "Pension/Benefit Claim Application",
        "category": "social_security",
        "icon": "💰",
        "description": "Apply for government pensions or social benefits"
    },
    "fir_complaint": {
        "name": "FIR (First Information Report) Complaint",
        "category": "law_enforcement",
        "icon": "🚨",
        "description": "File a criminal complaint with police"
    },
    "official_letter": {
        "name": "General Official Letter",
        "category": "general",
        "icon": "📄",
        "description": "Create a formal letter to any government department"
    }
}


class DraftingEngine:
    """
    Generates formal Indian official documents using Llama-3 via Groq.
    
    Features:
    - Smart prompt engineering for professional formatting
    - Multiple document templates (RTI, complaints, appeals, etc.)
    - Placeholder insertion for user customization
    - Citation compliance with Indian bureaucratic standards
    """
    
    def __init__(self):
        self.groq_client = Groq(api_key=config.groq_api_key)
        self.model = "llama-3.3-70b-versatile"  # Upgraded to latest Llama 3.3
    
    def generate_draft_document(
        self,
        user_issue: str,
        document_type: str = "rti",
        user_name: Optional[str] = None,
        user_address: Optional[str] = None,
        recipient: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate a formal Indian official document.
        
        Args:
            user_issue: Detailed description of the issue/request
            document_type: Type of document (rti, panchayat_complaint, etc.)
            user_name: User's full name (optional, will be a placeholder if not given)
            user_address: User's full address (optional, will be a placeholder if not given)
            recipient: Recipient authority (optional, auto-detected based on issue)
        
        Returns:
            Dict with "document_text" and "metadata"
        """
        
        template = DOCUMENT_TEMPLATES.get(document_type, DOCUMENT_TEMPLATES["official_letter"])
        
        # Build the specialized prompt based on document type
        prompt = self._build_prompt(
            user_issue=user_issue,
            document_type=document_type,
            template=template,
            user_name=user_name,
            user_address=user_address,
            recipient=recipient
        )
        
        print(f"🖊️  DraftingEngine: Generating {template['name']}...")
        
        try:
            response = self.groq_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,  # Low temperature for formal, consistent output
                max_tokens=1500
            )
            
            draft_text = response.choices[0].message.content
            
            return {
                "document_text": draft_text,
                "document_type": document_type,
                "template_name": template["name"],
                "category": template["category"],
                "success": True
            }
            
        except Exception as e:
            print(f"❌ Draft generation failed: {e}")
            return {
                "document_text": f"Error generating document: {str(e)}",
                "document_type": document_type,
                "template_name": template["name"],
                "success": False,
                "error": str(e)
            }
    
    def _build_prompt(
        self,
        user_issue: str,
        document_type: str,
        template: Dict,
        user_name: Optional[str] = None,
        user_address: Optional[str] = None,
        recipient: Optional[str] = None
    ) -> str:
        """Construct specialized prompt based on document type."""
        
        # Build context from document type
        if document_type == "rti":
            context = self._rti_context(user_issue, recipient)
        elif document_type == "panchayat_complaint":
            context = self._panchayat_context(user_issue)
        elif document_type == "consumer_complaint":
            context = self._consumer_context(user_issue)
        elif document_type == "labor_grievance":
            context = self._labor_context(user_issue)
        elif document_type == "fir_complaint":
            context = self._fir_context(user_issue)
        else:
            context = f"Issue/Request: {user_issue}"
        
        # User details with placeholders
        user_info = f"""
User Details (to be filled):
- Name: {user_name or '[Your Full Name]'}
- Address: {user_address or '[Your Full Address, City, State, PIN Code]'}
- Contact: [Your Mobile Number]
- Email: [Your Email Address]
- Date: [DD/MM/YYYY]
        """.strip()
        
        prompt = f"""
You are an expert Indian legal clerk with 15+ years of experience in drafting official government documents, RTI applications, complaints, and formal letters.

TASK: Draft a formal, professional {template['name']} based on the following issue.

{context}

{user_info}

STRICT FORMATTING RULES:
1. Use formal Indian English (e.g., "Respected Sir/Madam" not "Dear Sir")
2. Structure: To, From, Date, Reference Number, Subject, Body, Signature
3. Replace user details with EXACT PLACEHOLDERS like [Your Full Name], [Your Address], [Date]
4. Use numbered lists [1], [2], [3] for points
5. Include all legally required sections for this document type
6. Keep language respectful but firm and assertive
7. Do NOT add any conversational intro/outro - ONLY the document itself
8. Add a footer with "Yours faithfully," and space for signature
9. Make sure the document is ready to print and submit immediately

OUTPUT: Only the formal document. No explanations, no markdown formatting, no "---" dividers.

GENERATE THE DOCUMENT NOW:
"""
        return prompt
    
    def _rti_context(self, user_issue: str, recipient: Optional[str] = None) -> str:
        """RTI-specific context."""
        rec = recipient or "the Public Information Officer (PIO)"
        return f"""
DOCUMENT TYPE: Right to Information (RTI) Act, 2005 Application

This is an RTI application to request specific government information.

ISSUE/REQUEST:
{user_issue}

Recipient: {rec}

LEGAL BASIS: The citizen is exercising their right under the Right to Information Act, 2005 to obtain non-disclosed government information.
        """.strip()
    
    def _panchayat_context(self, user_issue: str) -> str:
        """Panchayat complaint context."""
        return f"""
DOCUMENT TYPE: Village Panchayat/Municipal Complaint Letter

This is a formal complaint to the local Panchayat/Municipal authority about a local governance issue.

ISSUE/COMPLAINT:
{user_issue}

Your Gram Panchayat/Municipal Corporation has the duty to address this.
        """.strip()
    
    def _consumer_context(self, user_issue: str) -> str:
        """Consumer complaint context."""
        return f"""
DOCUMENT TYPE: Consumer Protection Act Complaint

This is a formal complaint under the Consumer Protection Act (likely for the State Consumer Disputes Redressal Commission).

COMPLAINT DETAILS:
{user_issue}

Provide: Seller/Service Provider details, amount paid, date of purchase, defect/complaint.
        """.strip()
    
    def _labor_context(self, user_issue: str) -> str:
        """Labor grievance context."""
        return f"""
DOCUMENT TYPE: Labor Dispute Redressal Application

This is a formal grievance to the Labor Commissioner or Inspector under labor laws.

GRIEVANCE:
{user_issue}

Include: Your employer, workplace, violation details, impact on you.
        """.strip()
    
    def _fir_context(self, user_issue: str) -> str:
        """FIR complaint context."""
        return f"""
DOCUMENT TYPE: First Information Report (FIR) Complaint

This is a formal criminal complaint to be filed with the Police Station.

COMPLAINT DESCRIPTION:
{user_issue}

Provide: Date/time of incident, location, persons involved, witnesses, damages/loss.
        """.strip()
    
    def get_available_templates(self) -> Dict[str, Dict]:
        """Return all available document templates with descriptions."""
        return DOCUMENT_TEMPLATES
    
    def get_suggested_template(self, issue_text: str) -> str:
        """
        Suggest most appropriate document template based on issue keywords.
        
        Returns: document_type key for most relevant template
        """
        issue_lower = issue_text.lower()
        
        # Keyword-based suggestions
        if any(word in issue_lower for word in ["information", "rti", "right to", "official records"]):
            return "rti"
        elif any(word in issue_lower for word in ["panchayat", "village", "local", "gram"]):
            return "panchayat_complaint"
        elif any(word in issue_lower for word in ["seller", "product", "service", "defect", "consumer"]):
            return "consumer_complaint"
        elif any(word in issue_lower for word in ["salary", "wage", "workplace", "labor", "employer", "hours"]):
            return "labor_grievance"
        elif any(word in issue_lower for word in ["crime", "police", "theft", "assault", "harassment", "criminal"]):
            return "fir_complaint"
        elif any(word in issue_lower for word in ["tax", "income", "assessment", "appeal"]):
            return "income_tax_appeal"
        elif any(word in issue_lower for word in ["pension", "benefit", "allowance", "social security"]):
            return "pension_claim"
        
        # Default
        return "official_letter"
