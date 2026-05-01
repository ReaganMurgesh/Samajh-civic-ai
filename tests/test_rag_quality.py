"""Tests for evaluating RAG generation quality and hallucination guardrails."""

import pytest
from langchain_core.documents import Document
from backend.generator.hallucination_guard import guard

def test_hallucination_guard_grounded():
    """Test that the guard passes an answer directly extracted from sources."""
    answer = "The Repo Rate is used to control inflation by lending money."
    chunks = [
        Document(page_content="The repo rate is the rate at which the Reserve Bank lends money. It helps control inflation.")
    ]
    result = guard.verify_grounding(answer, chunks)
    assert result["is_grounded"] is True
    assert result["score"] >= 0.5

def test_hallucination_guard_hallucinated():
    """Test that the guard catches an answer with external unverified information."""
    answer = "RTI was passed in 2005 by Manmohan Singh. You can file it on the website."
    chunks = [
        Document(page_content="The Right to Information (RTI) Act allows citizens to request information.")
    ]
    result = guard.verify_grounding(answer, chunks)
    # The answer introduces "2005", "Manmohan", "Singh", "website" which are not in chunks
    assert result["is_grounded"] is False

def test_hallucination_guard_empty():
    """Test behavior with empty inputs."""
    result = guard.verify_grounding("", [Document(page_content="text")])
    assert result["is_grounded"] is True
    
    result = guard.verify_grounding("Some answer", [])
    assert result["is_grounded"] is False
