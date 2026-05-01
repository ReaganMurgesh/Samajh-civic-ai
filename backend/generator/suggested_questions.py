"""
Suggested Questions Generator for SAMAJH Official Database Mode

Generates contextual questions based on ChromaDB documents and user conversation history.
"""

from typing import List
import os
from groq import Groq


class SuggestedQuestionsGenerator:
    """Generate smart suggested questions from ChromaDB documents."""

    def __init__(self):
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        # Use fallback if API key is missing or placeholder
        self.use_fallback = not api_key or api_key == "your_groq_key_here"
        if not self.use_fallback:
            self.groq_client = Groq(api_key=api_key)
        else:
            self.groq_client = None
        self.model = "llama-3.3-70b-versatile"

    def generate_from_documents(self, documents_text: str, num_questions: int = 12) -> List[str]:
        """
        Generate suggested questions from document content.
        
        Args:
            documents_text: Combined text from retrieved documents
            num_questions: Number of questions to generate (default 12)
            
        Returns:
            List of natural language questions
        """
        if self.use_fallback or not self.groq_client:
            return self._get_detailed_fallback_questions()
            
        prompt = f"""You are an expert civic information assistant for Indian government schemes and policies.
Based on the following government documents/schemes, generate {num_questions} specific, detailed questions 
that citizens would actually want answers to. These questions should help users understand important 
government programs, benefits, and how to access them.

Documents (schemes/topics):
{documents_text[:3000]}

Requirements:
1. MUST be SPECIFIC - mention actual scheme names, programs, or topics (e.g., "PM-KISAN", "Ayushman Bharat", "RTI", not just "scheme")
2. MUST be DETAILED - include relevant context (e.g., "What are the income limits for PM-KISAN eligibility?" not just "What is eligibility?")
3. MUST be PRACTICAL - questions citizens actually need answers to
4. Vary difficulty - include simple, intermediate, and advanced questions
5. Cover different aspects - eligibility, benefits, application process, deadlines, rights, grievances
6. Make them complete questions (8-20 words) so users understand the full context

IMPORTANT: Each question MUST be independent and understandable on its own. Include enough context/details.

Format as numbered list, one question per line:
1. Detailed question about a specific topic?
2. Another specific detailed question?
..."""

        try:
            response = self.groq_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.7
            )
            
            text = response.choices[0].message.content if response.choices else ""
            questions = self._parse_questions(text)
            return questions[:num_questions] if questions else self._get_detailed_fallback_questions()
            
        except Exception as e:
            print(f"Error generating questions: {e}")
            return self._get_detailed_fallback_questions()

    def generate_from_topics(self, topics: List[str], num_questions: int = 12) -> List[str]:
        """
        Generate questions from a list of topics/keywords.
        
        Args:
            topics: List of topic keywords (e.g., ["RTI", "PM-KISAN", "Ayushman Bharat"])
            num_questions: Number of questions to generate
            
        Returns:
            List of natural language questions
        """
        topics_text = ", ".join(topics[:10])
        
        prompt = f"""You are a civic information assistant. Create {num_questions} practical questions 
that citizens would ask about these government topics/schemes:

Topics: {topics_text}

Generate questions that are:
1. Specific and practical
2. Actionable (citizens want to DO something)
3. Clear and concise
4. Varied difficulty levels
5. Related to eligibility, application, benefits, timelines

Format as numbered list:
1. Question here?
2. Another question?
..."""

        try:
            response = self.groq_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.7
            )
            
            text = response.choices[0].message.content if response.choices else ""
            questions = self._parse_questions(text)
            return questions[:num_questions]
            
        except Exception:
            return self._get_fallback_questions()

    def generate_contextual(
        self, 
        current_question: str,
        conversation_history: List[str],
        num_questions: int = 5,
        answer_context: str = ""
    ) -> List[str]:
        """
        Generate follow-up questions based on current conversation and the AI's actual answer.
        
        Args:
            current_question: The question user just asked
            conversation_history: List of previous questions
            num_questions: Number of follow-up questions
            answer_context: The answer just provided to the user, to ground the follow-ups
            
        Returns:
            List of related follow-up questions
        """
        history_text = "\n".join([f"- {q}" for q in conversation_history[-5:]]) if conversation_history else "No previous questions"
        
        context_prompt = f"\nAnswer just provided to the user:\n{answer_context[:1500]}\n" if answer_context else ""
        
        prompt = f"""You are a helpful expert assistant. The user just asked this question:

Current Question: {current_question}{context_prompt}
Previous Questions in this conversation:
{history_text}

Now suggest {num_questions} SPECIFIC, HELPFUL follow-up questions that:
1. Are directly related to what they just asked and the answer they received (not generic defaults)
2. Help them understand different aspects of the topic they're interested in
3. Are more detailed and specific than the original question
4. Help the user dig deeper into the information just provided
5. Include enough context so each question is clear and complete (not vague)

Examples of GOOD follow-ups:
- Instead of "How to apply?" ask "What documents are needed to apply for this specific program by the deadline?"
- Instead of "What are benefits?" ask "How much monthly assistance does this scheme provide?"
- Instead of "Eligibility?" ask "Are there any special eligibility provisions for marginalized categories?"

Format as numbered list:
1. Specific, detailed follow-up question?
2. Another relevant, detailed question?
..."""

        if self.use_fallback or not self.groq_client:
            return self._get_contextual_fallback(current_question)

        try:
            response = self.groq_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=700,
                temperature=0.7
            )
            
            text = response.choices[0].message.content if response.choices else ""
            questions = self._parse_questions(text)
            return questions[:num_questions] if questions else self._get_contextual_fallback(current_question)
            
        except Exception as e:
            print(f"Error generating follow-up questions: {e}")
            return self._get_contextual_fallback(current_question)

    def _parse_questions(self, text: str) -> List[str]:
        """Extract numbered questions from Groq response."""
        questions = []
        
        for line in text.split("\n"):
            line = line.strip()
            
            # Remove numbering (1., 1), etc.)
            if line and (line[0].isdigit()):
                # Find where the question text starts
                for i, char in enumerate(line):
                    if char in ".):":
                        question = line[i+1:].strip()
                        if question and len(question) > 5:
                            questions.append(question)
                        break
        
        return questions

    def _get_detailed_fallback_questions(self) -> List[str]:
        """Detailed fallback questions when generation fails - specific to Indian government topics."""
        return [
            "What are the income and land-holding criteria for PM-KISAN eligibility?",
            "How do I apply for Ayushman Bharat health insurance and what documents are required?",
            "What is Right to Information (RTI) and how do I file an RTI request online?",
            "What are the benefits and eligibility requirements for widow pension schemes?",
            "How can I check my NREGA work status and download job cards in my state?",
            "What documents are needed for property registration and what are the stamp duty rates?",
            "How do I apply for scholarships under SC/ST/OBC categories for higher education?",
            "What is the process for getting a Unique Identification Number (Aadhaar)?",
            "How much maternity benefit am I entitled to under the Pradhan Mantri Matritva Vandana scheme?",
            "What are the eligibility criteria and monthly payment amounts for senior citizen pension?",
            "How do I register a complaint against a government official and track its status?",
            "What are the different types of government loans available for small businesses and farmers?",
        ]

    def _get_contextual_fallback(self, question: str) -> List[str]:
        """Generate contextual fallback questions based on the user's actual question."""
        question_lower = question.lower()
        
        # Determine context from the question
        if any(word in question_lower for word in ["pm-kisan", "farmer", "agriculture", "crop", "subsidy"]):
            return [
                "What is the exact amount of cash assistance provided under PM-KISAN per year?",
                "Are tenant farmers and landless laborers eligible for PM-KISAN benefits?",
                "How do I correct my name or address if already registered in PM-KISAN?",
                "What is the process for filing a grievance if payment is delayed?",
                "Are there any additional state-level agricultural schemes complementing PM-KISAN?"
            ]
        elif any(word in question_lower for word in ["health", "insurance", "ayushman", "treatment", "hospital"]):
            return [
                "Which hospitals are empaneled under Ayushman Bharat across my district?",
                "How much medical coverage does Ayushman Bharat provide per family annually?",
                "Can I use Ayushman Bharat coverage in private hospitals and nursing homes?",
                "What health conditions and treatments are covered by Ayushman Bharat?",
                "How do I claim reimbursement if I paid for treatment out-of-pocket?"
            ]
        elif any(word in question_lower for word in ["rti", "information", "transparent", "government", "data"]):
            return [
                "What are the different RTI application fees for central and state governments?",
                "What is the time limit for government to respond to RTI requests?",
                "Can I appeal if my RTI request is rejected or information is partially disclosed?",
                "Which government departments have online RTI portals for faster filing?",
                "Are there any subjects exempted from RTI disclosure for national security?"
            ]
        elif any(word in question_lower for word in ["pension", "elderly", "senior", "widow", "benefit", "disability"]):
            return [
                "What is the monthly pension amount for old age pensioners in my state?",
                "Do I need to submit any documents annually to continue receiving widow pension?",
                "Are disability pension amounts based on the degree of disability?",
                "How do I apply for pension if I was unable to register during the initial enrollment?",
                "What happens to pension benefits if a beneficiary relocates to another state?"
            ]
        elif any(word in question_lower for word in ["education", "scholarship", "school", "college", "student", "fee"]):
            return [
                "What are the income limits for eligibility under merit-cum-means scholarships?",
                "Are vocational and professional courses covered under government scholarship schemes?",
                "How much scholarship amount is provided for undergraduate vs postgraduate studies?",
                "Can I receive scholarships from multiple schemes simultaneously?",
                "When and how do I need to renew my scholarship application each academic year?"
            ]
        elif any(word in question_lower for word in ["loan", "credit", "business", "enterprise", "mudra", "startup"]):
            return [
                "What are the loan amount limits under MUDRA scheme for different business categories?",
                "How much interest subsidy is available for loans under priority sector lending?",
                "What collateral or guarantee is required for government-backed business loans?",
                "Are women entrepreneurs eligible for additional benefits in startup loans?",
                "What is the repayment period and moratorium available for agricultural loans?"
            ]
        else:
            # Generic but more detailed fallback for unknown topics
            return [
                "What specific benefits does this scheme or policy provide to eligible applicants?",
                "What are the complete eligibility criteria including income, age, and location requirements?",
                "What documents or certificates must be submitted to apply for this program?",
                "What is the application deadline and how frequently can I reapply if rejected?",
                "How long does the processing take and when will I receive benefits or approval?"
            ]


# Singleton instance
suggested_questions_gen = SuggestedQuestionsGenerator()
