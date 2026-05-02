"""
SAMAJH Omni-Platform - Redesigned UI with Top Navigation
- Official Database (🏛️) - with suggested questions
- Document Upload (📄) - enhanced RAG analysis
- Live Web Search (🌐) - real-time results
"""

import streamlit as st
from datetime import datetime
from typing import Optional
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.omni_router import SamajhOmniRouter
from backend.document_handler import StreamlitDocumentSession
from backend.pipeline import SamajhPipeline
from backend.jargon.jargon_engine import JargonEngine
from backend.generator.suggested_questions import suggested_questions_gen
from backend.vectorstore.chroma_store import SamajhVectorStore

# ============================================
# PAGE CONFIG
# ============================================

st.set_page_config(
    page_title="SAMAJH - Civic Information Platform",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================
# INDIAN COLOR DESIGN THEME
# ============================================

st.markdown("""
<style>
    /* Indian Colors: Saffron, White, Green */
    :root {
        --saffron: #FF9933;
        --white: #FFFFFF;
        --green: #138808;
        --blue: #1F41B5;
        --dark-bg: #0f172a;
        --card-bg: #1a2540;
        --text-light: #f1f5f9;
    }
    
    body, .main {
        background: linear-gradient(135deg, #0f172a 0%, #1a2540 100%);
        color: #f1f5f9;
    }
    
    /* Top Navigation Bar */
    .navbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 20px 30px;
        background: linear-gradient(90deg, rgba(255, 153, 51, 0.95) 0%, rgba(31, 65, 181, 0.95) 50%, rgba(19, 136, 8, 0.95) 100%);
        border-bottom: 3px solid #FF9933;
        border-radius: 0;
        margin-bottom: 30px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    
    .navbar-logo {
        font-size: 28px;
        font-weight: 800;
        color: white;
        text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.5);
    }
    
    .navbar-modes {
        display: flex;
        gap: 15px;
        justify-content: center;
        flex: 1;
    }
    
    .mode-btn {
        padding: 12px 20px;
        border: 2px solid white;
        background: rgba(255, 255, 255, 0.1);
        color: white;
        border-radius: 8px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
        font-size: 14px;
    }
    
    .mode-btn:hover {
        background: rgba(255, 255, 255, 0.2);
        transform: translateY(-2px);
    }
    
    .mode-btn.active {
        background: white;
        color: #FF9933;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    
    /* Suggested Questions Panel */
    .questions-panel {
        background: linear-gradient(135deg, rgba(255, 153, 51, 0.1) 0%, rgba(31, 65, 181, 0.1) 100%);
        border-left: 4px solid #FF9933;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
    }
    
    .questions-title {
        font-size: 18px;
        font-weight: 700;
        color: #FF9933;
        margin-bottom: 15px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .question-button {
        display: block;
        width: 100%;
        padding: 12px 15px;
        margin: 8px 0;
        background: rgba(255, 153, 51, 0.15);
        border: 1px solid #FF9933;
        border-radius: 6px;
        color: #f1f5f9;
        text-align: left;
        cursor: pointer;
        transition: all 0.2s ease;
        font-size: 14px;
        line-height: 1.4;
    }
    
    .question-button:hover {
        background: rgba(255, 153, 51, 0.3);
        border-color: #FF9933;
        transform: translateX(5px);
    }
    
    .question-button.active {
        background: #FF9933;
        color: #0f172a;
        border-color: #FF9933;
        font-weight: 600;
    }
    
    /* Chat Messages */
    .user-message {
        background: linear-gradient(135deg, #FF9933 0%, #FF9933 100%);
        color: white;
        padding: 12px 16px;
        border-radius: 12px 12px 0 12px;
        margin: 12px 0;
        text-align: right;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }
    
    .bot-message {
        background: rgba(31, 65, 181, 0.15);
        color: #f1f5f9;
        padding: 12px 16px;
        border-radius: 12px 12px 12px 0;
        margin: 12px 0;
        border-left: 4px solid #1F41B5;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }
    
    .bot-message.web {
        border-left-color: #138808;
        background: rgba(19, 136, 8, 0.15);
    }
    
    /* Answer Section */
    .answer-section {
        background: linear-gradient(135deg, rgba(31, 65, 181, 0.1) 0%, rgba(19, 136, 8, 0.1) 100%);
        border: 2px solid rgba(31, 65, 181, 0.3);
        border-radius: 8px;
        padding: 20px;
        margin: 15px 0;
    }
    
    .answer-title {
        font-size: 16px;
        font-weight: 700;
        color: #FF9933;
        margin-bottom: 10px;
        text-transform: uppercase;
    }
    
    /* File Upload */
    .upload-section {
        background: linear-gradient(135deg, rgba(19, 136, 8, 0.1) 0%, rgba(31, 65, 181, 0.1) 100%);
        border: 2px dashed #138808;
        border-radius: 8px;
        padding: 20px;
        text-align: center;
        margin: 20px 0;
    }
    
    /* PDF Info Cards */
    .pdf-info-card {
        background: rgba(255, 153, 51, 0.1);
        border-left: 4px solid #FF9933;
        border-radius: 6px;
        padding: 12px;
        margin: 8px 0;
        font-size: 12px;
    }
    
    .pdf-title {
        font-weight: 600;
        color: #FF9933;
    }
    
    .pdf-meta {
        color: #a0a0a0;
        font-size: 11px;
    }
    
    /* Status Indicators */
    .status-processing {
        color: #FF9933;
        font-weight: 600;
    }
    
    .status-success {
        color: #138808;
        font-weight: 600;
    }
    
    .status-error {
        color: #ef4444;
        font-weight: 600;
    }
    
    /* Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #FF9933 0%, #FF9933 100%);
        color: white;
        border: none;
        font-weight: 600;
        border-radius: 6px;
        padding: 10px 20px;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, #FF7722 0%, #FF7722 100%);
        transform: translateY(-2px);
    }
    
    .stSelectbox, .stTextInput {
        color: #f1f5f9;
    }
    
    /* Footer */
    .footer {
        text-align: center;
        padding: 20px;
        color: #a0a0a0;
        border-top: 1px solid rgba(255, 153, 51, 0.2);
        margin-top: 40px;
    }
    
    .footer-logo {
        font-size: 20px;
        font-weight: 700;
        background: linear-gradient(90deg, #FF9933, #1F41B5, #138808);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# INITIALIZATION
# ============================================

@st.cache_resource
def initialize_system():
    """Initialize RAG pipeline and components."""
    router = SamajhOmniRouter()
    pipeline = SamajhPipeline()
    jargon_engine = JargonEngine()
    vectorstore = SamajhVectorStore(persist_dir="./chromadb")
    return router, pipeline, jargon_engine, vectorstore

router, pipeline, jargon_engine, vectorstore = initialize_system()

# Initialize session state
if 'current_mode' not in st.session_state:
    st.session_state.current_mode = SamajhOmniRouter.MODE_OFFICIAL_DB

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'document_session' not in st.session_state:
    st.session_state.document_session = StreamlitDocumentSession(st.session_state)
    st.session_state.document_session.initialize()

if 'suggested_questions' not in st.session_state:
    st.session_state.suggested_questions = []

# NEW: Track if first question was asked in Official DB mode
if 'questions_shown' not in st.session_state:
    st.session_state.questions_shown = True  # Show questions initially

if 'conversation_title' not in st.session_state:
    st.session_state.conversation_title = None

document_session = st.session_state.document_session

# ============================================
# HELPER FUNCTIONS
# ============================================

def save_conversation(title: Optional[str] = None):
    """Save conversation history to JSON file."""
    if not st.session_state.chat_history:
        st.warning("No conversation to save!")
        return
    
    filename = title or f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    filepath = Path("./data/conversations") / f"{filename}.json"
    
    # Create conversations directory if it doesn't exist
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    conversation_data = {
        "title": title or filename,
        "mode": st.session_state.current_mode,
        "timestamp": datetime.now().isoformat(),
        "messages": [
            {
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": msg.get("timestamp", "").isoformat() if hasattr(msg.get("timestamp"), "isoformat") else str(msg.get("timestamp", ""))
            }
            for msg in st.session_state.chat_history
        ]
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(conversation_data, f, indent=2, ensure_ascii=False)
    
    return filepath

def clear_conversation():
    """Clear current conversation."""
    st.session_state.chat_history = []
    st.session_state.questions_shown = True
    st.session_state.suggested_questions = []
    st.rerun()

# ============================================
# TOP NAVBAR
# ============================================

col1, col2, col3, col4, col5 = st.columns([1, 1.5, 1.5, 1.5, 1])

with col1:
    st.markdown('<div class="navbar-logo">🏛️ SAMAJH</div>', unsafe_allow_html=True)

with col2:
    if st.button(
        "🏛️ Official Database",
        key="mode_official",
        use_container_width=True,
        help="Access 1,403 government documents indexed in our database"
    ):
        st.session_state.current_mode = SamajhOmniRouter.MODE_OFFICIAL_DB
        st.session_state.chat_history = []
        st.rerun()

with col3:
    if st.button(
        "📄 Upload Document",
        key="mode_upload",
        use_container_width=True,
        help="Analyze your own PDF documents using RAG"
    ):
        st.session_state.current_mode = SamajhOmniRouter.MODE_UPLOAD_DOC
        st.session_state.chat_history = []
        st.rerun()

with col4:
    if st.button(
        "🌐 Live Web Search",
        key="mode_web",
        use_container_width=True,
        help="Search live web for latest information"
    ):
        st.session_state.current_mode = SamajhOmniRouter.MODE_LIVE_WEB
        st.session_state.chat_history = []
        st.rerun()

with col5:
    st.markdown("")  # Spacer

st.markdown("---")

# ============================================
# MODE 1: OFFICIAL DATABASE
# ============================================

if st.session_state.current_mode == SamajhOmniRouter.MODE_OFFICIAL_DB:
    st.markdown("### 🏛️ Official Government Database | 1,403+ Indexed Documents")
    
    # Generate suggested questions on first load
    if not st.session_state.suggested_questions:
        with st.spinner("📚 Loading suggested questions from database..."):
            try:
                # Get sample documents from vectorstore
                sample_docs = vectorstore.get_sample_documents(limit=50)
                all_docs_text = "\n".join([doc.page_content for doc in sample_docs if doc.page_content])
                
                if all_docs_text and len(all_docs_text) > 100:
                    st.session_state.suggested_questions = suggested_questions_gen.generate_from_documents(
                        all_docs_text, num_questions=12
                    )
                else:
                    st.session_state.suggested_questions = suggested_questions_gen._get_fallback_questions()
            except Exception as e:
                print(f"Error generating questions: {e}")
                st.session_state.suggested_questions = suggested_questions_gen._get_fallback_questions()
    
    # Show suggested questions panel only if no chat history yet
    if st.session_state.questions_shown and len(st.session_state.chat_history) == 0:
        # SUGGESTED QUESTIONS SECTION
        st.markdown('<div class="questions-panel">', unsafe_allow_html=True)
        st.markdown('<div class="questions-title">💡 Suggested Questions</div>', unsafe_allow_html=True)
        st.markdown('<p style="color: #a0a0a0; font-size: 12px; margin-bottom: 15px;">Click any question to start exploring</p>', unsafe_allow_html=True)
        
        # Create grid of questions
        cols = st.columns(2)
        for idx, question in enumerate(st.session_state.suggested_questions):
            col = cols[idx % 2]
            with col:
                if st.button(
                    f"❓ {question}",
                    key=f"suggested_q_{idx}",
                    use_container_width=True,
                    help=f"Click to search"
                ):
                    st.session_state.execute_query = question
                    st.session_state.questions_shown = False
                    st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # CONVERSATION CONTROLS (shown after first question or anytime)
    if len(st.session_state.chat_history) > 0:
        col_save, col_new, col_settings = st.columns([0.35, 0.35, 0.30])
        
        with col_save:
            if st.button("💾 Save Conversation", use_container_width=True, key="btn_save_official"):
                save_name = datetime.now().strftime("chat_%Y%m%d_%H%M%S")
                saved_path = save_conversation(save_name)
                st.success(f"✅ Conversation saved: {saved_path.name}")
        
        with col_new:
            if st.button("🔄 New Conversation", use_container_width=True, key="btn_new_official"):
                clear_conversation()
        
        with col_settings:
            language = st.selectbox("Language:", ["English", "Hindi", "Mixed"], key="lang_official", label_visibility="collapsed")
    else:
        # Show settings when no chat yet
        col_lang, col_guide = st.columns(2)
        with col_lang:
            language = st.selectbox("Language:", ["English", "Hindi", "Mixed"], key="lang_official")
        with col_guide:
            guide = st.selectbox("Guide Persona:", ["General", "Legal", "Farmer", "Health"], key="guide_official")
    
    st.markdown("---")
    
    # CHAT INTERFACE (full width)
    st.markdown("### 💬 Conversation Window")
    
    # Chat container with better styling
    chat_container = st.container()
    with chat_container:
        if len(st.session_state.chat_history) == 0:
            st.markdown("""
            <div style="text-align: center; padding: 40px 20px; color: #a0a0a0;">
                <p style="font-size: 18px; margin-bottom: 20px;">📝 No conversation yet</p>
                <p style="font-size: 14px;">Select a suggested question above or ask your own question below to start</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            for message_idx, message in enumerate(st.session_state.chat_history):
                if message["role"] == "user":
                    st.markdown(f'<div class="user-message">👤 <strong>You:</strong> {message["content"]}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="bot-message">🤖 <strong>SAMAJH:</strong></div>', unsafe_allow_html=True)
                    
                    response = message.get("response", {})
                    st.markdown(response.get("answer", ""))
                    
                    # Show PDF sources
                    if response.get("sources"):
                        with st.expander("📄 Document Sources"):
                            for src in response["sources"][:3]:
                                st.markdown(f'<div class="pdf-info-card">', unsafe_allow_html=True)
                                st.markdown(f'<div class="pdf-title">{src.get("title", "Document")}</div>', unsafe_allow_html=True)
                                st.markdown(f'<div class="pdf-meta">Domain: {src.get("domain", "General")}</div>', unsafe_allow_html=True)
                                st.markdown(f'</div>', unsafe_allow_html=True)
                    
                    # Show follow-up questions for this answer
                    follow_ups = response.get("follow_up_questions", [])
                    if follow_ups:
                        st.markdown("""
                        <div style="margin-top: 15px; padding: 12px; background: rgba(255, 153, 51, 0.08); border-radius: 8px; border-left: 3px solid #FF9933;">
                            <p style="margin: 0 0 10px 0; font-weight: 600; color: #FF9933; font-size: 14px;">💡 Related Questions:</p>
                        """, unsafe_allow_html=True)
                        
                        # Display follow-ups in 2-column grid
                        followup_cols = st.columns(2)
                        for followup_idx, followup in enumerate(follow_ups[:4]):  # Show top 4 follow-ups
                            followup_col = followup_cols[followup_idx % 2]
                            with followup_col:
                                if st.button(
                                    f"❓ {followup}",
                                    key=f"followup_{message_idx}_{followup_idx}_{hash(followup) % 10000}",
                                    use_container_width=True,
                                    help="Click to ask this question"
                                ):
                                    st.session_state.execute_query = followup
                                    st.rerun()
                        
                        st.markdown("</div>", unsafe_allow_html=True)
    
    # Input area
    st.markdown("---")
    st.markdown("#### ❓ Ask Your Question")
    
    col_input, col_btn = st.columns([0.85, 0.15])
    
    with col_input:
        user_query = st.text_input(
            "🔍 Type your question...",
            placeholder="e.g., How to apply for PM-KISAN? | What is RTI? | Benefits of Ayushman Bharat?",
            label_visibility="collapsed",
            key="input_official"
        )
    
    with col_btn:
        send_btn = st.button("📤 Ask", use_container_width=True, key="btn_official")
    
    # Get language and guide from sidebar if chat history exists
    if len(st.session_state.chat_history) > 0:
        guide = st.selectbox("Guide Persona:", ["General", "Legal", "Farmer", "Health"], key="guide_official_chat")
    
    # Process query
    is_execute = "execute_query" in st.session_state
    if is_execute:
        user_query = st.session_state.pop("execute_query")
        send_btn = True
    
    if (send_btn and user_query) or is_execute:
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_query,
            "timestamp": datetime.now()
        })
        
        try:
            response = pipeline.answer_question(
                query=user_query,
                language=language.lower(),
                guide=guide.lower()
            )
            response["mode"] = st.session_state.current_mode
            
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": response.get("answer", "No response"),
                "response": response,
                "mode": st.session_state.current_mode,
                "timestamp": datetime.now()
            })
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
        
        st.rerun()

