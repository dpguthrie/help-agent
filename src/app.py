from __future__ import annotations
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

    async for chunk in orchestrator.handle_message_stream(message.content, session):
        if chunk.type == "token":
            await msg.stream_token(chunk.token)

    await msg.update()


@cl.on_chat_end
async def on_end():
    pass


@cl.on_stop
async def on_stop():
    await close_pool()
