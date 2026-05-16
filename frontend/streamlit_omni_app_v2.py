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
    /* Deep Dark Background */
    [data-testid="stAppViewContainer"] {
        background-color: #121212;
        color: #EDEDED;
    }

    /* Themed Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1A1A1D !important;
        border-right: 1px solid #333 !important;
    }

    /* Clean Chat Input with Orange Focus */
    [data-testid="stChatInputContainer"] {
        background-color: #1E1E24 !important;
        border: 1px solid #444 !important;
        border-radius: 10px;
    }

    /* SAMAJH Assistant Chat Bubble */
    [data-testid="chatAvatarIcon-assistant"] {
        background-color: #FF6B35; /* Vibrant Orange */
        color: white;
    }
    .stChatMessage {
        background-color: transparent;
        padding: 1.5rem;
        border-radius: 8px;
    }
    
    /* Highlight the AI's response to separate it from the user */
    .stChatMessage:has([data-testid="chatAvatarIcon-assistant"]) {
        background-color: rgba(255, 107, 53, 0.05); /* Very faint orange tint */
        border-left: 4px solid #FF6B35;
    }

    /* Follow-up Buttons (matching Top Navigation modes / Streamlit buttons) */
    .stButton>button {
        border-radius: 8px !important;
        transition: 0.3s;
        border: 1px solid #444 !important;
        background-color: #1A1A1D !important;
        color: #EDEDED !important;
        padding: 12px;
        font-weight: 600;
    }
    .stButton>button:hover {
        border-color: #FF6B35 !important;
        color: #FF6B35 !important;
    }

    /* Source Chips */
    .source-chip { 
        background-color: #1E1E24; 
        padding: 12px; 
        border-radius: 8px; 
        font-size: 0.85rem; 
        border: 1px solid #333; 
        margin-bottom: 10px; 
        border-left: 3px solid #666;
    }
    
    /* Global Typography */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif !important;
    }
    
    /* Logo Symbol Header */
    .brand-container {
        display: flex;
        align-items: center;
        gap: 15px;
        padding: 5px 0;
        margin-bottom: 20px;
    }
    .brand-icon {
        font-size: 36px;
        color: #FF6B35;
        filter: drop-shadow(0 2px 4px rgba(255,107,53,0.3));
    }
    .brand-text-block {
        display: flex;
        flex-direction: column;
    }
    .brand-title {
        font-size: 28px;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: 0.5px;
        line-height: 1.1;
    }
    .brand-subtitle {
        font-size: 12px;
        font-weight: 500;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 2px;
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

col1, col2, col3, col4, col5 = st.columns([1.2, 1.5, 1.5, 1.5, 1])

with col1:
    st.markdown('''
        <div class="brand-container">
            <div class="brand-icon">🏛️</div>
            <div class="brand-text-block">
                <span class="brand-title">SAMAJH</span>
                <span class="brand-subtitle">Civic Info Platform</span>
            </div>
        </div>
    ''', unsafe_allow_html=True)

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