# ============================================
# MODE 2: UPLOAD DOCUMENT
# ============================================

elif st.session_state.current_mode == SamajhOmniRouter.MODE_UPLOAD_DOC:
    st.markdown("### 📄 Upload & Analyze Your Document")
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a PDF, TXT, or Markdown file",
        type=["pdf", "txt", "md", "png", "jpg", "jpeg"],
        help="Upload documents to analyze with AI"
    )
    
    if uploaded_file:
        result = document_session.process_upload(uploaded_file)
        
        if result["success"]:
            # Load into pipeline if not already loaded for this file
            if st.session_state.get('loaded_doc_name') != uploaded_file.name:
                with st.spinner("Indexing document for AI analysis..."):
                    pipeline.load_document_chunks(result["chunks"])
                    st.session_state.loaded_doc_name = uploaded_file.name
                    
            st.success(f"✅ {result['summary_message']}")
            if "chunks" in result:
                st.info(f"📊 Extracted {result['num_chunks']} chunks ({result['text_length']} characters)")
            
            # Settings
            col1, col2 = st.columns(2)
            with col1:
                language = st.selectbox("Language:", ["English", "Hindi", "Mixed"], key="lang_upload")
            with col2:
                guide = st.selectbox("Guide Persona:", ["General", "Legal", "Farmer", "Health"], key="guide_upload")
            
            st.markdown("---")
            st.markdown("### 💬 Ask About Your Document")
            
            # Chat interface
            for message in st.session_state.chat_history:
                if message["role"] == "user":
                    st.markdown(f'<div class="user-message">👤 <strong>You:</strong> {message["content"]}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="bot-message">🤖 <strong>SAMAJH:</strong></div>', unsafe_allow_html=True)
                    response = message.get("response", {})
                    st.markdown(response.get("answer", ""))

                    # Show sources for this answer (if available)
                    if response.get("sources"):
                        with st.expander("📄 Document Sources"):
                            for src in response["sources"][:3]:
                                st.markdown(f'<div class="pdf-info-card">', unsafe_allow_html=True)
                                st.markdown(
                                    f'<div class="pdf-title">{src.get("title", "Document")}</div>',
                                    unsafe_allow_html=True,
                                )
                                st.markdown(
                                    f'<div class="pdf-meta">Source: {src.get("source", "")}</div>',
                                    unsafe_allow_html=True,
                                )
                                st.markdown(f'</div>', unsafe_allow_html=True)

                    # Show follow-up questions for this answer
                    follow_ups = response.get("follow_up_questions", [])
                    if follow_ups:
                        st.markdown(
                            """
                            <div style="margin-top: 15px; padding: 12px; background: rgba(255, 153, 51, 0.08); border-radius: 8px; border-left: 3px solid #FF9933;">
                                <p style="margin: 0 0 10px 0; font-weight: 600; color: #FF9933; font-size: 14px;">💡 Related Questions:</p>
                            """,
                            unsafe_allow_html=True,
                        )

                        followup_cols = st.columns(2)
                        for followup_idx, followup in enumerate(follow_ups[:4]):
                            followup_col = followup_cols[followup_idx % 2]
                            with followup_col:
                                if st.button(
                                    f"❓ {followup}",
                                    key=f"doc_followup_{hash((message.get('timestamp'), followup_idx, followup)) % 100000}",
                                    use_container_width=True,
                                    help="Click to ask this question",
                                ):
                                    st.session_state.execute_doc_query = followup
                                    st.rerun()

                        st.markdown("</div>", unsafe_allow_html=True)
            
            # Input
            with st.form("doc_upload_chat_form", clear_on_submit=True):
                col_input, col_btn = st.columns([0.85, 0.15])
                with col_input:
                    user_query = st.text_input(
                        "Ask about your document...",
                        placeholder="e.g., What are the main topics covered?",
                        label_visibility="collapsed",
                        key="input_upload"
                    )
                with col_btn:
                    send_btn = st.form_submit_button("📤 Ask", use_container_width=True)
                
                if send_btn and user_query:
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": user_query,
                        "timestamp": datetime.now()
                    })
                    
                    try:
                        response = pipeline.answer_from_document(
                            query=user_query,
                            language=language.lower(),
                            top_k=5
                        )
                        response["mode"] = st.session_state.current_mode
                        
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": response.get("answer", "No response"),
                            "response": response,
                            "mode": st.session_state.current_mode,
                            "timestamp": datetime.now()
                        })
                    except Exception as e:
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": f"❌ Error analyzing document: {str(e)}",
                            "response": {"answer": f"Error: {e}"},
                            "mode": st.session_state.current_mode,
                            "timestamp": datetime.now()
                        })
                    
                    st.rerun()

            # Also allow queued follow-up clicks to run the query outside the form
            if "execute_doc_query" in st.session_state:
                queued_query = st.session_state.pop("execute_doc_query")
                st.session_state.chat_history.append({
                    "role": "user",
                    "content": queued_query,
                    "timestamp": datetime.now()
                })

                try:
                    response = pipeline.answer_from_document(
                        query=queued_query,
                        language=language.lower(),
                        top_k=5
                    )
                    response["mode"] = st.session_state.current_mode

                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": response.get("answer", "No response"),
                        "response": response,
                        "mode": st.session_state.current_mode,
                        "timestamp": datetime.now()
                    })
                except Exception as e:
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"❌ Error analyzing document: {str(e)}",
                        "response": {"answer": f"Error: {e}"},
                        "mode": st.session_state.current_mode,
                        "timestamp": datetime.now()
                    })

                st.rerun()
        else:
            st.error(f"❌ {result.get('error', 'Upload failed')}")

