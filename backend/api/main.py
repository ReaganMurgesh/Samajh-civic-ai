"""FastAPI application entry point for the Samajh platform."""

from __future__ import annotations

from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

from backend.utils.config import config


class AskRequest(BaseModel):
    query: str
    language: Optional[str] = None
    domain: Optional[str] = None
    guide: Optional[str] = "general"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config.validate()

    app = FastAPI(
        title="Samajh API",
        description="Multilingual RAG civic intelligence platform for Indian citizens.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if config.app_env != "production" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health_check() -> dict:
        """Return a basic health response for local development."""
        return {
            "status": "ok",
            "app_env": config.app_env,
            "default_language": config.default_language,
            "supported_languages": config.supported_languages,
            "supported_domains": config.supported_domains,
        }

    from backend.pipeline import pipeline
    from backend.jargon.jargon_engine import jargon_engine

    @app.post("/api/ask")
    async def ask(question: AskRequest = Body(...)):
        """Generate RAG answer for query with guide-specific persona."""
        response = pipeline.answer_question(
            query=question.query,
            language=question.language,
            domain=question.domain,
            guide=question.guide or "general"
        )
        return response

    @app.get("/api/guides")
    async def list_guides():
        """List all available guide personas."""
        from backend.generator.guide_personas import list_guides
        return {
            "guides": list_guides(),
            "description": "Choose a guide that matches your need: general (all topics), legal (rights & laws), farmer (agriculture), health (schemes & wellness)"
        }

    @app.get("/api/jargon/{term}")
    async def get_jargon(term: str, language: str = "english"):
        """Get jargon explanation."""
        expl = jargon_engine.explain_term(term, language)
        return expl or {"error": f"Term '{term}' not found"}

    @app.get("/api/diag/jargon")
    async def jargon_diagnostics() -> Dict[str, Any]:
        """Return development diagnostics for loaded jargon dictionaries."""
        terms_by_dictionary = {
            name: len(terms)
            for name, terms in jargon_engine.dictionaries.items()
        }
        sample_terms = []
        for terms in jargon_engine.dictionaries.values():
            sample_terms.extend(list(terms.keys())[:5])

        return {
            "status": "ok",
            "dictionary_count": len(jargon_engine.dictionaries),
            "total_terms": sum(terms_by_dictionary.values()),
            "terms_by_dictionary": terms_by_dictionary,
            "sample_terms": sample_terms[:15],
        }

    @app.post("/api/feedback")
    async def feedback(fb: Dict[str, str]):
        """Store user feedback."""
        # TODO: Log to DB/Langfuse
        print(f"Feedback: {fb}")
        return {"status": "thanks", "received": True}

    @app.get("/api/feeds/status")
    async def feeds_status():
        """Feed ingestion status."""
        return {
            "feeds_count": 8,
            "domains": config.supported_domains,
            "last_update": "manual_run_required"
        }

    return app



app = create_app()
