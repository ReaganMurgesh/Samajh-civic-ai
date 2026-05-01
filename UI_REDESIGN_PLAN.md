# SAMAJH UI Redesign Plan

## Overview
Redesign the Streamlit app with:
1. **Top navbar** instead of sidebar for mode selection
2. **Suggested questions** (10+) from ChromaDB for Official DB mode
3. **Enhanced UI** for each mode with Indian color design
4. **Different algorithms** for each mode

## Color Scheme (Indian Colors)
- **Saffron**: #FF9933
- **White**: #FFFFFF  
- **Green**: #138808
- **Blue**: #1F41B5
- **Dark Background**: #0f172a
- **Cards Background**: #1a2540

## Layout Structure

### 1. Header/Navbar (Full Width)
- SAMAJH logo on left
- Three mode buttons in center (Official DB | Upload Doc | Live Search)
- Settings icon on right
- Active mode indicator

### 2. Content Area

#### Mode 1: Official Database (🏛️)
- **Left Panel (40%):**
  - Search box at top
  - Suggested questions list (10+ questions)
  - Each question clickable
  
- **Right Panel (60%):**
  - Chat interface
  - Q&A bubbles
  - Show detailed PDF info when answers provided

#### Mode 2: Upload Document (📄)
- **Top Section:**
  - File uploader
  - File status indicator
  
- **Bottom Section:**
  - Search box
  - Chat interface with document-specific Q&A

#### Mode 3: Live Web Search (🌐)
- **Search box** at top
- **Chat interface** showing:
  - Web results
  - Generated answer
  - Related sources
  - Follow-up questions

## Features to Implement

### Suggested Questions Generator
- Extract key topics from ChromaDB documents
- Generate 10+ natural language questions
- Rank by relevance to user's potential needs
- Update dynamically as conversation progresses

### Official DB Mode Algorithm
1. Retrieve relevant documents from ChromaDB
2. Extract key information
3. Generate suggested questions
4. When user clicks question → Execute RAG pipeline
5. Display answer with document citations

### Upload Doc Mode Algorithm
1. Ingest PDF into memory
2. Create temporary embeddings
3. Generate questions from uploaded doc
4. Execute in-memory RAG
5. Display document-specific answers

### Live Search Mode Algorithm
1. Execute web search via DuckDuckGo
2. Extract relevant information
3. Generate answer via Groq
4. Display results with sources
5. Suggest follow-up questions

## File Changes
- `frontend/streamlit_omni_app_v2.py` - New app with redesigned UI
- `backend/suggested_questions_generator.py` - New module for Q generation
