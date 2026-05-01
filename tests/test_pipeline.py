"""End-to-end pipeline tests for Samajh."""

import pytest

from langchain_core.documents import Document

from backend.pipeline import pipeline
from backend.ingestion.chunker import chunk_documents
from backend.embeddings.embedder import MultilingualEmbedder


@pytest.fixture(scope="module")
def sample_data():
    """Populate test Chroma with 3 sample docs."""

    embedder = MultilingualEmbedder()

    # Mock RSS entry
    rss_doc = Document(
        page_content="RTI Act 2005 allows citizens to request information from public authorities. File online or offline.",
        metadata={"source": "pib.gov.in", "title": "RTI Guide", "domain": "law", "language": "english"}
    )

    # Mock PDF page
    pdf_doc = Document(
        page_content="Repo rate is the rate at which RBI lends to banks. Current repo rate 6.5%. When repo rate increases, loan EMIs rise.",
        metadata={"source": "rbi.org.in", "title": "Monetary Policy", "domain": "finance", "language": "english"}
    )

    # Mock web
    web_doc = Document(
        page_content="आयुष्मान भारत योजना गरीब परिवारों को 5 लाख तक का मुफ्त स्वास्थ्य बीमा देती है। सरकारी और निजी अस्पतालों में कैशलेस उपचार।",
        metadata={"source": "mohfw.gov.in", "title": "Ayushman Bharat", "domain": "health", "language": "hindi"}
    )

    docs = [rss_doc, pdf_doc, web_doc]
    chunks = chunk_documents(docs, chunk_size=300, overlap=20)

    embeddings = embedder.embed_chunks(chunks)
    pipeline.vectorstore.add_chunks(chunks, [emb for _, emb in embeddings])

    return True


def test_pipeline_english(sample_data):
    response = pipeline.answer_question("What is RTI act and how do I use it?", language="english", domain="law")
    assert response["confidence"] > 0.1
    assert "RTI" in response["answer"]
    assert len(response["sources"]) > 0
    assert response["language"] == "english"


def test_pipeline_hindi(sample_data):
    response = pipeline.answer_question("रेपो रेट क्या है?", language="hindi", domain="finance")
    assert "repo" in response["answer"].lower()
    assert response["language"] == "hindi"


def test_pipeline_tamil(sample_data):
    response = pipeline.answer_question("ஆயுஷ்மான் பாரத் திட்டம்?", language="tamil", domain="health")
    assert response["language"] in {"tamil", "english"}
    assert len(response["sources"]) > 0


def test_pipeline_no_results(sample_data):
    response = pipeline.answer_question("Quantum physics in Mars", language="english")
    assert "no relevant" in response["answer"].lower() or response["confidence"] < 0.3


def test_jargon_annotation(sample_data):
    response = pipeline.answer_question("Explain repo rate and RTI", language="english")
    annotated = response.get("annotated_answer", "")
    assert "**repo rate**" in annotated or "**RTI**" in annotated
    assert isinstance(response["explanations"], list)

