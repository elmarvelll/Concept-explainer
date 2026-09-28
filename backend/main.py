import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ai import get_explanation
from auth import require_user
from db import get_db
from history import load_history, save_message
from learning_state import format_state_block, list_paused_topics, load_active_state
from models import MessageRole

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Concept Explainer API")

# Browsers block cross-origin requests by default. The frontend runs on a
# different port (Next.js dev server at :3000) than this API, so CORS must
# be enabled explicitly or the browser will reject the frontend's requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
async def chat(req: ChatRequest, user: dict = Depends(require_user), db: AsyncSession = Depends(get_db)):
    text = req.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="message must not be empty")

    user_id = user["sub"]
    logger.info("Received chat message from %s: %r", user.get("email"), text)

    # The DB is the source of truth for conversation history — each turn is
    # saved as it happens, so a fresh request only needs to send its own new
    # message, not the whole conversation back.
    history = await load_history(db, user_id)
    await save_message(db, user_id, MessageRole.USER, text)

    # The learning state, not conversation length, is the model's primary
    # source of continuity — history here is just a small recent window
    # (see history.HISTORY_LIMIT) for things like "the example you just gave".
    state = await load_active_state(db, user_id)
    paused_topics = await list_paused_topics(db, user_id)
    state_block = format_state_block(state, paused_topics)

    try:
        reply = await get_explanation(user_id, db, state_block, [*history, {"role": "user", "content": text}])
    except Exception as e:
        logger.exception("AI service error while generating an explanation")
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")

    logger.info("Agent replied: %r", reply)
    await save_message(db, user_id, MessageRole.ASSISTANT, reply)

    return {"reply": reply}


# Simple liveness endpoint — useful for uptime checks or confirming the
# server is reachable before wiring up the frontend.
@app.get("/api/health")
async def health():
    return {"status": "ok"}
