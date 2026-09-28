import logging
import os

from dotenv import load_dotenv
from langchain.agents import create_agent

from langchain_groq import ChatGroq

from ai.prompts import CONCEPT_EXPLAINER_SYSTEM_PROMPT
from ai.tools import calculator, circuit_solver, make_update_learning_state_tool, problem_finder, search_textbook, topic_finder

logger = logging.getLogger(__name__)

# Reads GROQ_API_KEY (and any other secrets) from backend/.env into the
# process environment.
load_dotenv()

# LangChain's wrapper around Groq. Created once and reused across requests —
# this holds no per-user state, just API credentials and model config.
llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=os.environ["GROQ_API_KEY"])
logger.info("Groq chat model initialized: %s", llm.model_name)

# Stateless tools — safe to share across every request/user.
_SHARED_TOOLS = [search_textbook, calculator, topic_finder, problem_finder, circuit_solver]


def build_agent(user_id: str, db):
    """Build a fresh agent for one request, with update_learning_state bound
    to this request's user_id/DB session (see ai/tools.py — that tool can't
    be a shared singleton the way the others are, since it needs to know
    who's asking). Cheap: no network calls happen here, just assembling the
    LangGraph graph around the already-initialized `llm` and tool objects.
    """
    tools = [*_SHARED_TOOLS, make_update_learning_state_tool(user_id, db)]
    return create_agent(model=llm, tools=tools, system_prompt=CONCEPT_EXPLAINER_SYSTEM_PROMPT)
