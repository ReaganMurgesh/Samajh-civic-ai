"""
SAMAJH — Omni-Platform RAG Civic Intelligence System
=====================================================
Architecture:
  • State Machine   : app_state ∈ {home, chat}
  • Session Manager : chat_sessions {uuid → session_dict}
  • Context Window  : last MAX_CONTEXT_PAIRS interactions sent to LLM
  • Tri-Mode Router : db | doc | web  (call_backend dispatcher)
  • Perplexity UI   : dark theme, inline citations, tucked source expanders
"""

from __future__ import annotations

import sys
import uuid
import time
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st

# ── Backend imports (graceful degradation) ───────────────────────────────────
try:
    from backend.pipeline import pipeline
    PIPELINE_AVAILABLE = True
except ImportError:
    PIPELINE_AVAILABLE = False

try:
    from backend.generator.guide_personas import list_guides
    GUIDES_AVAILABLE = True
except ImportError:
    GUIDES_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SAMAJH · Civic Intelligence",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Deep Dark Background */
    [data-testid="stAppViewContainer"] {
        background-color: #121212;
        color: #EDEDED;
    }

    /* Themed Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1A1A1D;
        border-right: 1px solid #333;
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

    /* Follow-up Buttons */
    .stButton>button {
        border-radius: 8px;
        transition: 0.3s;
        border: 1px solid #444;
        background-color: #1A1A1D;
    }
    .stButton>button:hover {
        border-color: #FF6B35;
        color: #FF6B35;
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
.src-num {
    flex-shrink: 0; width: 20px; height: 20px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 4px;
    display: flex; align-items: center; justify-content: center;
    font-family: 'DM Mono', monospace; font-size: 0.7rem;
    font-weight: 600; color: var(--accent);
}
.src-body { flex:1; min-width:0; }
.src-title { font-size: 0.84rem; font-weight: 600; color: var(--text); }
.src-meta  { font-size: 0.73rem; color: var(--muted); margin-top: 2px; }

/* ── Input ── */
.stTextInput > div > div > input {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    color: var(--text) !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.96rem !important;
    padding: 12px 16px !important;
    transition: border-color 0.15s;
}
.stTextInput > div > div > input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px rgba(255,107,53,0.12) !important;
}
.stTextInput > div > div > input::placeholder { color: var(--muted) !important; }

/* ── Primary buttons ── */
.stButton > button[kind="primary"] {
    background: var(--accent) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--radius) !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    transition: opacity 0.15s !important;
}
.stButton > button[kind="primary"]:hover { opacity: 0.86 !important; }

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: var(--surface2);
    border: 1px dashed var(--border);
    border-radius: var(--radius);
    padding: 10px;
}

/* ── Context badge ── */
.ctx-badge {
    display: inline-flex; align-items: center; gap: 5px;
    background: var(--surface3); border: 1px solid var(--border);
    border-radius: 999px; padding: 3px 10px;
    font-size: 0.72rem; color: var(--muted); font-family: 'DM Mono', monospace;
}

hr { border-color: var(--border) !important; margin: 1rem 0 !important; }

/* ── Sample chips ── */
.stButton > button.sample-btn {
    background: var(--surface2) !important;
    border: 1px solid var(--border) !important;
    color: var(--muted) !important;
    border-radius: 999px !important;
    font-size: 0.8rem !important;
    padding: 5px 14px !important;
    white-space: nowrap;
    transition: all 0.15s !important;
}
.stButton > button.sample-btn:hover {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
}

/* ── Session active indicator ── */
.session-active {
    background: rgba(255,107,53,0.1);
    border-left: 2px solid var(--accent);
}

/* ── Typing indicator ── */
@keyframes blink { 0%,80%,100%{opacity:0} 40%{opacity:1} }
.typing-dot {
    display: inline-block; width: 6px; height: 6px;
    background: var(--accent); border-radius: 50%; margin: 0 2px;
    animation: blink 1.4s infinite;
}
.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
MAX_CONTEXT_PAIRS = 4   # last N user+assistant pairs sent to LLM
MAX_SIDEBAR_SESSIONS = 12

