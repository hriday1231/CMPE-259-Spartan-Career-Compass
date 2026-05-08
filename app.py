from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import streamlit.components.v1 as components

from config import OLLAMA_LARGE_MODEL, OLLAMA_SMALL_MODEL
from src.agent import run_agent, stream_agent_simple
from src.tool_router import run_tools_with_meta

# unique marker so the JS overlay can find our hidden stop button
_STOP_BTN_MARKER = "_cc_stop_btn_marker_7f3a"

st.set_page_config(page_title="Spartan Career Compass", page_icon="🧭", layout="wide")
st.title("🧭 Spartan Career Compass")
st.caption("SJSU Career Center assistant for events, counselors, and guides.")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "generating" not in st.session_state:
    st.session_state.generating = False
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

with st.sidebar:
    st.header("Settings")
    # mistral:7b runs about 2.4x faster than llama2:13b on this hardware
    # with comparable grounding quality, so it is the default
    model_choice = st.selectbox(
        "LLM Model",
        [OLLAMA_SMALL_MODEL, OLLAMA_LARGE_MODEL],
        index=0,
        help="Select the Ollama model. mistral:7b is the faster default.",
        disabled=st.session_state.generating,
    )
    mode_choice = st.selectbox(
        "Prompting Mode",
        ["simple", "chain", "reflect"],
        index=0,
        help=(
            "simple: one-shot, streams token-by-token (default).\n"
            "chain: plan -> answer sub-tasks -> combine.\n"
            "reflect: draft -> critique -> revise."
        ),
        disabled=st.session_state.generating,
    )
    use_cache = st.checkbox(
        "Use prompt cache",
        value=True,
        help="Cache LLM responses on disk keyed by (model, full prompt).",
        disabled=st.session_state.generating,
    )

    st.divider()

    st.header("Data Management")
    st.caption("Refresh events and staff data from the SJSU Career Center website.")

    disabled = st.session_state.generating
    if st.button("🔄 Scrape Latest Data", use_container_width=True, disabled=disabled):
        with st.spinner("Scraping events and staff from careercenter.sjsu.edu..."):
            try:
                from scripts.scrape_events import main as scrape_events_main
                from scripts.scrape_staff import main as scrape_staff_main
                scrape_staff_main()
                scrape_events_main()
                st.success("Data refreshed successfully!")
            except Exception as e:
                st.error(f"Scrape failed: {e}")

    if st.button("📄 Reload Career Guides", use_container_width=True, disabled=disabled):
        with st.spinner("Reloading PDF guides into database..."):
            try:
                from scripts.load_guides import main as load_guides_main
                load_guides_main()
                st.success("Guides reloaded successfully!")
            except Exception as e:
                st.error(f"Guide reload failed: {e}")

    if st.button("🧹 Clear prompt cache", use_container_width=True, disabled=disabled):
        from src.prompt_cache import clear as cache_clear, stats as cache_stats
        n = cache_clear()
        st.success(f"Cleared {n} cached entries. Stats: {cache_stats()}")

    st.divider()

    with st.expander("💡 Example questions", expanded=False):
        st.markdown("""
- What career events are happening this week?
- Who is the counselor for engineering students?
- Summarize the Resume Guide into a checklist
- When is the next headshots event?
- Find resume workshops in the next 7 days
- What should I bring to a career fair?
- Find remote data science internships paying over $20/hr
- Show entry-level software roles in California
- Tell me about Adobe before my interview
""")

# one-time welcome banner
if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.markdown(
            "Hi 👋 I'm Spartan Career Compass. Ask me about Career Center events, "
            "counselors, career guides, internships, or employers. Pick a question "
            "from **💡 Example questions** in the sidebar, or type your own below."
        )

# while generating, the last two messages are the just-submitted user prompt
# and the in-progress assistant slot - both are rendered fresh inside the
# pending-prompt block below, so trim them off the history loop or they
# show up twice on the page during streaming
history = (
    st.session_state.messages[:-2]
    if st.session_state.generating and len(st.session_state.messages) >= 2
    else st.session_state.messages
)
for msg in history:
    with st.chat_message(msg["role"]):
        if msg.get("tools_used"):
            st.caption("🔧 Tools used: " + ", ".join(msg["tools_used"]))
        st.markdown(msg["content"])

