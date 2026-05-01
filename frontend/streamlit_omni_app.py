"""
SAMAJH Omni-Platform - Beautiful 3-Mode UI
- Official Database (🏛️ SAMAJH Database)
- Document Upload (📄 My Document)
- Live Web Search (🌐 Live News)
"""

import streamlit as st
import asyncio
from datetime import datetime
from typing import Optional
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.omni_router import SamajhOmniRouter, QueryDispatcher
from backend.document_handler import StreamlitDocumentSession
from backend.pipeline import SamajhPipeline
from backend.jargon.jargon_engine import JargonEngine

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
        --primary-color: #6366f1;      /* Indigo */
        --secondary-color: #f59e0b;    /* Amber */
        --success-color: #10b981;      /* Green */
        --danger-color: #ef4444;       /* Red */
        --bg-dark: #0f172a;            /* Very dark slate */
        --bg-darker: #0a0f1f;          /* Even darker */
        --text-light: #f1f5f9;         /* Light slate */
    }
    
    body, .main {
        background-color: #0f172a;
        color: #f1f5f9;
    }
    
    /* Mode indicator badges */
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
    
    /* Source cards */
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
    
    /* Chat bubbles */
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
# INITIALIZATION
# ============================================

@st.cache_resource
def initialize_system():
    """Initialize RAG pipeline and router once."""
    router = SamajhOmniRouter()
    pipeline = SamajhPipeline()
    jargon_engine = JargonEngine()
    return router, pipeline, jargon_engine

# Initialize
router, pipeline, jargon_engine = initialize_system()

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'current_mode' not in st.session_state:
    st.session_state.current_mode = SamajhOmniRouter.MODE_OFFICIAL_DB

if 'document_session' not in st.session_state:
    st.session_state.document_session = StreamlitDocumentSession(st.session_state)
    st.session_state.document_session.initialize()

document_session = st.session_state.document_session

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_mode_emoji(mode: str) -> str:
    """Get emoji for mode."""
    emojis = {
        SamajhOmniRouter.MODE_OFFICIAL_DB: "🏛️",
        SamajhOmniRouter.MODE_UPLOAD_DOC: "📄",
        SamajhOmniRouter.MODE_LIVE_WEB: "🌐",
    }
    return emojis.get(mode, "❓")

def get_mode_color(mode: str) -> str:
    """Get color for mode."""
    colors = {
        SamajhOmniRouter.MODE_OFFICIAL_DB: "#6366f1",
        SamajhOmniRouter.MODE_UPLOAD_DOC: "#f59e0b",
        SamajhOmniRouter.MODE_LIVE_WEB: "#10b981",
    }
    return colors.get(mode, "#64748b")

def display_answer_with_sources(response: dict, mode: str, message_index: int = 0):
    """Display answer with beautiful formatting and mode-specific enhancements."""
    
    # Mode-specific header info
    if mode == SamajhOmniRouter.MODE_OFFICIAL_DB:
        st.caption("📚 Official Database | Indexed from 31+ government documents")
    elif mode == SamajhOmniRouter.MODE_UPLOAD_DOC:
        st.caption("📄 Document Analysis | Analysis based on your uploaded document")
        if response.get("warning"):
            st.warning(response["warning"])
    elif mode == SamajhOmniRouter.MODE_LIVE_WEB:
        st.caption("🌐 Live Web Search | Powered by Gemini 1.5 Flash with Google Search")
        if response.get("info"):
            st.info(response["info"])
    
    # Main answer
    st.markdown(f"**{get_mode_emoji(mode)} Answer:**")
    st.markdown(response.get("answer", "No answer generated"))
    
    # Brief explanation (if available from jargon engine)
    if "brief_explanation" in response and response["brief_explanation"]:
        with st.expander("?? **Brief Explanation**"):
            st.markdown(response["brief_explanation"])
                    
    # Suggested follow ups
    follow_ups = response.get("follow_up_questions", []) or response.get("suggested_follow_up_questions", [])
    if follow_ups:
        st.markdown("#### ?? Related Questions")
        cols = st.columns(len(follow_ups[:3]))
        for idx, q in enumerate(follow_ups[:3]):
            # Use message_index to ensure unique key across all messages
            unique_key = f"btn_{message_index}_{idx}_{hash(q) % 10000}"
            if cols[idx].button(q, key=unique_key):
                st.session_state.execute_query = q
                st.rerun()