MODES = {
    "db":  {"label": "🗄️ SAMAJH Database", "pill": "db",  "desc": "Offline RAG · ChromaDB + Groq"},
    "doc": {"label": "📄 My Document",      "pill": "doc", "desc": "Upload PDF · In-memory RAG"},
    "web": {"label": "🌐 Live Web Search",  "pill": "web", "desc": "Gemini 1.5 Flash · Google Grounding"},
}

SAMPLE_QUESTIONS = {
    "db":  ["What is the RTI Act?", "How do I apply for PM-Kisan?", "What are my rights if arrested?", "Explain Ayushman Bharat"],
    "doc": ["Summarise this document", "What are the key clauses?", "List all deadlines mentioned", "Who are the parties involved?"],
    "web": ["Latest UPSC 2025 notification", "Today's RBI policy update", "New labour law changes 2025", "Current MSP rates kharif 2025"],
}

LANGUAGES   = {"english": "English", "hindi": "हिंदी"}
DOMAINS     = ["All", "law", "health", "finance", "news", "schemes", "environment", "career", "rights"]

FALLBACK_GUIDES = {
    "general": {"name": "Samajh Assistant",  "emoji": "🇮🇳"},
    "legal":   {"name": "Legal Advisor",     "emoji": "⚖️"},
    "farmer":  {"name": "Kisan Mitra",       "emoji": "🌾"},
    "health":  {"name": "Swasthya Saathi",   "emoji": "🏥"},
}


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE BOOTSTRAP
# ─────────────────────────────────────────────────────────────────────────────
def _boot():
    defaults = {
        # ── State machine ──────────────────────────────────────────────────
        "app_state":          "home",   # "home" | "chat"

        # ── Session store ──────────────────────────────────────────────────
        # {session_id: {"title": str, "mode": str, "guide": str,
        #               "language": str, "domain": str,
        #               "messages": [...], "doc_loaded": bool,
        #               "doc_name": str, "created_at": str}}
        "chat_sessions":      {},
        "current_session_id": None,

        # ── Global prefs (applied to new sessions) ─────────────────────────
        "pref_language":      "english",
        "pref_domain":        "All",
        "pref_guide":         "general",
        "pref_mode":          "db",

        # ── Misc ───────────────────────────────────────────────────────────
        "pending_input":      "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_boot()

# Load guides
available_guides = FALLBACK_GUIDES
if GUIDES_AVAILABLE:
    try:
        available_guides = list_guides()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# SESSION HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _new_session(mode: str | None = None, guide: str | None = None) -> str:
    """Create a fresh session dict, register it, set as current, return id."""
    sid = str(uuid.uuid4())[:8]
    st.session_state.chat_sessions[sid] = {
        "title":      "New Chat",
        "mode":       mode or st.session_state.pref_mode,
        "guide":      guide or st.session_state.pref_guide,
        "language":   st.session_state.pref_language,
        "domain":     st.session_state.pref_domain,
        "messages":   [],
        "doc_loaded": False,
        "doc_name":   "",
        "created_at": datetime.now().strftime("%d %b %H:%M"),
    }
    st.session_state.current_session_id = sid
    return sid


def _cur() -> dict:
    """Return the current session dict (always valid after _ensure_session)."""
    return st.session_state.chat_sessions[st.session_state.current_session_id]


def _ensure_session():
    """If no session exists yet, create one silently."""
    sid = st.session_state.current_session_id
    if sid is None or sid not in st.session_state.chat_sessions:
        _new_session()


def _set_session_title(session: dict, first_user_message: str):
    """Auto-title a session from its first user message."""
    if session["title"] == "New Chat" and first_user_message:
        session["title"] = first_user_message[:32] + ("…" if len(first_user_message) > 32 else "")


# ─────────────────────────────────────────────────────────────────────────────
# CONTEXT WINDOW MANAGER
# ─────────────────────────────────────────────────────────────────────────────
def get_context_window(messages: list, max_pairs: int = MAX_CONTEXT_PAIRS) -> list:
    """Return only the last `max_pairs` user+assistant exchanges.

    Safety contract:
        - Never mutates the original list.
        - Always returns an even-length slice (complete pairs).
        - The LLM always sees at least 1 exchange if history exists.
    """
    if not messages:
        return []
    limit = max_pairs * 2          # 1 pair = user msg + assistant msg
    trimmed = messages[-limit:]    # take tail
    # Ensure we start on a user turn (role == "user")
    for i, msg in enumerate(trimmed):
        if msg["role"] == "user":
            return trimmed[i:]
    return trimmed


def context_info(messages: list) -> str:
    """Human-readable context window status string."""
    total   = len([m for m in messages if m["role"] == "user"])
    active  = min(total, MAX_CONTEXT_PAIRS)
    return f"🧠 {active}/{total} turns in context"


# ─────────────────────────────────────────────────────────────────────────────
# BACKEND ROUTER
# ─────────────────────────────────────────────────────────────────────────────
def call_backend(query: str, session: dict) -> dict:
    """Dispatch to the correct pipeline method based on session mode.

    Args:
        query:   The user's question for THIS turn.
        session: The full current session dict (for mode/guide/language/domain).

    Returns:
        Standardised response dict:
            answer              str
            sources             list[dict]
            follow_up_questions list[str]
            confidence          float
    """
    mode     = session["mode"]
    language = session["language"]
    domain   = session["domain"] if session["domain"] != "All" else None
    guide    = session["guide"]

    # ── STUB (no backend wired) ───────────────────────────────────────────
    if not PIPELINE_AVAILABLE:
        stub_sources = [
            {"title": "Ministry of Law — RTI Act 2005",    "domain": "law",     "ministry": "MoL",   "url": "https://rti.gov.in",    "similarity_score": 0.91},
            {"title": "India.gov.in Official Portal",       "domain": "schemes", "ministry": "MeitY", "url": "https://india.gov.in",  "similarity_score": 0.83},
        ]
        return {
            "answer": (
                f"**[STUB — {MODES[mode]['label']}]** Placeholder response for: *{query}*\n\n"
                "Wire `backend/pipeline.py` to replace this. Sources **[1]** and **[2]** appear below."
            ),
            "sources":              stub_sources if mode == "db" else [],
            "follow_up_questions":  ["Tell me more", "Related schemes?", "How to apply?"],
            "confidence":           0.88,
        }

    # ── Live backend ──────────────────────────────────────────────────────
    if mode == "db":
        return pipeline.answer_question(
            query=query, language=language, domain=domain, guide=guide
        )
    if mode == "doc":
        return pipeline.answer_from_document(
            query=query, language=language
        )
    if mode == "web":
        return pipeline.answer_from_web(
            query=query, language=language
        )
    return {"answer": "Unknown mode.", "sources": [], "follow_up_questions": []}


# ─────────────────────────────────────────────────────────────────────────────
# RENDER HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _mode_badge(mode: str) -> str:
    m = MODES[mode]
    return f'<span class="mode-pill {m["pill"]}">{m["label"]}</span>'


def render_user_bubble(text: str):
    st.markdown(
        f'<div class="user-bubble"><div class="user-bubble-inner">{text}</div></div>',
        unsafe_allow_html=True,
    )


def render_bot_bubble(message: dict, msg_idx: int, session: dict):
    mode        = message.get("mode", "db")
    guide_key   = session.get("guide", "general")
    g_info      = available_guides.get(guide_key, FALLBACK_GUIDES["general"])
    answer      = message.get("answer", "")
    sources     = message.get("sources", [])
    follow_ups  = message.get("follow_up_questions", [])
    ts          = message.get("timestamp", "")

    st.markdown(
        f"""
        <div class="bot-bubble mode-{mode}">
            <div class="bubble-meta">
                {g_info['emoji']} {g_info['name'].split('(')[0].strip()}
                &nbsp;{_mode_badge(mode)}
                <span style="margin-left:auto;opacity:0.45;font-size:0.7rem">{ts[11:16]}</span>
            </div>
            <div class="bot-answer">{answer}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Sources expander (tucked, collapsed by default) ───────────────────
    if sources:
        with st.expander(f"   {len(sources)} source{'s' if len(sources)!=1 else ''}", expanded=False):
            for i, src in enumerate(sources, 1):
                title    = src.get("title", src.get("source", "Unknown source"))
                domain   = src.get("domain", "")
                ministry = src.get("ministry", "")
                url      = src.get("url", "")
                score    = src.get("similarity_score")

                meta = " · ".join(filter(None, [
                    domain.upper() if domain else "",
                    ministry,
                    f"{score:.0%} match" if score else "",
                ]))
                link = (f'<a href="{url}" target="_blank" '
                        f'style="color:var(--accent);font-size:0.73rem;'
                        f'text-decoration:none;margin-left:6px;">↗ open</a>') if url else ""

                st.markdown(
                    f"""<div class="src-row">
                            <div class="src-num">{i}</div>
                            <div class="src-body">
                                <div class="src-title">{title}{link}</div>
                                <div class="src-meta">{meta}</div>
                            </div>
                        </div>""",
                    unsafe_allow_html=True,
                )

    # ── Follow-up chips ───────────────────────────────────────────────────
    if follow_ups:
        st.markdown(
            "<div style='margin-top:8px;font-size:0.74rem;color:var(--muted);'>Continue exploring →</div>",
            unsafe_allow_html=True,
        )
        fu_cols = st.columns(min(len(follow_ups), 3))
        for i, fq in enumerate(follow_ups[:3]):
            with fu_cols[i]:
                if st.button(fq, key=f"fu_{msg_idx}_{i}", use_container_width=True):
                    st.session_state.pending_input = fq
                    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# ██████████████████████  PAGE 1 : LANDING  ██████████████████████████████████
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.app_state == "home":

    _, center_col, _ = st.columns([1, 2.2, 1])
    with center_col:

        st.markdown("""
        <div class="landing-wrap">
            <div class="landing-logo">🏛️</div>
            <div class="landing-title">SAMAJH<span>.</span></div>
            <p class="landing-sub">
                Your personal civic intelligence agent — navigates Indian laws,
                explains government schemes, drafts RTI applications, and answers
                every civic question using <strong>100% verified official sources</strong>.
            </p>

            <div class="feature-grid">
                <div class="feature-card">
                    <div class="icon">🗄️</div>
                    <strong>SAMAJH Database</strong>
                    Offline RAG over curated civic documents
                </div>
                <div class="feature-card">
                    <div class="icon">📄</div>
                    <strong>My Document</strong>
                    Upload any PDF — ask anything about it
                </div>
                <div class="feature-card">
                    <div class="icon">🌐</div>
                    <strong>Live Web Search</strong>
                    Gemini-powered real-time answers
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        launch = st.button(
            "🚀  Launch SAMAJH Agent",
            type="primary",
            use_container_width=True,
            key="launch_btn",
        )

        if launch:
            with st.spinner("Initialising AI Core…"):
                time.sleep(0.8)
            _new_session()
            st.session_state.app_state = "chat"
            st.rerun()

    st.stop()   # Nothing below renders on the landing page


# ─────────────────────────────────────────────────────────────────────────────
# ██████████████████████  PAGE 2 : CHAT  █████████████████████████████████████
# ─────────────────────────────────────────────────────────────────────────────
_ensure_session()
session = _cur()

# ── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:

    # Logo
    st.markdown(
        "<div style='padding:10px 0 6px'>"
        "<span style='font-size:1.35rem;font-weight:700;letter-spacing:-0.03em;color:var(--text)'>"
        "SAMAJH <span style='color:var(--accent)'>·</span></span>"
        "<br/><span style='font-size:0.73rem;color:var(--muted)'>Civic Intelligence for India</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Global prefs ────────────────────────────────────────────────────
    st.caption("🌐 LANGUAGE")
    lang_choice = st.selectbox(
        "language",
        list(LANGUAGES.keys()),
        format_func=lambda k: LANGUAGES[k],
        index=list(LANGUAGES.keys()).index(st.session_state.pref_language),
        label_visibility="collapsed",
        key="sb_lang",
    )
    if lang_choice != st.session_state.pref_language:
        st.session_state.pref_language = lang_choice
        session["language"] = lang_choice   # apply to current session too
        st.rerun()

    st.caption("🎯 DOMAIN FILTER")
    dom_choice = st.selectbox(
        "domain",
        DOMAINS,
        index=DOMAINS.index(st.session_state.pref_domain),
        label_visibility="collapsed",
        key="sb_domain",
        disabled=(session["mode"] != "db"),
    )
    if dom_choice != st.session_state.pref_domain:
        st.session_state.pref_domain = dom_choice
        session["domain"] = dom_choice
        st.rerun()

    st.divider()

    # ── Guide persona ────────────────────────────────────────────────────
    st.caption("👤 GUIDE PERSONA")
    for gk, ginfo in available_guides.items():
        is_sel = session["guide"] == gk
        label  = f"{ginfo['emoji']}  {ginfo['name'].split('(')[0].strip()}"
        if st.button(label, key=f"g_{gk}", use_container_width=True,
                     type="primary" if is_sel else "secondary"):
            session["guide"] = gk
            st.session_state.pref_guide = gk
            st.rerun()

    st.divider()

    # ── Session management ───────────────────────────────────────────────
    st.caption("💬 CONVERSATIONS")
    if st.button("＋  New Chat", use_container_width=True, key="new_chat_btn"):
        _new_session()
        st.rerun()

    sessions_by_time = list(reversed(list(st.session_state.chat_sessions.keys())))
    for sid in sessions_by_time[:MAX_SIDEBAR_SESSIONS]:
        s      = st.session_state.chat_sessions[sid]
        is_cur = sid == st.session_state.current_session_id
        title  = s.get("title", "New Chat")
        meta   = s.get("created_at", "")
        mode_e = {"db": "🗄️", "doc": "📄", "web": "🌐"}.get(s.get("mode", "db"), "💬")
        label  = f"{mode_e} {title}"

        btn_style = "primary" if is_cur else "secondary"
        if st.button(label, key=f"sess_{sid}", use_container_width=True, type=btn_style):
            st.session_state.current_session_id = sid
            st.rerun()

        if not is_cur:
            st.markdown(
                f"<div style='font-size:0.68rem;color:var(--muted);"
                f"padding:0 4px 4px;margin-top:-6px'>{meta}</div>",
                unsafe_allow_html=True,
            )

    st.divider()

    # ── Context window status ────────────────────────────────────────────
    msgs = session.get("messages", [])
    if msgs:
        st.markdown(
            f"<div class='ctx-badge'>{context_info(msgs)}</div>",
            unsafe_allow_html=True,
        )
        st.caption("Only last 4 exchanges reach the LLM")


# ── MAIN AREA ─────────────────────────────────────────────────────────────────

# Mode selector
mode_cols = st.columns([1, 1, 1, 1.8])
for col, mk in zip(mode_cols[:3], list(MODES.keys())):
    with col:
        is_sel = session["mode"] == mk
        if st.button(
            MODES[mk]["label"],
            key=f"mode_{mk}_{st.session_state.current_session_id}",
            use_container_width=True,
            type="primary" if is_sel else "secondary",
        ):
            session["mode"] = mk
            st.session_state.pref_mode = mk
            # Reset doc state when switching away from doc mode
            if mk != "doc":
                session["doc_loaded"] = False
            st.rerun()

# Active mode caption
st.markdown(
    f"<div style='font-size:0.77rem;color:var(--muted);margin:-4px 0 14px;padding-left:2px'>"
    f"{MODES[session['mode']]['desc']}</div>",
    unsafe_allow_html=True,
)

# ── Document upload panel (doc mode only) ─────────────────────────────────────
if session["mode"] == "doc":
    with st.container():
        st.markdown(
            "<div style='background:var(--surface2);border:1px solid var(--border);"
            "border-radius:var(--radius);padding:14px 18px;margin-bottom:14px'>",
            unsafe_allow_html=True,
        )
        uploaded = st.file_uploader(
            "Upload a PDF to query against",
            type=["pdf"],
            key=f"pdf_{st.session_state.current_session_id}",
        )
        if uploaded and not session["doc_loaded"]:
            with st.spinner("Loading document into memory…"):
                try:
                    if PIPELINE_AVAILABLE:
                        pipeline.load_document(uploaded)
                    session["doc_loaded"] = True
                    session["doc_name"]   = uploaded.name
                    st.success(f"✅ **{uploaded.name}** loaded. Ask anything about it.")
                except Exception as e:
                    st.error(f"Failed to load document: {e}")
        elif session["doc_loaded"]:
            st.success(f"✅ **{session['doc_name']}** is active in this session.")
        st.markdown("</div>", unsafe_allow_html=True)

st.divider()

# ── Chat history ──────────────────────────────────────────────────────────────
messages = session.get("messages", [])

if not messages:
    # Welcome + sample chips
    guide_info = available_guides.get(session["guide"], FALLBACK_GUIDES["general"])
    st.markdown(
        f"<div style='text-align:center;padding:40px 0 28px;color:var(--muted);'>"
        f"<div style='font-size:2.4rem;margin-bottom:8px'>{guide_info['emoji']}</div>"
        f"<div style='font-size:1.2rem;font-weight:600;color:var(--text);margin-bottom:6px'>"
        f"How can {guide_info['name'].split('(')[0].strip()} help you?</div>"
        f"<div style='font-size:0.88rem'>Select a mode above and ask your first question.</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    samples = SAMPLE_QUESTIONS.get(session["mode"], [])
    s_cols  = st.columns(len(samples))
    for ci, sq in enumerate(samples):
        with s_cols[ci]:
            if st.button(sq, key=f"sq_{ci}_{st.session_state.current_session_id}",
                         use_container_width=True):
                st.session_state.pending_input = sq
                st.rerun()
else:
    # Render full history
    for idx, msg in enumerate(messages):
        if msg["role"] == "user":
            render_user_bubble(msg["content"])
        else:
            render_bot_bubble(msg, idx, session)

# ── Input bar ─────────────────────────────────────────────────────────────────
st.divider()

doc_guard   = (session["mode"] == "doc" and not session["doc_loaded"])
placeholder = {
    "db":  "Ask about Indian rights, schemes, laws…",
    "doc": "Ask something about your document…" if not doc_guard else "Please upload a PDF first ↑",
    "web": "Search anything — results are live…",
}[session["mode"]]

input_col, btn_col = st.columns([9, 1])
with input_col:
    user_input = st.text_input(
        "query",
        value=st.session_state.pending_input,
        placeholder=placeholder,
        label_visibility="collapsed",
        disabled=doc_guard,
        key=f"inp_{st.session_state.current_session_id}",
    )
with btn_col:
    send = st.button("↑", type="primary", use_container_width=True,
                     disabled=doc_guard, key="send_btn")

# ── Process ───────────────────────────────────────────────────────────────────
if (send or st.session_state.pending_input) and (user_input or st.session_state.pending_input).strip():
    query = (st.session_state.pending_input or user_input).strip()
    st.session_state.pending_input = ""

    # Append user message
    messages.append({"role": "user", "content": query, "timestamp": datetime.now().isoformat()})
    _set_session_title(session, query)

    # Context-limited history for LLM (not stored — only passed to backend)
    _ = get_context_window(messages)   # noqa: trimmed history available here for multi-turn backends

    with st.spinner("Agent SAMAJH is analysing…"):
        try:
            response = call_backend(query, session)
            answer   = response.get("annotated_answer", response.get("answer", "No answer generated."))

            messages.append({
                "role":               "bot",
                "mode":               session["mode"],
                "answer":             answer,
                "sources":            response.get("sources", []),
                "follow_up_questions": response.get("follow_up_questions", []),
                "confidence":         response.get("confidence", 0),
                "timestamp":          datetime.now().isoformat(),
            })
        except Exception as exc:
            messages.append({
                "role":      "bot",
                "mode":      session["mode"],
                "answer":    f"⚠️ Error: `{exc}`",
                "sources":   [],
                "follow_up_questions": [],
                "timestamp": datetime.now().isoformat(),
            })

    st.rerun()

# ── Footer ────────────────────────────────────────────────────────────────────
g = available_guides.get(session["guide"], FALLBACK_GUIDES["general"])
st.markdown(
    f"<div style='text-align:center;padding:16px 0 4px;font-size:0.71rem;color:var(--muted)'>"
    f"SAMAJH · {g['name'].split('(')[0].strip()} · "
    f"{LANGUAGES[session['language']]} · {MODES[session['mode']]['label']}"
    f"</div>",
    unsafe_allow_html=True,
)