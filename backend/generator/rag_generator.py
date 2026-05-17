"""RAG answer generation utilities for the Samajh platform."""

from __future__ import annotations

import re
from typing import Any

from anthropic import Anthropic
from groq import Groq
from langchain_core.documents import Document

from backend.utils.config import config
from backend.generator.guide_personas import get_guide_persona
from backend.generator.smart_follow_ups import SmartFollowUpGenerator


# Official Government Source Catalog with URLs and Descriptions
OFFICIAL_SOURCES_INFO = {
    "RTI_Act_Citizens_Guide.pdf": {
        "title": "Right to Information Act - Citizens Guide",
        "url": "https://www.rti.gov.in/guide",
        "domain": "law",
        "description": "Official guide explaining how citizens can request government information under the RTI Act. Covers filing procedures, fees, timelines, and appeal process.",
        "ministry": "Department of Personnel & Training"
    },
    "Bharatiya_Nyaya_Sanhita_2023_Official.pdf": {
        "title": "Bharatiya Nyaya Sanhita (Indian Penal Code) 2023",
        "url": "https://pib.gov.in/PressReleasePage.aspx?PRID=1839564",
        "domain": "law",
        "description": "New criminal justice code replacing IPC. Contains sections on various offenses, punishments, and legal procedures.",
        "ministry": "Ministry of Law & Justice"
    },
    "Constitution_Fundamental_Rights_Summary.pdf": {
        "title": "Constitution of India - Fundamental Rights",
        "url": "https://www.constitution.gov.in/",
        "domain": "law",
        "description": "Your constitutional rights as an Indian citizen. Covers freedom of speech, equality, right to life, and other fundamental rights.",
        "ministry": "Parliamentary Affairs"
    },
    "CrPC_Criminal_Procedure_Guide.pdf": {
        "title": "Criminal Procedure Code - Citizen Guide",
        "url": "https://www.mha.gov.in/",
        "domain": "law",
        "description": "Guide to criminal procedures in India. Explains FIR filing, investigation process, arrest rights, and court procedures.",
        "ministry": "Ministry of Home Affairs"
    },
    "Union_Budget_2026_27_Summary.pdf": {
        "title": "Union Budget 2026-27",
        "url": "https://www.indiabudget.gov.in/",
        "domain": "finance",
        "description": "Central government budget allocation for 2026-27. Shows government spending, tax policies, and fiscal priorities.",
        "ministry": "Ministry of Finance"
    },
    "RBI_Monetary_Policy_Guide.pdf": {
        "title": "RBI Monetary Policy Guide",
        "url": "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=55949",
        "domain": "finance",
        "description": "Reserve Bank of India's monetary policy decisions. Explains interest rates, inflation control, and banking regulations.",
        "ministry": "Reserve Bank of India"
    },
    "National_Health_Policy_2017.pdf": {
        "title": "National Health Policy 2017",
        "url": "https://main.mohfw.gov.in/",
        "domain": "health",
        "description": "Government health policy framework covering healthcare access, disease prevention, and universal health coverage goals.",
        "ministry": "Ministry of Health & Family Welfare"
    },
    "Ayushman_Bharat_Eligibility_Guide.pdf": {
        "title": "Ayushman Bharat Scheme - Eligibility & Benefits",
        "url": "https://www.pmjay.gov.in/",
        "domain": "health",
        "description": "Free health insurance for low-income families up to Rs. 5 lakhs per year. Check eligibility and benefits.",
        "ministry": "Ministry of Labour & Employment"
    },
    "Pradhan_Mantri_Awas_Yojana_Guide.pdf": {
        "title": "Pradhan Mantri Awas Yojana (Housing Scheme)",
        "url": "https://pmaymis.gov.in/",
        "domain": "schemes",
        "description": "Government housing scheme with subsidized loans and grants for affordable homes. For low-income families.",
        "ministry": "Ministry of Housing & Urban Affairs"
    },
    "Crop_Insurance_PMFBY_Manual.pdf": {
        "title": "Pradhan Mantri Fasal Bima Yojana (Crop Insurance)",
        "url": "https://pmfby.gov.in/",
        "domain": "schemes",
        "description": "Crop insurance scheme protecting farmers from crop failure. Low premiums with government support.",
        "ministry": "Ministry of Agriculture & Farmers Welfare"
    },
    "PM_KISAN_Official_Manual.pdf": {
        "title": "PM-KISAN Scheme Manual",
        "url": "https://pmkisan.gov.in/",
        "domain": "schemes",
        "description": "Direct cash benefit scheme for farmers. Rs. 6,000 per year in three installments. For all farmers with land holding up to 2 hectares.",
        "ministry": "Ministry of Agriculture & Farmers Welfare"
    }
}


