from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

from config import OLLAMA_BASE_URL, OLLAMA_LARGE_MODEL
from src.tool_router import run_tools

SYSTEM_PROMPT = """You are Spartan Career Compass, a helpful virtual assistant for SJSU students.

STRICT RULES — follow these exactly:

1. ONLY use data provided below. You will receive real data from Career Center tools (events, staff/counselors, career guide content). Base your ENTIRE answer on this data.

2. NEVER invent or fabricate:
   - Event names, dates, times, or locations
   - Staff/counselor names, emails, or roles
   - URLs or links not present in the data
   - Drop-in hours, office hours, or schedules not in the data
   - Placeholder text like [insert date here], [insert name], [TBD], etc.

3. If the data does NOT contain what the user asked for, say so honestly:
   - "Based on the current Career Center data, I don't see any [X] events scheduled."
   - "I don't have specific information about [X] in my data. You may want to check directly with the Career Center."
   - Do NOT make up an answer or fill in gaps with assumptions.

4. LINK RULES:
   - Use the specific source_url or profile_url from the data for events and staff.
   - When citing guide content, reference the Career Guides page: https://careercenter.sjsu.edu/resources/career-guides/
   - Do NOT add generic "visit the Career Center website" links unless no specific link fits.
   - NEVER fabricate URLs.

5. FORMAT:
   - Be concise, friendly, and specific.
   - When listing events, include the exact title, date, time, location, and source_url from the data.
   - When referencing guide content, cite the guide name and page number from the data.
   - When listing staff, include their name, role, college, and email from the data.

6. For questions about guide content (resume tips, interview prep, career fair prep, etc.):
   - Summarize the ACTUAL text from the guide chunks provided in the data.
   - Do NOT generate generic advice — use the specific content from the PDF guides.
   - Cite which guide and page the information comes from."""


def get_llm(model_name: str | None = None):
    name = model_name or OLLAMA_LARGE_MODEL
    return ChatOllama(
        model=name,
        base_url=OLLAMA_BASE_URL,
        temperature=0.2,
    )


def run_agent(user_message: str, model_name: str | None = None) -> str:
    """
    Run the tool-augmented pipeline: fetch real data from tools, then have the LLM
    synthesize an answer. This guarantees the response is grounded in real events,
    staff, and guide content.
    """
    context = run_tools(user_message)
    llm = get_llm(model_name)
    prompt = f"""Here is the REAL data retrieved from Career Center tools. Use ONLY this data to answer.

{context}

---
User question: {user_message}

IMPORTANT REMINDERS:
- Answer using ONLY the data above. Do not invent any details.
- Use the exact event names, dates, staff names, emails, and URLs from the data.
- If the data does not contain relevant information, say so honestly.
- Do NOT use placeholder text like [insert date], [insert name], etc.
- Do NOT add generic "visit the Career Center website" unless no specific links are available.
- For guide content, summarize what the actual guide text says — do not generate generic advice."""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]
    response = llm.invoke(messages)
    return response.content if hasattr(response, "content") else str(response)


if __name__ == "__main__":
    msg = "What career events are coming up?"
    print("Context from tools:", run_tools(msg)[:500], "...")
    print("\n---\nReply:", run_agent(msg))