# the input bar always renders st.chat_input - while generating, we inject
# CSS+JS that hides the native send-arrow SVG, overlays a stop glyph, and
# reroutes clicks to our hidden stop button so the same button visually
# morphs from "send" to "stop" rather than rendering a separate bar
user_prompt = st.chat_input("Ask about events, counselors, or career guides...")

if st.session_state.generating:
    # hidden Streamlit button - clicking it triggers a rerun, which raises
    # RerunException inside the streaming loop -> graceful stop + socket close
    if st.button(_STOP_BTN_MARKER, key="cc_stop_hidden"):
        pass

    st.markdown(
        """
        <style>
        div[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"] svg {
            display: none !important;
        }
        div[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"]::before {
            content: "⏹";
            font-size: 22px;
            line-height: 1;
            color: #ff4b4b;
        }
        div[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"] {
            cursor: pointer !important;
            opacity: 1 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    components.html(
        f"""
        <script>
        (function() {{
            const doc = window.parent.document;
            const MARKER = {_STOP_BTN_MARKER!r};

            let hiddenStopBtn = null;
            for (const b of doc.querySelectorAll('button')) {{
                if (b.innerText && b.innerText.trim() === MARKER) {{
                    hiddenStopBtn = b;
                    break;
                }}
            }}
            if (!hiddenStopBtn) return;

            const container = hiddenStopBtn.closest('[data-testid="stElementContainer"]')
                || hiddenStopBtn.closest('[data-testid="element-container"]');
            if (container) {{
                container.style.position = 'absolute';
                container.style.left = '-99999px';
                container.style.height = '0';
                container.style.overflow = 'hidden';
                container.style.pointerEvents = 'none';
            }}

            const sendBtn = doc.querySelector(
                'div[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"]'
            );
            if (!sendBtn) return;

            // Streamlit disables the send button when the textarea is empty,
            // re-enable it so the morph reads as a real stop button
            sendBtn.disabled = false;
            sendBtn.removeAttribute('disabled');

            if (!sendBtn.dataset.ccStopBound) {{
                sendBtn.dataset.ccStopBound = '1';
                sendBtn.addEventListener('click', function(e) {{
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    hiddenStopBtn.click();
                }}, true);
            }}
        }})();
        </script>
        """,
        height=0,
    )

# capture a new submission, then schedule generation for the next rerun
if user_prompt and not st.session_state.generating:
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    st.session_state.messages.append({"role": "assistant", "content": "", "tools_used": []})
    st.session_state.pending_prompt = user_prompt
    st.session_state.generating = True
    st.rerun()

# process the pending prompt (runs on the rerun after submission)
if st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            context, tools_used = run_tools_with_meta(prompt)
        except Exception as e:
            tools_used = []
            context = ""
            st.error(f"Tool dispatch failed: {e}")

        st.session_state.messages[-1]["tools_used"] = tools_used
        if tools_used:
            st.caption("🔧 Tools used: " + ", ".join(tools_used))
        else:
            st.caption("🔧 No tools dispatched")

        placeholder = st.empty()
        stream = None

        try:
            if mode_choice == "simple" and not use_cache:
                stream = stream_agent_simple(prompt, context, model_name=model_choice)
                for chunk in stream:
                    st.session_state.messages[-1]["content"] += chunk
                    placeholder.markdown(st.session_state.messages[-1]["content"] + "▌")
                placeholder.markdown(st.session_state.messages[-1]["content"])
            else:
                with st.spinner(f"Running {mode_choice} mode on {model_choice}..."):
                    text = run_agent(
                        prompt,
                        model_name=model_choice,
                        mode=mode_choice,
                        use_cache=use_cache,
                    )
                st.session_state.messages[-1]["content"] = text
                placeholder.markdown(text)
        except Exception as e:
            err = (
                f"**Error:** {e}\n\n"
                "Make sure Ollama is running and the database is set up.\n"
                "Run: `python scripts/init_db.py`, `python scripts/load_guides.py`, "
                "`python scripts/scrape_all.py`"
            )
            st.session_state.messages[-1]["content"] += (
                ("\n\n" if st.session_state.messages[-1]["content"] else "") + err
            )
            placeholder.markdown(st.session_state.messages[-1]["content"])
        except BaseException:
            # catches the RerunException fired by the stop button click
            st.session_state.messages[-1]["content"] += "\n\n_(stopped by user)_"
            raise
        finally:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            st.session_state.pending_prompt = None
            st.session_state.generating = False

        if not st.session_state.messages[-1]["content"]:
            st.session_state.messages[-1]["content"] = "_(no response)_"

    st.rerun()
