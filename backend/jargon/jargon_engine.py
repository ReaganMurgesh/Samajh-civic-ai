"""Jargon detection and explanation engine for Samajh."""

import json
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path
import re


LOGGER = logging.getLogger(__name__)


class JargonEngine:
    """Loads jargon dictionaries and provides explanation services."""

    def __init__(self, dict_dir: str = "data/jargon_dict") -> None:
        self.dict_dir = Path(dict_dir)
        self.dictionaries: Dict[str, Dict[str, Dict]] = {}
        self._patterns_cache: List[tuple[re.Pattern, str]] = []
        self._load_dictionaries()

    def _load_dictionaries(self) -> None:
        """Load all JSON jargon files from dict_dir."""
        for json_file in self.dict_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    category = json_file.stem  # e.g., 'legal_terms'
                    raw_data = json.load(f)
                    normalized: Dict[str, Dict] = {}

                    if isinstance(raw_data, dict):
                        for term, payload in raw_data.items():
                            if isinstance(term, str) and isinstance(payload, dict):
                                normalized[term.lower()] = payload
                            else:
                                LOGGER.warning("Skipping malformed jargon entry in %s", json_file.name)
                    elif isinstance(raw_data, list):
                        for item in raw_data:
                            if not isinstance(item, dict):
                                LOGGER.warning("Skipping non-dict item in %s", json_file.name)
                                continue
                            term_value = item.get("term")
                            if isinstance(term_value, str) and term_value.strip():
                                normalized[term_value.strip().lower()] = item
                            else:
                                LOGGER.warning("Skipping list item missing string 'term' in %s", json_file.name)
                    else:
                        LOGGER.warning("Unsupported jargon JSON format in %s", json_file.name)

                    self.dictionaries[category] = normalized
            except Exception as e:
                LOGGER.warning("Could not load %s: %s", json_file, e)

        self._patterns_cache = self._build_search_patterns()

    def detect_jargon(self, text: str) -> List[str]:
        """Detect jargon terms present in text across all dictionaries."""

        if not isinstance(text, str) or not text.strip():
            return []

        found_terms = set()
        patterns = self._patterns_cache or self._build_search_patterns()
        for pattern, term in patterns:
            if pattern.search(text):
                found_terms.add(term)

        return sorted(list(found_terms))

    def _build_search_patterns(self) -> List[tuple[re.Pattern, str]]:
        """Build regex patterns for all jargon terms."""

        patterns = []
        for cat_dict in self.dictionaries.values():
            for term in cat_dict.keys():
                if not isinstance(term, str) or not term.strip():
                    continue
                escaped = re.escape(term)
                pattern_str = r'\b' + escaped + r'\b'
                pattern = re.compile(pattern_str, re.IGNORECASE)
                patterns.append((pattern, term))
        return patterns

    def explain_term(self, term: str, language: str = "english") -> Optional[Dict]:
        """Get explanation for a term in specified language."""

        language = language.lower()
        term_key = term.lower()
        for cat_dict in self.dictionaries.values():
            if term_key in cat_dict:
                expl_key = f"plain_{language}"
                explanation = cat_dict[term_key].get(expl_key)
                if explanation:
                    return {
                        "term": term,
                        "plain_explanation": explanation,
                        "example": cat_dict[term_key].get("example", ""),
                        "source": cat_dict[term_key].get("source", "")
                    }
        return None

    def annotate_answer(self, answer: str, language: str = "english") -> Dict[str, Any]:
        """Annotate answer: detect jargon, add explanations."""

        if not isinstance(answer, str):
            answer = str(answer or "")

        jargon_terms = self.detect_jargon(answer)
        explanations = []
        for term in jargon_terms:
            expl = self.explain_term(term, language)
            if expl:
                explanations.append(expl)

        annotated = answer
        for term in jargon_terms:
            annotated = re.sub(r'\b' + re.escape(term) + r'\b', f"**{term}**", annotated, flags=re.IGNORECASE)

        return {
            "annotated_answer": annotated,
            "jargon_terms": jargon_terms,
            "explanations": explanations
        }


# Global instance
jargon_engine = JargonEngine()