# ============================================
# MODE 3: LIVE WEB SEARCH
# ============================================

elif st.session_state.current_mode == SamajhOmniRouter.MODE_LIVE_WEB:
    st.markdown("### 🌐 Live Web Search | Real-Time Government Information")
    
    col1, col2 = st.columns(2)
    with col1:
        language = st.selectbox("Language:", ["English", "Hindi"], key="lang_web")
    with col2:
        guide = st.selectbox("Guide Persona:", ["General", "Legal", "Farmer", "Health"], key="guide_web")
    
    st.info("🌐 **Powered by official civic web sources** | Returns current information with source references")
    
    st.markdown("---")
    st.markdown("### 💬 Ask Your Question")
    
    # Chat interface
    for message_idx, message in enumerate(st.session_state.chat_history):
        if message["role"] == "user":
            st.markdown(f'<div class="user-message">👤 <strong>You:</strong> {message["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="bot-message web">🤖 <strong>SAMAJH (Web Search):</strong></div>', unsafe_allow_html=True)
            response = message.get("response", {})
            st.markdown(response.get("answer", ""))

            if response.get("sources"):
                with st.expander("🔗 Web Sources"):
                    for src in response["sources"][:5]:
                        st.markdown(f'**{src.get("title", "Source")}**')
                        if src.get("url"):
                            st.markdown(f'[Open source]({src.get("url")})')
                        if src.get("description"):
                            st.caption(src.get("description"))

            follow_ups = response.get("follow_up_questions", [])
            if follow_ups:
                st.markdown("💡 Related Questions:")
                followup_cols = st.columns(2)
                for followup_idx, followup in enumerate(follow_ups[:4]):
                    followup_col = followup_cols[followup_idx % 2]
                    with followup_col:
                        if st.button(
                            f"❓ {followup}",
                            key=f"web_followup_{message_idx}_{followup_idx}_{hash(followup) % 100000}",
                            use_container_width=True,
                        ):
                            st.session_state.execute_web_query = followup
                            st.rerun()
    
    # Input
    col_input, col_btn = st.columns([0.85, 0.15])
    with col_input:
        user_query = st.text_input(
            "Search the web...",
            placeholder="e.g., Latest government schemes 2026",
            label_visibility="collapsed",
            key="input_web"
        )
    with col_btn:
        send_btn = st.button("🔍 Search", use_container_width=True, key="btn_web")
    
    if send_btn and user_query:
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_query,
            "timestamp": datetime.now()
        })
        
        try:
            response = pipeline.answer_from_web(
                query=user_query,
                language=language.lower()
            )
            response["mode"] = st.session_state.current_mode
            
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": response.get("answer", "No response"),
                "response": response,
                "mode": st.session_state.current_mode,
                "timestamp": datetime.now()
            })
        except Exception as e:
            st.error(f"❌ Search error: {str(e)}")
        
        st.rerun()

    if "execute_web_query" in st.session_state:
        queued_query = st.session_state.pop("execute_web_query")
        st.session_state.chat_history.append({
            "role": "user",
            "content": queued_query,
            "timestamp": datetime.now()
        })

        try:
            response = pipeline.answer_from_web(
                query=queued_query,
                language=language.lower()
            )
            response["mode"] = st.session_state.current_mode

            st.session_state.chat_history.append({
                "role": "assistant",
                "content": response.get("answer", "No response"),
                "response": response,
                "mode": st.session_state.current_mode,
                "timestamp": datetime.now()
            })
        except Exception as e:
            st.error(f"❌ Search error: {str(e)}")

        st.rerun()

# ============================================
# FOOTER
# ============================================

st.markdown("---")
st.markdown("""
<div class="footer">
    <div class="footer-logo">🏛️ SAMAJH</div>
    <p>Understand Government. Ask Questions. Get Answers.</p>
    <p style="font-size: 11px; margin-top: 10px;">
        <strong>🏛️</strong> Official Database | <strong>📄</strong> Upload Documents | <strong>🌐</strong> Live Search
    </p>
    <p style="font-size: 10px; color: #666; margin-top: 15px;">
        Made with ❤️ for Indian Citizens | Powered by Groq & ChromaDB
    </p>
</div>
""", unsafe_allow_html=True)
