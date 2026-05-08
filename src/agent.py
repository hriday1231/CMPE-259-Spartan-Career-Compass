"""tool-augmented agent with three prompting modes (simple, chain, reflect)"""

from pathlib import Path
import sys
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

from config import OLLAMA_BASE_URL, OLLAMA_LARGE_MODEL
from src.tool_router import run_tools
from src.prompts import (
    META_SYSTEM_PROMPT,
    SIMPLE_ANSWER_PROMPT,
    CHAIN_STEP1_PLAN,
    CHAIN_STEP2_ANSWER,
    CHAIN_STEP3_COMBINE,
    REFLECT_CRITIQUE,
    REFLECT_REVISE,
)
from src.prompt_cache import cached_invoke
from src.response_filter import clean_response, filtered_stream


def get_llm(model_name: str | None = None, temperature: float = 0.2):
    """build a ChatOllama tuned for this app

    num_ctx=4096 because system prompt + retrieved context routinely cross
    2000 tokens (default 2048 silently truncates), num_predict caps tail
    length, top_k/top_p tighten sampling for cacheable outputs, keep_alive
    keeps the model hot in VRAM between queries
    """
    name = model_name or OLLAMA_LARGE_MODEL
    return ChatOllama(
        model=name,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
        num_ctx=4096,
        num_predict=600,
        top_k=20,
        top_p=0.9,
        keep_alive="30m",
    )


def _invoke(llm, user_prompt: str, use_cache: bool = True) -> str:
    messages = [
        SystemMessage(content=META_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]
    if use_cache:
        text = cached_invoke(llm, messages)
    else:
        response = llm.invoke(messages)
        text = response.content if hasattr(response, "content") else str(response)
    return clean_response(text)


def _run_simple(llm, question: str, context: str, use_cache: bool) -> str:
    prompt = SIMPLE_ANSWER_PROMPT.format(context=context, question=question)
    return _invoke(llm, prompt, use_cache=use_cache)


def _run_chain(llm, question: str, context: str, use_cache: bool) -> str:
    plan = _invoke(
        llm,
        CHAIN_STEP1_PLAN.format(context=context, question=question),
        use_cache=use_cache,
    )
    sub_answers = _invoke(
        llm,
        CHAIN_STEP2_ANSWER.format(plan=plan, context=context),
        use_cache=use_cache,
    )
    final = _invoke(
        llm,
        CHAIN_STEP3_COMBINE.format(sub_answers=sub_answers, question=question),
        use_cache=use_cache,
    )
    return final


def _run_reflect(llm, question: str, context: str, use_cache: bool) -> str:
    draft = _invoke(
        llm,
        SIMPLE_ANSWER_PROMPT.format(context=context, question=question),
        use_cache=use_cache,
    )
    critique = _invoke(
        llm,
        REFLECT_CRITIQUE.format(draft=draft, context=context, question=question),
        use_cache=use_cache,
    )
    if "VERDICT: OK" in critique.upper():
        return draft
    revised = _invoke(
        llm,
        REFLECT_REVISE.format(
            draft=draft, critique=critique, context=context, question=question
        ),
        use_cache=use_cache,
    )
    return revised


def run_agent(
    user_message: str,
    model_name: str | None = None,
    mode: str = "simple",
    use_cache: bool = True,
) -> str:
    """run one user question through tool dispatch + the chosen prompting mode"""
    context = run_tools(user_message)
    llm = get_llm(model_name)

    if mode == "chain":
        return _run_chain(llm, user_message, context, use_cache)
    if mode == "reflect":
        return _run_reflect(llm, user_message, context, use_cache)
    return _run_simple(llm, user_message, context, use_cache)


def stream_agent_simple(
    user_message: str,
    context: str,
    model_name: str | None = None,
) -> Iterator[str]:
    """stream tokens for a simple-mode answer given precomputed tool context

    caller must run tool dispatch first (so the UI can show tools_used) and
    must close the iterator to stop generation server-side - that close is
    what the cancel button relies on
    """
    llm = get_llm(model_name)
    user_prompt = SIMPLE_ANSWER_PROMPT.format(context=context, question=user_message)
    messages = [
        SystemMessage(content=META_SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    def _raw():
        for chunk in llm.stream(messages):
            content = getattr(chunk, "content", None) or ""
            if content:
                yield content

    yield from filtered_stream(_raw())


if __name__ == "__main__":
    msg = "What career events are coming up?"
    print("Context:", run_tools(msg)[:500], "...\n")
    print("Simple:\n", run_agent(msg, mode="simple"))
