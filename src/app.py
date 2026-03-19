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

    # Single status message that updates in place during processing
    status_msg = cl.Message(content="_Classifying intent..._", author="system")
    await status_msg.send()

    msg = None  # The actual response message, created when tokens start flowing
    streaming_started = False

    async for chunk in orchestrator.handle_message_stream(message.content, session):
        if chunk.type == "classify_end":
            topic_name = TOPIC_DISPLAY_NAMES.get(chunk.topic_id, chunk.topic_id)
            status_msg.content = f"_Topic: **{topic_name}** — Generating response..._"
            await status_msg.update()

        elif chunk.type == "tool_start":
            display_name = TOOL_DISPLAY_NAMES.get(chunk.tool_name, chunk.tool_name)
            status_msg.content = f"_{display_name}..._"
            await status_msg.update()

        elif chunk.type == "tool_end":
            status_msg.content = f"_Generating response..._"
            await status_msg.update()

        elif chunk.type == "token":
            if not streaming_started:
                # Remove the status message and start the real response
                await status_msg.remove()
                msg = cl.Message(content="")
                await msg.send()
                streaming_started = True
            await msg.stream_token(chunk.token)

    if msg:
        await msg.update()
    elif not streaming_started:
        # Edge case: no tokens were produced
        status_msg.content = "I'm sorry, I wasn't able to generate a response. Please try again."
        await status_msg.update()


@cl.on_chat_end
async def on_end():
    pass


@cl.on_stop
async def on_stop():
    await close_pool()