# ---------------------------------------------------------------------------
# SYSTEM PROMPT — Strict answer policy for direct, verified responses
# ---------------------------------------------------------------------------
DEFAULT_SYSTEM_PROMPT = """
You are SAMAJH, a highly intelligent, direct, and helpful civic assistant for Indian citizens. 
You must answer the user's question using ONLY the provided context chunks.

CRITICAL RULES FOR ANSWERING:
1. TALK LIKE A HUMAN: Explain concepts simply, as if speaking to a high school student. Absolutely no dense legal jargon or long, unbroken walls of text.
2. BE DIRECT: State the answer immediately in the first sentence.
3. THE "NO GUESSING" RULE: If the context chunks are about "Housing" but the user asks about "Farming", you MUST REFUSE TO ANSWER. Say: "I do not have verified information on this specific topic in my database yet, but I can check the live web for you."
4. MANDATORY SPACING: Use double line breaks (\n\n) between every section. Use bullet points for lists.

Format your response EXACTLY like this:

**Direct Answer:** (1-2 sentences explaining the core concept simply).

**Key Details:**
* (Bullet point 1)
* (Bullet point 2)
* (Bullet point 3)

**Real-World Example:**
(Provide a quick, practical 1-sentence example of a citizen using this).

**What You Should Do Next:** (1 sentence of actionable advice).
"""


