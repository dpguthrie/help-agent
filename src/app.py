from __future__ import annotations
import json
import os
import chainlit as cl
from dotenv import load_dotenv

load_dotenv()

from agent.config import Settings
from agent.models import SessionState, AuthState
from agent.orchestrator import Orchestrator
from db.connection import get_pool, close_pool

settings = Settings()
_orchestrator: Orchestrator | None = None

# Friendly names for tools shown in the UI
TOOL_DISPLAY_NAMES = {
    "search_knowledge": "Searching knowledge base",
    "get_user_context": "Looking up account details",
    "create_case": "Creating support case",
    "validate_and_transfer": "Validating transfer eligibility",
    "emit_event": "Triggering event",
    "get_recent_cases": "Fetching recent cases",
    "get_case": "Looking up case",
    "perform_case_action": "Updating case",
    "raise_flag_for_supervisor": "Escalating to supervisor",
    "get_personalization": "Loading personalized info",
    "get_datetime": "Getting current time",
}

TOPIC_DISPLAY_NAMES = {
    "knowledge_faq": "Knowledge & FAQ",
    "case_creation": "Case Creation",
    "agent_transfer": "Agent Transfer",
    "case_management": "Case Management",
    "off_topic": "General",
}


async def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        pool = await get_pool(settings)
        _orchestrator = Orchestrator(settings=settings, db_pool=pool)
    return _orchestrator


@cl.on_chat_start
async def on_start():
    session_id = cl.user_session.get("id")
    session = SessionState(session_id=session_id)
    cl.user_session.set("session_state", session)

    # Simulate authenticated user for demo
    session.auth_state = AuthState(
        tenant_name="COMPANY_demo_001",
        org_id="SFID_demo_001",
        product="core",
        success_plan="Premier",
    )

    await cl.Message(content="Welcome to Salesforce Help. How can I assist you today?").send()


@cl.on_message
async def on_message(message: cl.Message):
    session = cl.user_session.get("session_state")
    orchestrator = await get_orchestrator()

    msg = cl.Message(content="")
    await msg.send()

    classify_step = None
    tool_step = None

    async for chunk in orchestrator.handle_message_stream(message.content, session):
        if chunk.type == "classify_start":
            classify_step = cl.Step(name="Classifying intent", type="tool")
            await classify_step.send()

        elif chunk.type == "classify_end":
            if classify_step:
                topic_name = TOPIC_DISPLAY_NAMES.get(chunk.topic_id, chunk.topic_id)
                classify_step.output = f"**{topic_name}** (confidence: {chunk.confidence:.0%})"
                await classify_step.update()

        elif chunk.type == "tool_start":
            display_name = TOOL_DISPLAY_NAMES.get(chunk.tool_name, chunk.tool_name)
            tool_step = cl.Step(name=display_name, type="tool")
            if chunk.tool_input:
                tool_step.input = json.dumps(chunk.tool_input, indent=2)
            await tool_step.send()

        elif chunk.type == "tool_end":
            if tool_step:
                tool_step.output = chunk.tool_output
                await tool_step.update()
                tool_step = None

        elif chunk.type == "token":
            await msg.stream_token(chunk.token)

    await msg.update()


@cl.on_chat_end
async def on_end():
    pass


@cl.on_stop
async def on_stop():
    await close_pool()
