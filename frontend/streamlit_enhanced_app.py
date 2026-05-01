"""
SAMAJH - Simple Chat Interface v3.0
Base version with Official Database mode only
Clean, minimal design like Gemini
"""

import streamlit as st
from datetime import datetime
from typing import Optional, List
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.omni_router import SamajhOmniRouter
from backend.pipeline import SamajhPipeline
from backend.jargon.jargon_engine import JargonEngine

# ============================================
# PAGE CONFIG & MINIMAL THEME
# ============================================

st.set_page_config(
    page_title="SAMAJH - Ask Anything",
    page_icon="🏛️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Minimal CSS - Clean and Simple
st.markdown("""
<style>
    body, .main {
        background-color: #ffffff;
        color: #202124;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    .header-simple {
        text-align: center;
        padding: 20px 0;
        border-bottom: 1px solid #dadce0;
        margin-bottom: 20px;
    }
    
    .header-simple h1 {
        margin: 0;
        font-size: 24px;
        font-weight: 500;
    }
    
    .header-simple p {
        margin: 8px 0 0 0;
        color: #5f6368;
        font-size: 14px;
    }
    
    .chat-container {
        max-height: 500px;
        overflow-y: auto;
        padding: 0;
        margin-bottom: 20px;
    }
    
    .message-user {
        display: flex;
        justify-content: flex-end;
        margin-bottom: 12px;
    }
    
    .message-user-bubble {
        background-color: #6366f1;
        color: white;
        padding: 12px 16px;
        border-radius: 18px;
        max-width: 70%;
        word-wrap: break-word;
        font-size: 14px;
    }
    
    .message-bot {
        display: flex;
        justify-content: flex-start;
        margin-bottom: 12px;
    }
    
    .message-bot-bubble {
        background-color: #f0f0f0;
        color: #202124;
        padding: 12px 16px;
        border-radius: 18px;
        max-width: 70%;
        word-wrap: break-word;
        font-size: 14px;
        line-height: 1.5;
    }
    
    .input-section {
        border-top: 1px solid #dadce0;
        padding-top: 16px;
    }
    
    ::-webkit-scrollbar {
        width: 6px;
    }
    
    ::-webkit-scrollbar-track {
        background: transparent;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #d3d3d3;
        border-radius: 3px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #999;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# INITIALIZATION
# ============================================

@st.cache_resource
def initialize_system():
    """Initialize system components."""
    router = SamajhOmniRouter()
    router.set_mode(SamajhOmniRouter.MODE_OFFICIAL_DB)
    pipeline = SamajhPipeline()
    jargon_engine = JargonEngine()
    return router, pipeline, jargon_engine

router, pipeline, jargon_engine = initialize_system()

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []


# ============================================
# DISPLAY FUNCTIONS
# ============================================

def display_chat_message(message: dict):
    """Display a chat message (user or bot) - Clean Perplexity-style UI."""
    if message["role"] == "user":
        # User message
        with st.chat_message("user", avatar="👤"):
            st.markdown(message["content"])
    else:
        # Bot response - Assistant message
        with st.chat_message("assistant", avatar="🏛️"):
            answer = message.get("answer", message.get("content", "No answer generated"))
            sources = message.get("sources", [])
            
            # 1. Display main answer first (clean and prominent)
            st.markdown(answer)
            
            # 2. Create ONE single, neat expander for sources and verification
            with st.expander("📚 View Sources & Verification", expanded=False):
                # Warning/Note
                st.caption("⚠️ **Note:** This is official government information. Always verify important details before acting on this information.")
                
                st.divider()
                
                # List the sources cleanly
                if sources:
                    st.markdown("**📖 Official Sources:**")
                    for i, source in enumerate(sources[:2], 1):  # Show only top 2
                        title = source.get("title") or source.get("name", "Official Document")
                        ministry = source.get("ministry", "Government Source")
                        url = source.get("url", "")
                        description = source.get("description", "")
                        
                        st.markdown(f"""
                        **Source {i}: {title}**  
                        🏛️ *{ministry}*
                        """)
                        
                        if description:
                            st.caption(description)
                        
                        if url:
                            st.markdown(f"[🔗 Read Full Document]({url})")
                        
                        st.divider()
                else:
                    st.caption("No specific documents cited for this query.")

# ============================================
# MAIN INTERFACE
# ============================================


# ============================================
# MAIN UI
# ============================================

# Header
st.markdown("""
<div class="header-simple">
    <h1>🏛️ SAMAJH</h1>
    <p>Ask about Indian government laws, policies, and schemes</p>
</div>
""", unsafe_allow_html=True)

# Chat area - display messages
if st.session_state.chat_history:
    for message in st.session_state.chat_history:
        display_chat_message(message)
else:
    st.info("""
    **Welcome to SAMAJH!** 👋
    
    Ask me anything about:
    - Government schemes & benefits
    - Laws & constitutional rights
    - Taxes & finance
    - Consumer protection & human rights
    - Education policies & welfare programs
    """)

st.divider()

# Input section

# Helpful tips
st.markdown("""
<div style="background-color: #f0f0f0; padding: 10px; border-radius: 6px; margin-bottom: 12px; font-size: 12px; color: #5f6368;">
💡 <strong>How to Ask:</strong> "What is RTI?", "How to apply for PM-KISAN?", "What are my tax benefits?" 
</div>
""", unsafe_allow_html=True)

# Simple input
user_input = st.text_input(
    "Your question",
    placeholder="Ask anything about government laws and schemes...",
    label_visibility="collapsed"
)

# Send button
if st.button("Send", use_container_width=True):
    if user_input:
        # Add user message
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_input
        })
        
        # Get response from pipeline
        try:
            with st.spinner("Searching..."):
                response = pipeline.answer_question(
                    query=user_input,
                    language="english",
                    guide="general"
                )
                
                # Store the full response for display
                st.session_state.chat_history.append({
                    "role": "bot",
                    "answer": response.get("answer", "No answer found"),
                    "sources": response.get("sources", []),
                    "full_response": response
                })
                
                st.rerun()
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.session_state.chat_history.pop()  # Remove user message on error

st.divider()

# Footer
st.markdown("""
<div style="text-align: center; color: #5f6368; font-size: 12px; margin-top: 30px; padding-top: 10px; border-top: 1px solid #dadce0;">
<strong>💡 Need simpler explanation?</strong> Ask your question differently or request "Explain in simple terms"
</div>
""", unsafe_allow_html=True)
