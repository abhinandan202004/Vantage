"""
The chat agent's tool-calling loop: send messages to Groq, check if
the model wants to call a tool, execute it, feed the result back, and
repeat until the model returns a final text answer.

Stateless by design: the caller (the /chat route) passes the full
message history on every request rather than this module persisting
conversations server-side — simplest correct thing for an MVP, and
matches how most chat UIs already manage state client-side. Swap in a
DB-backed history later if you want cross-device conversation
persistence.
"""
import json
from groq import Groq, BadRequestError
from sqlalchemy.orm import Session

from app.config import settings
from app.chat.tools import TOOL_SCHEMAS, execute_tool_call

SYSTEM_PROMPT = (
    "You are a finance assistant embedded in a personal NSE stock-screener app. "
    "You can answer general finance/investing questions from your own knowledge "
    "(e.g. explaining ratios, concepts, strategies), AND you have tools to look up "
    "live data from the user's own screener (stock scores, price summaries) when "
    "they ask about a specific stock, plus a knowledge-base search tool covering "
    "this screener's own scoring methodology and any ingested company filings. "
    "Use a tool whenever the question is about a specific stock's current data — "
    "don't guess numbers you could look up. Use search_knowledge_base specifically "
    "when asked why a score came out a certain way, what a condition means IN THIS "
    "screener, or about qualitative filing content (management commentary, capex, "
    "order book). Only include the optional 'symbol' argument on search_knowledge_base "
    "when the user names a specific stock — omit it entirely (do not pass an empty "
    "string) for general methodology questions. For general concept questions "
    "unrelated to this screener's specifics, answer directly without calling a tool. "
    "This is not licensed financial advice — for buy/sell recommendations, present "
    "what the data shows and let the user draw their own conclusion, rather than "
    "telling them what to do."
)

MAX_TOOL_ITERATIONS = 5  # safety cap — stops an infinite tool-call loop from hanging a request


def _is_tool_use_failed(e: BadRequestError) -> bool:
    """
    True if this 400 is specifically Groq's "the model's tool-call
    output was malformed and couldn't be parsed" error — a model
    reliability issue (confirmed to happen with llama-3.3-70b-versatile
    in practice, e.g. emitting `<function=...>` XML-ish syntax instead
    of a proper structured tool call), not a problem with our request.
    Distinguished from other 400s (bad model name, invalid schema, etc.)
    which SHOULD keep failing loudly rather than being silently retried.
    """
    body = getattr(e, "body", None) or {}
    error_info = body.get("error", {}) if isinstance(body, dict) else {}
    return error_info.get("code") == "tool_use_failed"


def run_chat_turn(db: Session, messages: list[dict]) -> list[dict]:
    """
    `messages`: the existing conversation as a list of
    {"role": "user"|"assistant"|"tool", "content": ...} dicts, ending
    with the newest user message. Does NOT include the system prompt —
    that's added here.

    Returns the updated message list with the model's new turn(s)
    appended (including any tool-call/tool-result pairs, so the
    caller/frontend can render or persist the full exchange if it
    wants to, not just the final answer).
    """
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set — get a free key at console.groq.com "
            "and add it to your .env file."
        )

    client = Groq(api_key=settings.groq_api_key)
    working_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    for _ in range(MAX_TOOL_ITERATIONS):
        try:
            response = client.chat.completions.create(
                model=settings.groq_model,
                messages=working_messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
            )
        except BadRequestError as e:
            if not _is_tool_use_failed(e):
                raise  # a real problem with our request — don't hide it

            # The model tried to call a tool but produced malformed
            # output Groq couldn't parse. Retry ONCE with tools turned
            # off, forcing a direct text answer — degrades gracefully
            # (the user gets an answer without tool-augmented data for
            # this turn) instead of the whole request crashing.
            fallback_response = client.chat.completions.create(
                model=settings.groq_model,
                messages=working_messages,
                tool_choice="none",
            )
            fallback_content = fallback_response.choices[0].message.content
            working_messages.append({
                "role": "assistant",
                "content": (
                    fallback_content
                    or "I had trouble looking that up just now — could you rephrase the question?"
                ),
            })
            return working_messages[1:]

        choice = response.choices[0].message

        if not choice.tool_calls:
            # Final answer — no more tools requested.
            working_messages.append({"role": "assistant", "content": choice.content})
            return working_messages[1:]  # drop the system prompt before returning

        # Model wants to call one or more tools. Append its tool-call
        # request, execute each one, and append results before looping
        # back for the model to use them.
        working_messages.append({
            "role": "assistant",
            "content": choice.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in choice.tool_calls
            ],
        })

        for tc in choice.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            # Drop empty-string arguments — a model sometimes passes ""
            # for an optional parameter instead of omitting it, and an
            # empty-string symbol would incorrectly filter search_knowledge_base
            # down to "no such stock" instead of searching unfiltered.
            args = {k: v for k, v in args.items() if v != ""}
            tool_result = execute_tool_call(db, tc.function.name, args)
            working_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_result,
            })

    # Hit the iteration cap without a final answer — return what we
    # have plus an explicit note, rather than silently returning
    # nothing or hanging.
    working_messages.append({
        "role": "assistant",
        "content": "I wasn't able to finish looking that up after several tool calls — could you rephrase or narrow the question?",
    })
    return working_messages[1:]