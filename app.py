from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from config import OLLAMA_LARGE_MODEL, OLLAMA_SMALL_MODEL
from src.agent import run_agent

st.set_page_config(page_title="Spartan Career Compass", page_icon="🧭", layout="wide")
st.title("🧭 Spartan Career Compass")
st.caption("SJSU Career Center assistant for events, counselors, and guides.")

with st.sidebar:
    st.header("Settings")
    model_choice = st.selectbox(
        "LLM Model",
        [OLLAMA_LARGE_MODEL, OLLAMA_SMALL_MODEL],
        index=0,
        help="Select the Ollama model (ensure Ollama is running locally).",
    )

    st.divider()

    st.header("Data Management")
    st.caption("Refresh events and staff data from the SJSU Career Center website.")

    if st.button("🔄 Scrape Latest Data", use_container_width=True):
        with st.spinner("Scraping events and staff from careercenter.sjsu.edu..."):
            try:
                from scripts.scrape_events import main as scrape_events_main
                from scripts.scrape_staff import main as scrape_staff_main

                scrape_staff_main()
                scrape_events_main()
                st.success("Data refreshed successfully!")
            except Exception as e:
                st.error(f"Scrape failed: {e}")

    if st.button("📄 Reload Career Guides", use_container_width=True):
        with st.spinner("Reloading PDF guides into database..."):
            try:
                from scripts.load_guides import main as load_guides_main
                load_guides_main()
                st.success("Guides reloaded successfully!")
            except Exception as e:
                st.error(f"Guide reload failed: {e}")

    st.divider()

    st.caption("Example questions:")
    st.markdown("""
- What career events are happening this week?
- Who is the counselor for engineering students?
- Summarize the Resume Guide into a checklist
- When is the next headshots event?
- Find resume workshops in the next 7 days
- What should I bring to a career fair?
""")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask about events, counselors, or career guides..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Checking events, staff, and guides..."):
            try:
                reply = run_agent(prompt, model_name=model_choice)
            except Exception as e:
                reply = (
                    f"**Error:** {e}\n\n"
                    "Make sure Ollama is running and the database is set up.\n"
                    "Run: `python scripts/init_db.py`, `python scripts/load_guides.py`, `python scripts/scrape_all.py`"
                )
            st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})
