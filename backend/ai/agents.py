import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ai.models import build_agent

logger = logging.getLogger(__name__)


async def get_explanation(user_id: str, db, learning_state_block: str, messages: list[dict]) -> str:
    """Send a conversation to the agent and return its reply.

    `messages` is a list of {"role": "user" | "assistant", "content": str}
    dicts — a small recent window (see history.py's HISTORY_LIMIT), not the
    whole conversation. `learning_state_block` is the student's compact
    pedagogical state (learning_state.format_state_block) — this, not
    conversation length, is the model's primary source of continuity.
    """
    conversation = [
        SystemMessage(content=learning_state_block),
        *(
            HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"])
            for m in messages
        ),
    ]

    agent = build_agent(user_id, db)
    logger.info("Invoking agent with %d messages (+ learning state)", len(conversation) - 1)
    result = await agent.ainvoke({"messages": conversation})
    reply = _extract_text(result["messages"][-1].content)
    logger.info("Agent replied: %r", reply)

    return reply


def _extract_text(content) -> str:
    """Pull plain text out of a message's `content`.

    Depending on the model, `content` is either a plain string or a list of
    content blocks (e.g. `{"type": "text", "text": "...", ...}`), so handle
    both instead of assuming one shape.
    """
    if isinstance(content, str):
        return content

    return "".join(block["text"] for block in content if isinstance(block, dict) and block.get("type") == "text")
