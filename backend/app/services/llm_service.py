"""LLM generation with cooperative cancellation and texting-style output."""

from __future__ import annotations

import asyncio
import json
import re
from typing import AsyncGenerator

from openai import AsyncOpenAI

from app.config import settings
from app.services import session_service, exa_service
from app.mcp import executor as mcp_executor
from app.mcp.registry import get_tools_for_providers
from app.mcp.token_store import list_connected_providers

_client: AsyncOpenAI | None = None

SYSTEM_PROMPT = """\
You are a conversational assistant embedded inside iMessage / SMS / RCS. You behave like a real person texting, not a chatbot.

You write in a casual, spoken tone. Short sentences. Fragmented thoughts are fine. You do not over-explain. You do not sound formal, robotic, or structured.

You MUST simulate real texting behavior using message splitting. Instead of one long response, you output multiple messages using this exact format:

<new_message time=seconds>
message text

Each block is sent separately. The time attribute represents the delay (in seconds) before that message is sent. Use small, realistic delays (0–6 seconds). Vary them slightly to feel human.

Rules:

Default to 2–6 messages per response unless the reply is extremely short.
Keep each message short (1–2 sentences max, often less).
You can send partial thoughts, corrections, or follow-ups as separate messages.
You may use natural texting artifacts like "wait", "lol", "nah", "ok", "hold on", but don't overdo it.
Do not write long paragraphs in a single message; split instead.
Never mention that you are using formatting, tags, or a system.

Conversation style:

Casual, direct, slightly messy like real texting.
You can be abrupt, playful, or mildly sarcastic depending on context.
Avoid overly polished grammar.
No formal intros or closings.

If the user is vague, ask a short clarifying question in a separate message rather than bundling it.

The goal is realism: it should feel like a real person actively texting, not generating a response.
"""

BASE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information. Use when the user asks about recent events, facts you're unsure about, or anything that benefits from live data.",
            "parameters": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    }
                },
            },
        },
    }
]


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.nebius_api_key,
            base_url=settings.nebius_base_url,
        )
    return _client


def _parse_messages(raw_text: str) -> list[dict]:
    """Parse the <new_message time=N> format into structured message chunks."""
    pattern = r'<new_message\s+time=(\d+(?:\.\d+)?)>\s*\n?(.*?)(?=<new_message|$)'
    matches = re.findall(pattern, raw_text, re.DOTALL)

    if not matches:
        # Fallback: treat entire text as a single message
        return [{"content": raw_text.strip(), "delay_seconds": 1.0}]

    messages = []
    for delay_str, content in matches:
        content = content.strip()
        if content:
            messages.append({
                "content": content,
                "delay_seconds": float(delay_str),
            })
    return messages


async def _get_tools_for_session(session_id: str) -> list[dict]:
    """Build the full tool list: base tools + MCP tools for connected providers."""
    tools = list(BASE_TOOLS)

    # Get user_id from session
    session = await session_service.get_session(session_id)
    if session:
        connected = await list_connected_providers(session.user_id)
        if connected:
            mcp_tools = get_tools_for_providers(connected)
            tools.extend(mcp_tools)

    return tools


async def _handle_tool_call(tc, user_id: str) -> str:
    """Route a tool call to the right handler (base or MCP)."""
    name = tc.function.name
    args = json.loads(tc.function.arguments)

    # Base tool: web search via Exa
    if name == "web_search":
        results = exa_service.search(args.get("query", ""))
        return json.dumps(results)

    # MCP tool: format is {provider}__{tool_name}
    if "__" in name:
        return await mcp_executor.execute(name, args, user_id)

    return json.dumps({"error": f"Unknown tool: {name}"})


async def generate_response(
    session_id: str,
    generation_id: str,
) -> AsyncGenerator[dict, None]:
    """
    Generate a response for the session. Yields message chunks.
    Cooperatively checks if this generation is still active.
    """
    client = _get_client()
    history = await session_service.get_history(session_id)
    session = await session_service.get_session(session_id)
    user_id = session.user_id if session else ""

    # Build tools list dynamically based on connected MCP providers
    tools = await _get_tools_for_session(session_id)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

    # First call — may involve tool use
    response = await client.chat.completions.create(
        model=settings.nebius_model,
        messages=messages,
        tools=tools if tools else None,
        temperature=0.9,
    )

    choice = response.choices[0]

    # Handle tool calls (search + MCP tools)
    while choice.finish_reason == "tool_calls":
        # Check cancellation before processing tools
        active = await session_service.get_active_generation_id(session_id)
        if active != generation_id:
            return

        tool_calls = choice.message.tool_calls
        messages.append(choice.message)

        for tc in tool_calls:
            result = await _handle_tool_call(tc, user_id)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

        # Check cancellation again
        active = await session_service.get_active_generation_id(session_id)
        if active != generation_id:
            return

        response = await client.chat.completions.create(
            model=settings.nebius_model,
            messages=messages,
            tools=tools if tools else None,
            temperature=0.9,
        )
        choice = response.choices[0]

    # We have the final text response
    raw_text = choice.message.content or ""

    # Check cancellation one more time
    active = await session_service.get_active_generation_id(session_id)
    if active != generation_id:
        return

    # Parse into message bubbles
    parsed = _parse_messages(raw_text)

    # Store assistant response in history (full text)
    full_content = " ".join(m["content"] for m in parsed)
    await session_service.append_history(session_id, "assistant", full_content)

    # Yield each message chunk
    for i, msg in enumerate(parsed):
        # Cooperative cancellation check per message
        active = await session_service.get_active_generation_id(session_id)
        if active != generation_id:
            return

        is_last = i == len(parsed) - 1
        yield {
            "generation_id": generation_id,
            "message_index": i,
            "content": msg["content"],
            "delay_seconds": msg["delay_seconds"],
            "done": is_last,
        }

        # Simulate the typing delay between messages
        if not is_last:
            await asyncio.sleep(msg["delay_seconds"])
