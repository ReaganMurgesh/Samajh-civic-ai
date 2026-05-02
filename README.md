# 🏛️ SAMAJH

**SAMAJH** is a civic intelligence platform that helps users understand government information in simple language.

It supports three modes:

- **🏛️ Official Database** — ask questions about indexed government schemes, policies, and public documents
- **📄 Upload Document** — upload your own PDF, TXT, or Markdown file and ask questions about it
- **🌐 Live Web Search** — fetch current information from trusted web sources

The app is built with **Streamlit**, **Groq**, **ChromaDB**, and a retrieval-augmented generation pipeline.

---

## ✨ Highlights

- Context-aware answers grounded in retrieved sources
- Follow-up question suggestions for deeper exploration
- Source display for answers and document citations
- Support for uploaded documents with in-memory indexing
- Multilingual handling for civic and government content
- Robust PDF extraction with multiple fallbacks

---

## 📁 Project Structure

```text
backend/
  api/
  drafting/
  embeddings/
  generator/
  ingestion/
  jargon/
  notifications/
  retriever/
  utils/
  vectorstore/
frontend/
data/
tests/
scripts/
```

---

## 🚀 Run the App

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Start the Streamlit app

```bash
streamlit run frontend/streamlit_omni_app_v2.py
```

### 3) Open the app

```text
http://localhost:8501
```

---

## 🧪 Run Tests

```bash
pytest -q
```

---

## 📄 Document Upload Mode

Upload a supported file and ask questions such as:

- “What are the main topics covered?”
- “What are the eligibility criteria?”
- “What deadlines are mentioned?”

The app will:

- extract text from the file
- chunk and index it in an ephemeral vector store
- answer your question with cited context
- show follow-up questions for continued analysis

---

## 🏛️ Official Database Mode

Use this mode to ask questions about the built-in civic knowledge base, such as:

- welfare schemes
- legal rights
- health programs
- eligibility and application steps

Answers include source references and related follow-up questions.

---

## 🌐 Live Web Search Mode

This mode helps with current information by searching trusted online sources and returning a grounded response.

---

## ⚙️ Configuration

Create a `.env` file if needed and add your API key(s), for example:

```env
GROQ_API_KEY=your_key_here
```

Depending on the features you use, you may also need additional keys for web search or other integrations.

---

## 🛠️ Tech Stack

- **Frontend:** Streamlit
- **Backend:** Python
- **LLM:** Groq
- **Vector Store:** ChromaDB
- **Embeddings:** sentence-transformers
- **PDF Parsing:** pdfplumber, pypdf, pdfminer.six

---

## 📌 Notes

- Uploaded documents are handled in-memory for privacy.
- Follow-up questions are contextual rather than generic.
- Answers are designed to be source-grounded and easy to understand.

---

## 🧾 License

This project does not currently include a license file. Add one before public distribution if needed.
