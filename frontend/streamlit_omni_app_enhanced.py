"""
SAMAJH Omni-Platform - Enhanced 3-Mode UI with Document Suggestions
- Official Database (🏛️ SAMAJH Database) with document-based questions
- Document Upload (📄 My Document)
- Live Web Search (🌐 Live News) with government scheme websites
"""

import streamlit as st
import json
from datetime import datetime
from pathlib import Path
import sys
import os

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.omni_router import SamajhOmniRouter
from backend.document_handler import StreamlitDocumentSession
from backend.pipeline import SamajhPipeline
from backend.jargon.jargon_engine import JargonEngine
from backend.web_search_engine import search_government_websites, generate_web_answer, create_web_source_cards

# ============================================
# PAGE CONFIG & THEME
# ============================================

st.set_page_config(
    page_title="SAMAJH - Civic Information Platform",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom theme
st.markdown("""
<style>
    :root {
        --primary-color: #6366f1;
        --secondary-color: #f59e0b;
        --success-color: #10b981;
        --danger-color: #ef4444;
        --bg-dark: #0f172a;
        --bg-darker: #0a0f1f;
        --text-light: #f1f5f9;
    }
    
    body, .main {
        background-color: #0f172a;
        color: #f1f5f9;
    }
    
    .mode-badge {
        display: inline-block;
        padding: 8px 12px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 14px;
        margin: 8px 0;
    }
    
    .mode-official { background-color: rgba(99, 102, 241, 0.2); color: #a5b4fc; border-left: 3px solid #6366f1; }
    .mode-upload { background-color: rgba(245, 158, 11, 0.2); color: #fcd34d; border-left: 3px solid #f59e0b; }
    .mode-web { background-color: rgba(16, 185, 129, 0.2); color: #6ee7b7; border-left: 3px solid #10b981; }
    
    .source-card {
        background-color: #1a2540;
        border-left: 4px solid #6366f1;
        padding: 12px 16px;
        border-radius: 6px;
        margin: 8px 0;
        font-size: 14px;
    }
    
    .source-card-upload { border-left-color: #f59e0b; }
    .source-card-web { border-left-color: #10b981; }
    
    .suggested-question-btn {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        color: white;
        border: none;
        padding: 10px 15px;
        border-radius: 6px;
        margin: 4px;
        cursor: pointer;
        font-size: 13px;
        transition: all 0.3s;
    }
    
    .suggested-question-btn:hover {
        background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
        transform: translateY(-2px);
    }
    
    .user-message {
        background-color: #6366f1;
        color: white;
        padding: 12px 16px;
        border-radius: 12px 12px 0 12px;
        margin: 8px 0;
        margin-left: 100px;
        text-align: right;
    }
    
    .bot-message {
        background-color: #1a2540;
        color: #f1f5f9;
        padding: 12px 16px;
        border-radius: 12px 12px 12px 0;
        margin: 8px 0;
        margin-right: 100px;
        border-left: 3px solid #6366f1;
    }
    
    .bot-message.upload { border-left-color: #f59e0b; }
    .bot-message.web { border-left-color: #10b981; }
</style>
""", unsafe_allow_html=True)

# ============================================
# HELPER FUNCTIONS
# ============================================

@st.cache_resource
def initialize_system():
    """Initialize RAG pipeline and router once."""
    router = SamajhOmniRouter()
    pipeline = SamajhPipeline()
    jargon_engine = JargonEngine()
    return router, pipeline, jargon_engine

@st.cache_data
def load_document_metadata():
    """Load metadata with suggested questions for all documents."""
    metadata_path = Path("data/processed/document_metadata.json")
    if metadata_path.exists():
        try:
            with open(metadata_path) as f:
                return json.load(f)
        except:
            return {}
    return {}

def get_all_suggested_questions():
    """Extract all suggested questions from documents."""
    metadata = load_document_metadata()
    all_questions = []
    
    for doc_name, doc_info in metadata.items():
        if "suggested_questions" in doc_info:
            for question in doc_info["suggested_questions"]:
                all_questions.append({
                    "text": question,
                    "document": doc_info.get("title", doc_name),
                    "domain": doc_info.get("domain", "general"),
                    "icon": doc_info.get("icon", "📄")
                })
    
    return all_questions[:12]  # Return top 12

def get_mode_emoji(mode: str) -> str:
    """Get emoji for mode."""
    emojis = {
        SamajhOmniRouter.MODE_OFFICIAL_DB: "🏛️",
        SamajhOmniRouter.MODE_UPLOAD_DOC: "📄",
        SamajhOmniRouter.MODE_LIVE_WEB: "🌐",
    }
    return emojis.get(mode, "❓")

def display_answer_with_sources(response: dict, mode: str):
    """Display answer with beautiful formatting."""
    
    # Main answer
    st.markdown(f"**{get_mode_emoji(mode)} Answer:**")
    st.markdown(response.get("answer", "No answer generated"))
    
    # Sources
    sources = response.get("sources", [])
    if sources:
        if mode == SamajhOmniRouter.MODE_OFFICIAL_DB:
            # Simplified source display for offline mode
            with st.expander(f"📚 **Context from {len(sources)} source(s)**", expanded=False):
                seen_docs = set()
                for src in sources:
                    doc_name = src.get("title") or src.get("name") or "Unknown Document"
                    if doc_name not in seen_docs:
                        seen_docs.add(doc_name)
                        st.markdown(f"📄 **{doc_name}**")
        elif mode == SamajhOmniRouter.MODE_LIVE_WEB:
            # Rich source display for web mode
            with st.expander(f"🌐 **{len(sources)} Government Source(s)**", expanded=False):
                for i, src in enumerate(sources, 1):
                    title = src.get("title", "Document")
                    url = src.get("url", "")
                    description = src.get("description", "")
                    
                    source_html = f"""
                    <div class="source-card source-card-web">
                        <div style="font-weight: bold;">🔗 {title}</div>
                        {f'<div style="margin: 8px 0; line-height: 1.4;">{description}</div>' if description else ''}
                        {f'<div style="margin-top: 8px;"><a href="{url}" target="_blank" style="color: #60a5fa; text-decoration: none;">🌐 Visit Official Website →</a></div>' if url else ''}
                    </div>
                    """
                    st.markdown(source_html, unsafe_allow_html=True)
        else:
            # Upload mode
            with st.expander(f"📄 **Sources**"):
                for src in sources:
                    st.markdown(f"- {src.get('title', 'Source')}")
    
    # Suggested follow-ups
    follow_ups = response.get("follow_up_questions", [])
    if follow_ups and len(follow_ups) > 0:
        st.markdown("#### 💡 Related Questions")
        cols = st.columns(min(3, len(follow_ups)))
        for idx, q in enumerate(follow_ups[:3]):
            with cols[idx]:
                if st.button(q, key=f"followup_{q}_{len(st.session_state.chat_history)}"):
                    st.session_state.execute_query = q
                    st.rerun()

def display_chat_message(message: dict):
    """Display a chat message with proper styling."""
    if message["role"] == "user":
        st.markdown(f"""
        <div class="user-message">
            <strong>You:</strong> {message["content"]}
        </div>
        """, unsafe_allow_html=True)
    else:
        mode = message.get("mode", SamajhOmniRouter.MODE_OFFICIAL_DB)
        st.markdown(f"""
        <div class="bot-message">
            <strong>{get_mode_emoji(mode)} SAMAJH</strong> ({mode})
        </div>
        """, unsafe_allow_html=True)
        
        if "response" in message:
            display_answer_with_sources(message["response"], mode)

# ============================================
# INITIALIZATION
# ============================================

router, pipeline, jargon_engine = initialize_system()

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'current_mode' not in st.session_state:
    st.session_state.current_mode = SamajhOmniRouter.MODE_OFFICIAL_DB

if 'document_session' not in st.session_state:
    st.session_state.document_session = StreamlitDocumentSession(st.session_state)
    st.session_state.document_session.initialize()

document_session = st.session_state.document_session

# ============================================
# SIDEBAR CONFIGURATION
# ============================================

with st.sidebar:
    st.title("⚙️ SAMAJH Configuration")
    
    # Mode selector
    st.markdown("### 🎯 **Select Mode**")
    
    col1, col2, col3 = st.columns(3)
    
    if col1.button("🏛️ Database", use_container_width=True):
        st.session_state.current_mode = SamajhOmniRouter.MODE_OFFICIAL_DB
        st.rerun()
    
    if col2.button("📄 My Doc", use_container_width=True):
        st.session_state.current_mode = SamajhOmniRouter.MODE_UPLOAD_DOC
        st.rerun()
    
    if col3.button("🌐 Live Web", use_container_width=True):
        st.session_state.current_mode = SamajhOmniRouter.MODE_LIVE_WEB
        st.rerun()
    
    st.markdown("---")
    
    # Mode-specific settings
    current_mode = st.session_state.current_mode
    
    if current_mode == SamajhOmniRouter.MODE_OFFICIAL_DB:
        st.markdown("### 📚 Offline Database Settings")
        language = st.selectbox("Response Language:", ["English", "Hindi", "Mixed"], index=0, key="lang_db")
        guide = st.selectbox("Guide Persona:", ["General", "Legal", "Farmer", "Health"], index=0, key="guide_db")
        st.info("📖 Uses only verified government documents stored locally.")
    
    elif current_mode == SamajhOmniRouter.MODE_UPLOAD_DOC:
        st.markdown("### 📤 Upload Document")
        
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=["pdf", "txt", "md", "png", "jpg", "jpeg"],
            help="Upload document to analyze"
        )
        
        if uploaded_file:
            result = document_session.process_upload(uploaded_file)
            if result["success"]:
                st.success(f"✅ {result.get('summary_message', 'File uploaded')}")
            else:
                st.error(f"❌ {result.get('error', 'Upload failed')}")
        
        if st.session_state.document_processed:
            if st.button("🗑️ Clear Document", use_container_width=True):
                document_session.clear_upload()
                st.rerun()
        
        language = st.selectbox("Response Language:", ["English", "Hindi", "Mixed"], index=0, key="lang_doc")
        guide = st.selectbox("Guide Persona:", ["General", "Legal", "Farmer", "Health"], index=0, key="guide_doc")
    
    else:  # Live Web
        st.markdown("### 🔍 Live Search Settings")
        language = st.selectbox("Response Language:", ["English", "Hindi"], index=0, key="lang_web")
        guide = st.selectbox("Guide Persona:", ["General", "Legal", "Farmer", "Health"], index=0, key="guide_web")
        st.info("🌐 Searches live government websites for latest information.")
    
    # History controls
    st.markdown("---")
    if st.button("🔄 New Conversation", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

# ============================================
# MAIN CONTENT
# ============================================

st.markdown("""
<div style="text-align: center; margin-bottom: 30px;">
    <h1 style="margin: 0;">🏛️ SAMAJH</h1>
    <p style="color: #a0a0a0; margin: 5px 0;">Civic Information Platform - Understand Government</p>
</div>
""", unsafe_allow_html=True)

# Display suggested questions based on mode
if current_mode == SamajhOmniRouter.MODE_OFFICIAL_DB:
    st.markdown("### 💡 **Popular Questions from Documents**")
    suggested = get_all_suggested_questions()
    
    if suggested:
        # Group by domain for better organization
        domains = {}
        for q in suggested:
            domain = q["domain"]
            if domain not in domains:
                domains[domain] = []
            domains[domain].append(q)
        
        # Display in tabs by domain
        if len(domains) > 1:
            tabs = st.tabs([f"{q['icon']} {d.title()}" for d in domains.keys()])
            for tab, domain in zip(tabs, domains.keys()):
                with tab:
                    for q in domains[domain][:4]:
                        if st.button(f"→ {q['text']}", key=f"q_{q['text']}", use_container_width=True):
                            st.session_state.execute_query = q['text']
                            st.rerun()
        else:
            for q in suggested[:6]:
                if st.button(f"{q['icon']} {q['text']}", key=f"q_{q['text']}", use_container_width=True):
                    st.session_state.execute_query = q['text']
                    st.rerun()
    else:
        st.info("📚 No documents indexed yet. Run: `python ingest_local_documents.py --ingest-all`")

elif current_mode == SamajhOmniRouter.MODE_LIVE_WEB:
    st.markdown("### 🌐 **Popular Government Websites**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎯 My Scheme Portal", use_container_width=True):
            st.session_state.execute_query = "What government schemes am I eligible for?"
            st.rerun()
        if st.button("💰 Budget Information", use_container_width=True):
            st.session_state.execute_query = "What is the latest government budget news?"
            st.rerun()
    with col2:
        if st.button("🏥 Health Schemes", use_container_width=True):
            st.session_state.execute_query = "What are the latest health schemes?"
            st.rerun()
        if st.button("🌾 Farmer Schemes", use_container_width=True):
            st.session_state.execute_query = "What schemes are available for farmers?"
            st.rerun()

# Chat interface
st.markdown("---")
st.markdown("### 💬 **Conversation**")

for message in st.session_state.chat_history:
    display_chat_message(message)

# Input area
col1, col2 = st.columns([0.9, 0.1])

with col1:
    user_query = st.text_input(
        "Ask anything about Indian civic life...",
        placeholder="e.g., What is PM-KISAN? | How to file RTI? | Latest health schemes?",
        label_visibility="collapsed"
    )

with col2:
    send_button = st.button("📤", help="Send query")

# Process query
is_execute = st.session_state.pop("execute_query_flag", False)
if "execute_query" in st.session_state:
    user_query = st.session_state.pop("execute_query")
    is_execute = True

if (send_button and user_query) or (is_execute and user_query):
    # Add user message
    st.session_state.chat_history.append({
        "role": "user",
        "content": user_query,
        "timestamp": datetime.now()
    })
    
    current_mode = st.session_state.current_mode
    response = None
    
    try:
        if current_mode == SamajhOmniRouter.MODE_OFFICIAL_DB:
            lang = st.session_state.get("lang_db", "english").lower()
            gde = st.session_state.get("guide_db", "general").lower()
            
            response = pipeline.answer_question(
                query=user_query,
                language=lang,
                guide=gde
            )
            response["mode"] = current_mode
        
        elif current_mode == SamajhOmniRouter.MODE_UPLOAD_DOC:
            if not st.session_state.document_processed:
                response = {
                    "answer": "❌ Please upload a document first in the sidebar.",
                    "sources": [],
                    "mode": current_mode
                }
            else:
                lang = st.session_state.get("lang_doc", "english").lower()
                gde = st.session_state.get("guide_doc", "general").lower()
                
                response = pipeline.answer_question(
                    query=user_query,
                    language=lang,
                    guide=gde
                )
                response["mode"] = current_mode
        
        elif current_mode == SamajhOmniRouter.MODE_LIVE_WEB:
            lang = st.session_state.get("lang_web", "english").lower()
            gde = st.session_state.get("guide_web", "general").lower()
            
            # Use web search engine
            web_context = search_government_websites(user_query)
            response = generate_web_answer(user_query, web_context, lang)
            response["sources"] = create_web_source_cards(user_query)
            response["mode"] = current_mode
        
        else:
            response = {
                "answer": "❌ Unknown mode",
                "sources": [],
                "mode": current_mode
            }
    
    except Exception as e:
        response = {
            "answer": f"❌ Error: {str(e)}",
            "sources": [],
            "mode": current_mode
        }
    
    # Add response to history
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": response.get("answer", "No response"),
        "response": response,
        "mode": current_mode,
        "timestamp": datetime.now()
    })
    
    st.rerun()
