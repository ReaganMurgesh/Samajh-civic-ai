"""
SAMAJH - Perplexity-Style Omni-Search for Indian Civic Information
Seamlessly combines local ChromaDB + Gemini Live Web Search
+ Do It For Me: Official Document Drafting Engine
"""

import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.pipeline import process_query, OmniSearchAgent, pipeline

# --- STREAMLIT CONFIG ---
st.set_page_config(
    page_title="SAMAJH | Civic Intelligence",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for Perplexity-style UI
st.markdown("""
<style>
    .block-container { padding-top: 2rem; max-width: 900px; }
    
    .source-chip {
        background-color: #f0f0f0;
        padding: 12px;
        border-radius: 8px;
        font-size: 0.85rem;
        border: 1px solid #e0e0e0;
        transition: all 0.2s;
    }
    
    .source-chip:hover {
        background-color: #e8e8e8;
        border-color: #6366f1;
    }
    
    .samajh-header {
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .samajh-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    .samajh-subtitle {
        color: #666;
        font-size: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown(
    """
    <div class='samajh-header'>
        <div class='samajh-title'>🏛️ SAMAJH</div>
        <div class='samajh-subtitle'>Understand Indian Civic Life • Laws, Schemes & Rights</div>
    </div>
    """,
    unsafe_allow_html=True
)

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="👤" if message["role"] == "user" else "🏛️"):
        st.markdown(message["content"])
        
        # If it's an assistant message with sources and follow-ups, display them
        if message["role"] == "assistant" and "sources" in message:
            st.markdown("---")
            st.markdown("##### 📚 Sources")
            cols = st.columns(3)
            for i, source in enumerate(message["sources"][:3]):
                col = cols[i % 3]
                with col:
                    st.markdown(f"""
                    <div class="source-chip">
                        <b>[{i+1}] {source.get('title', 'Untitled')}</b><br>
                        <span style="color: #666; font-size: 0.8rem;">{source.get('domain', 'Unknown')}</span>
                    </div>
                    """, unsafe_allow_html=True)
            
            if "follow_ups" in message and message["follow_ups"]:
                st.markdown("---")
                st.markdown("##### 🔎 Related Questions")
                for q in message["follow_ups"]:
                    if st.button(f"↗ {q}", key=f"followup_{message.get('id', hash(q))}_{q}", use_container_width=True):
                        st.session_state.follow_up_query = q

# User Input
if prompt := st.chat_input("Ask anything about Indian laws, schemes, and rights...", key="main_input"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🏛️"):
        with st.spinner("🤔 Searching SAMAJH Database and the Web..."):
            try:
                response_data = process_query(prompt)
                
                answer_text = response_data.get("answer", "No answer found.")
                st.markdown(answer_text)
                
                sources = response_data.get("sources", [])
                follow_ups = response_data.get("follow_ups", [])
                
                if sources:
                    st.markdown("---")
                    st.markdown("##### 📚 Sources")
                    cols = st.columns(3)
                    for i, source in enumerate(sources[:3]):
                        col = cols[i % 3]
                        with col:
                            url = source.get("url", "#")
                            title = source.get("title", "Document")
                            domain = source.get("domain", "Source")
                            
                            st.markdown(f"""
                            <div class="source-chip">
                                <b>[{i+1}] <a href="{url}" target="_blank" style="color: #6366f1; text-decoration: none;">{title}</a></b><br>
                                <span style="color: #666; font-size: 0.8rem;">{domain}</span>
                            </div>
                            """, unsafe_allow_html=True)
                
                if follow_ups:
                    st.markdown("---")
                    st.markdown("##### 🔎 Related Questions")
                    for i, q in enumerate(follow_ups):
                        if st.button(f"↗ {q}", key=f"followup_{i}_{q}", use_container_width=True):
                            st.session_state.follow_up_query = q
                            st.rerun()
                
                # --- NEW: TAKE ACTION SECTION (DRAFTING ENGINE) ---
                st.markdown("---")
                st.markdown("##### 📝 Take Action")
                st.caption("Need to submit this to the government? Let SAMAJH draft the official document for you.")
                
                # Initialize agent for drafting
                agent = OmniSearchAgent(pipeline)
                
                # Get suggested document type based on the user's question
                suggested_type = agent.detect_document_type(prompt)
                templates = agent.get_draft_templates()
                
                # Create two-column layout for drafting options
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    # Document type selector
                    selected_template_name = st.selectbox(
                        "📋 Choose action type:",
                        options=[t["name"] for t in templates.values()],
                        index=list(templates.keys()).index(suggested_type),
                        key=f"doc_selector_{len(st.session_state.messages)}"
                    )
                    selected_type = [k for k, v in templates.items() if v["name"] == selected_template_name][0]
                
                with col2:
                    draft_btn = st.button("✍️ Draft Now", type="primary", key=f"draft_btn_{len(st.session_state.messages)}", use_container_width=True)
                
                if draft_btn:
                    with st.spinner(f"🖊️  Drafting {templates[selected_type]['name'].lower()}..."):
                        try:
                            draft_result = agent.generate_draft_document(
                                user_issue=prompt,
                                document_type=selected_type
                            )
                            
                            if draft_result.get("success"):
                                st.success("✅ Document drafted successfully!")
                                
                                # Display the draft in a formatted box
                                st.markdown("---")
                                st.markdown("**📄 Your Official Document:**")
                                st.markdown(f"""
                                <div style="
                                    background-color: #f8f9fa;
                                    border: 2px solid #6366f1;
                                    border-radius: 10px;
                                    padding: 20px;
                                    font-family: 'Courier New', monospace;
                                    font-size: 0.9rem;
                                    line-height: 1.6;
                                    color: #333;
                                    max-height: 400px;
                                    overflow-y: auto;
                                ">
                                {draft_result['document_text'].replace(chr(10), '<br>')}
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Download button
                                st.download_button(
                                    label="📥 Download as Text File",
                                    data=draft_result["document_text"],
                                    file_name=f"SAMAJH_{draft_result['template_name'].replace(' ', '_')}.txt",
                                    mime="text/plain",
                                    key=f"download_{len(st.session_state.messages)}"
                                )
                                
                                # Copy to clipboard info
                                st.info("💡 Tip: You can copy the text above and paste it into a Word document for formatting, or print it directly!")
                            else:
                                st.error(f"❌ Error generating document: {draft_result.get('error', 'Unknown error')}")
                        
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer_text,
                    "sources": sources,
                    "follow_ups": follow_ups,
                    "id": len(st.session_state.messages)
                })
                
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

if "follow_up_query" in st.session_state:
    query = st.session_state.follow_up_query
    del st.session_state.follow_up_query
    st.session_state.messages.append({"role": "user", "content": query})
    st.rerun()

st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #999; font-size: 0.85rem;'>🏛️ SAMAJH • Official Government Information + Live Web Search</p>",
    unsafe_allow_html=True
)