class SamajhGenerator:
    """Generate grounded answers from retrieved chunks with safe fallbacks."""

    _RELEVANCE_THRESHOLD = 0.12
    _MAX_CONTEXT_CHARS = 4000
    _MAX_CHUNKS = 5
    _MAX_JARGON_TERMS = 12

    def __init__(self, llm_provider: str = "groq") -> None:
        """Initialize the generator and configure an optional LLM client."""
        self.llm_provider = (llm_provider or "groq").strip().lower()
        self._client = self._build_client(self.llm_provider)
        self.current_guide = "general"

    def generate_answer(
        self,
        query: str,
        retrieved_chunks: list[Document],
        user_language: str = "english",
        guide: str = "general",
    ) -> dict[str, Any]:
        """Generate a grounded answer from retrieved chunks.

        Args:
            query: User question.
            retrieved_chunks: Retrieved LangChain documents.
            user_language: Requested answer language label.
            guide: Guide persona to use ('general', 'legal', 'farmer', 'health').

        Returns:
            JSON-serializable answer payload with answer text, confidence,
            jargon terms, sources, and follow-up questions.
        """
        self.current_guide = guide
        normalized_query = self._normalize_text(query)
        language = self._normalize_language(user_language)
        valid_chunks = self._prepare_chunks(retrieved_chunks)
        relevant_chunks = self._filter_relevant_chunks(normalized_query, valid_chunks)
        sources = self._build_sources(relevant_chunks)
        confidence = self._compute_confidence(relevant_chunks)

        if not normalized_query or not relevant_chunks:
            fallback_answer = self._build_no_information_fallback(language)
            return {
                "answer": fallback_answer,
                "original_query": query,
                "confidence": confidence,
                "jargon_terms": self._extract_jargon_terms(fallback_answer),
                "sources": sources,
                "language": language,
                "provider": self.llm_provider if self._client else "fallback",
            }

        if self._client is not None:
            answer = self._generate_with_llm(
                query=normalized_query,
                relevant_chunks=relevant_chunks,
                user_language=language,
            )
        else:
            answer = ""

        if not answer:
            answer = self._build_extractive_fallback(
                query=normalized_query,
                relevant_chunks=relevant_chunks,
                user_language=language,
            )

        follow_ups = self._generate_follow_up_questions(query, answer, guide)

        return {
            "answer": answer,
            "original_query": query,
            "confidence": confidence,
            "jargon_terms": self._extract_jargon_terms(answer),
            "sources": sources,
            "language": language,
            "provider": self.llm_provider if self._client else "fallback",
            "follow_up_questions": follow_ups,
            "guide": guide,
        }

    def _build_client(self, provider: str) -> Any | None:
        """Create a supported LLM client when the required API key is available."""
        if provider == "anthropic" and config.anthropic_api_key:
            return Anthropic(api_key=config.anthropic_api_key)
        if provider == "groq" and config.groq_api_key:
            return Groq(api_key=config.groq_api_key)
        return None

    def _prepare_chunks(self, chunks: list[Document]) -> list[Document]:
        """Normalize chunk text and metadata while keeping only valid documents."""
        prepared: list[Document] = []

        for chunk in chunks or []:
            if not isinstance(chunk, Document):
                continue

            text = self._normalize_text(chunk.page_content)
            if not text:
                continue

            metadata = self._sanitize_metadata(chunk.metadata)
            prepared.append(Document(page_content=text, metadata=metadata))

        return prepared[: self._MAX_CHUNKS]

    def _filter_relevant_chunks(self, query: str, chunks: list[Document]) -> list[Document]:
        """Keep chunks that appear relevant based on similarity + lightweight keyword overlap."""
        relevant: list[Document] = []
        query_terms = self._tokenize(query)
        enforce_overlap = any(term.isascii() for term in query_terms)
        english_stopwords = {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "if",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "do",
            "does",
            "did",
            "how",
            "what",
            "why",
            "when",
            "where",
            "who",
            "whom",
            "which",
            "i",
            "you",
            "my",
            "your",
            "me",
            "it",
            "this",
            "that",
            "these",
            "those",
            "can",
            "could",
            "should",
            "would",
            "please",
        }
        content_query_terms = (
            {t for t in query_terms if t not in english_stopwords}
            if enforce_overlap
            else query_terms
        )

        for chunk in chunks:
            raw_similarity = chunk.metadata.get("similarity_score")
            if raw_similarity is None:
                # Some callers may provide chunks without similarity metadata.
                # In that case, keep reasonably-sized text so we can still answer.
                if len(chunk.page_content.split()) >= 20:
                    relevant.append(chunk)
                continue

            similarity = self._safe_float(raw_similarity, default=0.0)

            if similarity < self._RELEVANCE_THRESHOLD:
                continue

            if not enforce_overlap:
                # Cross-language queries (Tamil/Hindi/etc.) won't share keywords with
                # English chunks, so rely on similarity.
                relevant.append(chunk)
                continue

            # Similarity alone can produce false positives for unrelated English queries.
            # Require an overlap on non-stopword terms unless similarity is very high.
            text_terms = self._tokenize(chunk.page_content)
            if content_query_terms and content_query_terms.intersection(text_terms):
                relevant.append(chunk)
                continue

            if similarity >= 0.35:
                relevant.append(chunk)

        return relevant[: self._MAX_CHUNKS]

    def _generate_with_llm(
        self,
        query: str,
        relevant_chunks: list[Document],
        user_language: str,
    ) -> str:
        """Generate an answer with the selected LLM provider."""
        context = self._build_context(relevant_chunks)
        prompt = self._build_user_prompt(query, context, user_language)

        # Merge the guide persona system prompt with the citation-enforcing DEFAULT_SYSTEM_PROMPT.
        # The guide persona adds personality/tone; DEFAULT_SYSTEM_PROMPT enforces citation format.
        guide_persona = get_guide_persona(self.current_guide)["system_prompt"]
        combined_system = f"{guide_persona}\n\n{DEFAULT_SYSTEM_PROMPT}"

        try:
            if self.llm_provider == "anthropic":
                response = self._client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=600,
                    temperature=0,
                    system=combined_system,
                    messages=[{"role": "user", "content": prompt}],
                )
                text_parts = []
                for item in getattr(response, "content", []):
                    item_text = getattr(item, "text", "")
                    if item_text:
                        text_parts.append(item_text)
                return self._normalize_answer("\n".join(text_parts))

            response = self._client.chat.completions.create(
                model="llama-3.3-70b-versatile",  # Upgraded to latest Llama 3.3 for better reasoning
                temperature=0,
                max_completion_tokens=600,
                messages=[
                    {"role": "system", "content": combined_system},
                    {"role": "user", "content": prompt},
                ],
            )
            message = response.choices[0].message.content if response.choices else ""
            return self._normalize_answer(message)
        except Exception:
            return ""

    def _build_user_prompt(self, query: str, context: str, user_language: str) -> str:
        """Build the user prompt that locks in numbered inline citation behaviour."""
        return (
            f"User language: {user_language}\n\n"
            f"## User's Question\n{query}\n\n"
            f"## Retrieved Source Chunks\n{context}\n\n"
            "## Your Task\n"
            "Answer ONLY the question above using ONLY the numbered source chunks.\n"
            "Every factual sentence MUST end with an inline citation like [1] or [1][2].\n"
            "Use Markdown: **bold** for key terms, bullet points for lists.\n"
            "Do NOT write 'According to the source' — just write the fact and cite it: fact [N].\n"
            "If the sources don't contain the answer, say so clearly and stop.\n"
            f"Respond in {user_language}."
        )

    def _build_context(self, chunks: list[Document]) -> str:
        """Create numbered context blocks that map directly to [N] inline citations."""
        parts: list[str] = []
        current_length = 0

        for index, chunk in enumerate(chunks, start=1):
            metadata = chunk.metadata or {}
            citation = self._format_source_label(metadata)
            snippet = chunk.page_content.strip()

            # Each block is clearly numbered so the LLM maps [N] → source N
            part = (
                f"[{index}] {citation}\n"
                f"{snippet}"
            )

            if current_length + len(part) > self._MAX_CONTEXT_CHARS:
                break
            parts.append(part)
            current_length += len(part)

        header = (
            f"Use ONLY these {len(parts)} sources. "
            "Cite each fact with its source number in square brackets, e.g. [1].\n\n"
        )
        return header + "\n\n---\n\n".join(parts)

    def _build_extractive_fallback(
        self,
        query: str,
        relevant_chunks: list[Document],
        user_language: str,
    ) -> str:
        """Build a deterministic extraction-style answer when LLM use is unavailable.

        Uses numbered citations matching _build_context numbering.
        """
        sentences = self._select_relevant_sentences(query, relevant_chunks)

        # Map sentences back to their source chunk index for inline citation
        citation_map: dict[str, int] = {}
        for chunk_idx, chunk in enumerate(relevant_chunks, start=1):
            for sentence in self._split_sentences(chunk.page_content):
                if sentence not in citation_map:
                    citation_map[sentence] = chunk_idx

        cited_sentences: list[str] = []
        for sentence in sentences[:2]:
            chunk_num = citation_map.get(sentence, 1)
            cited_sentences.append(f"{sentence} [{chunk_num}]")

        used_source_indices = sorted(
            {citation_map[s] for s in sentences[:2] if s in citation_map}
        )
        used_sources = [
            f"[{i}] {self._format_source_label(relevant_chunks[i - 1].metadata)}"
            for i in used_source_indices
            if i <= len(relevant_chunks)
        ] or [
            f"[{i}] {self._format_source_label(chunk.metadata)}"
            for i, chunk in enumerate(relevant_chunks[:3], start=1)
        ]

        if user_language == "hindi":
            explanation_heading = "**सीधा उत्तर**"
            meaning_heading = "**आपके लिए क्या मतलब है**"
            sources_heading = "**स्रोत**"
            explanation = (
                f"आपका प्रश्न: {query}\n\n" + " ".join(cited_sentences)
                if cited_sentences
                else f"'{query}' के बारे में सत्यापित जानकारी स्रोतों में उपलब्ध नहीं है।"
            )
            meaning = (
                "निर्णय लेने से पहले मूल दस्तावेज़ देखें।"
                if cited_sentences
                else "कृपया अधिक स्पष्ट प्रश्न पूछें।"
            )
        elif user_language == "tamil":
            explanation_heading = "**நேரடி பதில்**"
            meaning_heading = "**இது உங்களுக்கு என்ன அர்த்தம்**"
            sources_heading = "**மூலங்கள்**"
            explanation = (
                f"உங்கள் கேள்வி: {query}\n\n" + " ".join(cited_sentences)
                if cited_sentences
                else f"'{query}' பற்றிய தகவல் ஆதாரங்களில் கிடைக்கவில்லை."
            )
            meaning = (
                "அசல் ஆவணத்தை முதலில் பார்க்கவும்."
                if cited_sentences
                else "மேலும் தெளிவான கேள்வி கேளுங்கள்."
            )
        else:
            explanation_heading = "**Direct Answer**"
            meaning_heading = "**What This Means For You**"
            sources_heading = "**Sources**"
            explanation = (
                f"Your question: {query}\n\n" + " ".join(cited_sentences)
                if cited_sentences
                else f"The verified sources do not contain specific information about: '{query}'"
            )
            meaning = (
                "Check the original source before taking action."
                if cited_sentences
                else "Please ask a more specific question or add relevant documents."
            )

        # Note: Sources are now managed separately by the frontend
        # No longer appending sources to the answer text

        return (
            f"{explanation_heading}\n{explanation}\n\n"
            f"{meaning_heading}\n{meaning}"
        ).strip()

    def _build_no_information_fallback(self, user_language: str) -> str:
        """Return a language-aware fallback when verified information is unavailable."""
        if user_language == "hindi":
            return (
                "**सीधा उत्तर**\n"
                "मुझे दिए गए सत्यापित स्रोत अंशों में इस प्रश्न का भरोसेमंद उत्तर नहीं मिला।\n\n"
                "**आपके लिए क्या मतलब है**\n"
                "मैं बिना स्रोत के उत्तर नहीं दूँगा। कृपया अधिक स्पष्ट प्रश्न पूछें।"
            )
        if user_language == "tamil":
            return (
                "**நேரடி பதில்**\n"
                "கொடுக்கப்பட்ட சரிபார்க்கப்பட்ட ஆதாரங்களில் நம்பகமான பதில் கிடைக்கவில்லை.\n\n"
                "**இது உங்களுக்கு என்ன அர்த்தம்**\n"
                "ஆதாரம் இல்லாமல் பதில் அளிக்கமாட்டேன். தயவுசெய்து தெளிவான கேள்வி கேளுங்கள்."
            )
        return (
            "**Direct Answer**\n"
            "I could not find a reliable answer in the verified retrieved sources.\n\n"
            "**What This Means For You**\n"
            "I will not guess without source support. Please ask a more specific question "
            "or add relevant documents."
        )

    def _build_sources(self, chunks: list[Document]) -> list[dict[str, Any]]:
        """Convert chunk metadata into clean source dicts with citation index, URLs, descriptions."""
        sources: list[dict[str, Any]] = []
        seen_sources: set[str] = set()

        for index, chunk in enumerate(chunks, start=1):
            metadata = chunk.metadata
            source_name = str(metadata.get("source", ""))

            if source_name in seen_sources:
                continue
            seen_sources.add(source_name)

            source_info = OFFICIAL_SOURCES_INFO.get(source_name, {})

            source_item = {
                "citation_index": index,           # maps to [N] in the answer
                "source": source_name,
                "title": source_info.get("title", str(metadata.get("title", source_name))),
                "url": source_info.get("url", ""),
                "domain": source_info.get("domain", str(metadata.get("domain", "general"))),
                "description": source_info.get("description", ""),
                "ministry": source_info.get("ministry", ""),
                "content_type": str(metadata.get("content_type", "")),
                "published_date": (
                    str(metadata.get("published_date", ""))
                    if metadata.get("published_date")
                    else ""
                ),
                "language": str(metadata.get("language", "")) if metadata.get("language") else "",
                "chunk_index": self._safe_int(metadata.get("chunk_index"), default=0),
                "total_chunks": self._safe_int(metadata.get("total_chunks"), default=0),
                "similarity_score": round(
                    self._safe_float(metadata.get("similarity_score"), default=0.0), 6
                ),
            }
            sources.append(source_item)

        return sources

    def _compute_confidence(self, chunks: list[Document]) -> float:
        """Compute a lightweight confidence score from similarity metadata."""
        if not chunks:
            return 0.0

        scores = [
            self._safe_float(chunk.metadata.get("similarity_score"), default=-1.0)
            for chunk in chunks
            if chunk.metadata.get("similarity_score") is not None
        ]

        if not scores:
            return 0.35 if chunks else 0.0

        bounded_scores = [min(max(score, 0.0), 1.0) for score in scores]
        average_score = sum(bounded_scores) / len(bounded_scores)
        coverage_bonus = min(len(chunks), 3) * 0.05
        return round(min(average_score + coverage_bonus, 0.99), 3)

    def _select_relevant_sentences(
        self,
        query: str,
        chunks: list[Document],
    ) -> list[str]:
        """Select the most relevant chunk sentences using keyword overlap."""
        query_terms = self._tokenize(query)
        candidates: list[tuple[float, str]] = []

        for chunk in chunks:
            for sentence in self._split_sentences(chunk.page_content):
                overlap = self._keyword_overlap_ratio(query_terms, sentence)

                has_numbers = bool(re.search(r'\d+', sentence))
                has_currency = bool(re.search(r'Rs\.|rupees|amount|fee|cost', sentence, re.IGNORECASE))
                has_time = bool(re.search(r'\d+\s*(day|days|hour|hours|month|months|year|years)', sentence, re.IGNORECASE))

                detail_boost = 0.15 if (has_currency or has_time or has_numbers) else 0
                boosted_score = min(overlap + detail_boost, 1.0)

                if overlap > 0 or detail_boost > 0:
                    candidates.append((boosted_score, sentence))

        if not candidates:
            for chunk in chunks:
                first_sentence = self._split_sentences(chunk.page_content)
                if first_sentence:
                    return [first_sentence[0]]
            return []

        candidates.sort(key=lambda item: (-item[0], -len(item[1])))
        selected: list[str] = []

        for _, sentence in candidates:
            if sentence not in selected:
                selected.append(sentence)
            if len(selected) >= 3:
                break

        return selected

    def _extract_jargon_terms(self, answer: str) -> list[str]:
        """Extract likely jargon terms from an answer string."""
        patterns = [
            r"\b[A-Z]{2,}(?:-[A-Z0-9]+)?\b",
            r"\bSection\s+\d+[A-Z]?\b",
            r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}\b",
        ]

        found_terms: list[str] = []
        seen: set[str] = set()

        for pattern in patterns:
            for match in re.findall(pattern, answer or ""):
                term = self._normalize_text(match)
                key = term.lower()
                if len(term) < 3 or key in seen:
                    continue
                seen.add(key)
                found_terms.append(term)
                if len(found_terms) >= self._MAX_JARGON_TERMS:
                    return found_terms

        return found_terms

    def _format_source_label(self, metadata: dict[str, Any]) -> str:
        """Format a compact source label from chunk metadata."""
        title = str(metadata.get("title", "")).strip()
        source = str(metadata.get("source", "")).strip()
        chunk_index = metadata.get("chunk_index")
        published_date = str(metadata.get("published_date", "")).strip()

        parts = [part for part in [title or source, published_date] if part]
        label = " | ".join(parts) if parts else "Unknown source"

        if chunk_index is not None:
            label = f"{label} | chunk {self._safe_int(chunk_index, default=0)}"

        return label

    def _normalize_answer(self, answer: Any) -> str:
        """Normalize model output and enforce non-empty string behavior."""
        text = self._normalize_text(str(answer or ""))
        if not text:
            return ""
        return text

    def _normalize_language(self, language: str) -> str:
        """Normalize a language label with safe defaults."""
        normalized = self._normalize_text(language).lower()
        return normalized or config.default_language.lower()

    def _sanitize_metadata(self, metadata: dict[str, Any] | None) -> dict[str, Any]:
        """Convert metadata into serializable primitive values."""
        if not metadata:
            return {}

        sanitized: dict[str, Any] = {}
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                sanitized[str(key)] = value
            elif isinstance(value, (list, tuple, set)):
                sanitized[str(key)] = [self._serialize_scalar(item) for item in value]
            elif isinstance(value, dict):
                sanitized[str(key)] = {
                    str(sub_key): self._serialize_scalar(sub_value)
                    for sub_key, sub_value in value.items()
                }
            else:
                sanitized[str(key)] = str(value)

        return sanitized

    def _serialize_scalar(self, value: Any) -> Any:
        """Serialize nested metadata values into JSON-compatible scalars."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (list, tuple, set)):
            return [self._serialize_scalar(item) for item in value]
        if isinstance(value, dict):
            return {
                str(sub_key): self._serialize_scalar(sub_value)
                for sub_key, sub_value in value.items()
            }
        return str(value)

    def _normalize_text(self, text: str) -> str:
        """Normalize whitespace in text."""
        return re.sub(r"\s+", " ", text or "").strip()

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into simple sentences."""
        raw_sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return [sentence.strip() for sentence in raw_sentences if sentence.strip()]

    def _tokenize(self, text: str) -> set[str]:
        """Tokenize text into lowercase alphanumeric terms."""
        normalized = "".join(
            character.lower() if character.isalnum() else " " for character in text or ""
        )
        return {token for token in normalized.split() if len(token) > 1}

    def _keyword_overlap_ratio(self, query_terms: set[str], text: str) -> float:
        """Compute a lightweight keyword overlap ratio."""
        if not query_terms:
            return 0.0
        text_terms = self._tokenize(text)
        if not text_terms:
            return 0.0
        overlap = len(query_terms.intersection(text_terms))
        return overlap / max(len(query_terms), 1)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """Safely convert values to float."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _generate_follow_up_questions(self, query: str, answer: str, guide: str) -> list[str]:
        """Generate 3 contextual, action-oriented follow-up questions using SmartFollowUpGenerator."""
        if not answer or "not found" in answer.lower() or "not available" in answer.lower():
            return []

        # Use smart follow-up generator for contextual questions
        smart_generator = SmartFollowUpGenerator()
        follow_ups = smart_generator.generate(
            query=query,
            answer=answer,
            detected_type=None  # Auto-detect from content
        )
        
        return follow_ups[:3]  # Return top 3 questions

    def _safe_int(self, value: Any, default: int = 0) -> int:
        """Safely convert values to int."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default