def display_chat_message(message: dict, message_index: int = 0):
    """Display a chat message with proper styling."""
    if message["role"] == "user":
        st.markdown(f"""
        <div class="user-message">
            <strong>You:</strong> {message["content"]}
        </div>
        """, unsafe_allow_html=True)
    
    else:  # Bot message
        mode = message.get("mode", SamajhOmniRouter.MODE_OFFICIAL_DB)
        css_class = "bot-message"
        if mode == SamajhOmniRouter.MODE_UPLOAD_DOC:
            css_class += " upload"
        elif mode == SamajhOmniRouter.MODE_LIVE_WEB:
            css_class += " web"
        
        st.markdown(f"""
        <div class="{css_class}">
            <strong>{get_mode_emoji(mode)} SAMAJH</strong> ({mode})
        </div>
        """, unsafe_allow_html=True)
        
        response = message.get("response", {})
        display_answer_with_sources(response, mode, message_index)

# ============================================
# SIDEBAR - MODE SELECTOR & CONFIG
# ============================================

with st.sidebar:
    st.title("⚙️ SAMAJH Configuration")
    
    # Mode selector
    st.markdown("### 🎯 **Select Mode**")
    
    modes_info = router.get_all_modes_info()
    
    for mode_info in modes_info:
        if st.button(
            f"{mode_info['emoji']} {mode_info['title']}",
            use_container_width=True,
            key=f"btn_{mode_info['mode']}"
        ):
            st.session_state.current_mode = mode_info["mode"]
            router.set_mode(mode_info["mode"])
            st.rerun()
    
    # Current mode indicator
    current_config = router.get_mode_config(st.session_state.current_mode)
    st.markdown(f"""
    <div class="mode-badge mode-{st.session_state.current_mode.lower().replace(' ', '-')}">
        {current_config.get('emoji', '❓')} {st.session_state.current_mode}
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(current_config.get("description", ""))
    
    # Mode-specific UI
    st.markdown("---")
    
    if st.session_state.current_mode == SamajhOmniRouter.MODE_OFFICIAL_DB:
        st.markdown("### 📚 Database Settings")
        language = st.selectbox("Response Language:", ["English", "Hindi", "Mixed"], index=0)
        guide = st.selectbox("Guide Persona:", ["General", "Legal", "Farmer", "Health"], index=0)
    
    elif st.session_state.current_mode == SamajhOmniRouter.MODE_UPLOAD_DOC:
        st.markdown("### 📤 Upload Document")
        
        # File uploader
        uploaded_file = st.file_uploader(
            "Choose a file (PDF, TXT, MD, Image)",
            type=["pdf", "txt", "md", "png", "jpg", "jpeg"],
            help="Upload a document to analyze (max 50MB)"
        )
        
        if uploaded_file:
            # Process upload
            result = document_session.process_upload(uploaded_file)
            
            if result["success"]:
                st.success(f"✅ {result['summary_message']}")
                if "chunks" in result:
                    st.caption(f"📊 Extracted {result['num_chunks']} chunks ({result['text_length']} chars)")
            else:
                st.error(f"❌ {result.get('error', 'Upload failed')}")
        
        # Clear button
        if st.session_state.document_processed:
            if st.button("🗑️ Clear Document", use_container_width=True):
                document_session.clear_upload()
                st.rerun()
        
        language = st.selectbox("Response Language:", ["English", "Hindi", "Mixed"], index=0, key="language_upload")
        guide = st.selectbox("Guide Persona:", ["General", "Legal", "Farmer", "Health"], index=0, key="guide_upload")
    
    elif st.session_state.current_mode == SamajhOmniRouter.MODE_LIVE_WEB:
        st.markdown("### 🔍 Live Search Settings")
        language = st.selectbox("Response Language:", ["English", "Hindi"], index=0, key="language_web")
        guide = st.selectbox("Guide Persona:", ["General", "Legal", "Farmer", "Health"], index=0, key="guide_web")
        
        st.info("🌐 Searches live government websites and news sources for latest updates.")
    
    # Conversation history
    st.markdown("---")
    if st.button("🔄 New Conversation", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()
    
    if st.button("📥 Clear History", use_container_width=True):
        st.session_state.chat_history = []
        st.success("✅ History cleared")

# ============================================
# MAIN CONTENT AREA
# ============================================

# Header
st.markdown("""
<div style="text-align: center; margin-bottom: 30px;">
    <h1 style="margin: 0; color: #ff">🏛️ SAMAJH</h1>
    <p style="color: #a0a0a0; margin: 5px 0;">Civic Information Platform - Understand Government | Ask Questions | Get Answers</p>
</div>
""", unsafe_allow_html=True)

# Chat interface
st.markdown("### 💬 Conversation")

# Display chat history
for idx, message in enumerate(st.session_state.chat_history):
    display_chat_message(message, idx)

# Input area
st.markdown("---")

col1, col2 = st.columns([0.9, 0.1])

with col1:
    user_query = st.text_input(
        "🤔 Ask anything about Indian civic life...",
        placeholder="e.g., What is PM-KISAN? | How to file RTI? | What is new health scheme?",
        label_visibility="collapsed"
    )

with col2:
    send_button = st.button("📤 Ask", use_container_width=True)

# Process query
is_execute = st.session_state.pop("execute_query_flag", False)
if "execute_query" in st.session_state:
    user_query = st.session_state.pop("execute_query")
    is_execute = True

if (send_button and user_query) or (is_execute and user_query):
    # Add user message to history
    st.session_state.chat_history.append({
        "role": "user",
        "content": user_query,
        "timestamp": datetime.now()
    })
    
    # Check if upload mode and document is loaded
    current_mode = st.session_state.current_mode
    
    if current_mode == SamajhOmniRouter.MODE_UPLOAD_DOC:
        if not st.session_state.document_processed:
            st.error("❌ Please upload a document first in the sidebar, then ask your question.")
        else:
            # Use document-specific RAG pipeline
            try:
                response = pipeline.answer_from_document(
                    query=user_query,
                    language=language.lower(),
                    top_k=5
                )
                
                # Enhance response with mode info
                response["mode"] = current_mode
                response["warning"] = "⚠️ This analysis is based ONLY on your uploaded document, not government databases."
                
            except Exception as e:
                response = {
                    "answer": f"❌ Error analyzing document: {str(e)}",
                    "sources": [],
                    "mode": current_mode,
                    "follow_up_questions": [],
                    "confidence": 0.0,
                }
            
            # Add to history
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": response.get("answer", "No response"),
                "response": response,
                "mode": current_mode,
                "timestamp": datetime.now()
            })
    
    elif current_mode == SamajhOmniRouter.MODE_OFFICIAL_DB:
        # Query official database
        try:
            response = pipeline.answer_question(
                query=user_query,
                language=language.lower(),
                guide=guide.lower()
            )
            response["mode"] = current_mode
            
        except Exception as e:
            response = {
                "answer": f"❌ Error: {str(e)}",
                "sources": [],
                "mode": current_mode
            }
        
        # Add to history
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": response.get("answer", "No response"),
            "response": response,
            "mode": current_mode,
            "timestamp": datetime.now()
        })
    
    elif current_mode == SamajhOmniRouter.MODE_LIVE_WEB:
        # Query live web using Gemini with Google Search Grounding
        try:
            response = pipeline.answer_from_web(
                query=user_query,
                language=language.lower()
            )
            response["mode"] = current_mode
            response["info"] = "🌐 Powered by Gemini 1.5 Flash with Google Search Grounding"
            
        except Exception as e:
            response = {
                "answer": f"❌ Live search error: {str(e)}",
                "sources": [],
                "mode": current_mode,
                "follow_up_questions": [],
                "confidence": 0.0,
                "info": f"⚠️ {str(e)}"
            }
        
        # Add to history
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": response.get("answer", "No response"),
            "response": response,
            "mode": current_mode,
            "timestamp": datetime.now()
        })
    
    st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #64748b; font-size: 12px;">
    <p>SAMAJH - Understanding Civic India | Made with ❤️ for Indian Citizens</p>
    <p>🏛️ Official Database | 📄 Upload Documents | 🌐 Live Search</p>
</div>
""", unsafe_allow_html=True)

