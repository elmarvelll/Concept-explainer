from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Message, MessageRole

# How many prior messages to feed back to the agent as context — the last 2
# user/assistant turns (4 messages). Keeps the prompt bounded as a
# conversation grows instead of resending its entire lifetime history on
# every turn, which also matters now that tool outputs (problem_finder,
# search_textbook) add meaningfully to token usage per request.
HISTORY_LIMIT = 4


async def load_history(db: AsyncSession, user_id: str) -> list[dict]:
    """Return this user's last `HISTORY_LIMIT` messages, oldest first."""
    result = await db.execute(
        select(Message)
        .where(Message.userId == user_id)
        .order_by(Message.createdAt.desc())
        .limit(HISTORY_LIMIT)
    )
    rows = list(reversed(result.scalars().all()))
    return [{"role": row.role.value.lower(), "content": row.content} for row in rows]


async def save_message(db: AsyncSession, user_id: str, role: MessageRole, content: str) -> None:
    db.add(Message(userId=user_id, role=role, content=content))
    await db.commit()
