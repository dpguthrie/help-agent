from topics.base import Topic

AGENT_TRANSFER = Topic(
    id="agent_transfer",
    name="Agent Transfer",
    classification_description=(
        "The user wants to speak with a human agent, transfer to support, talk to someone, "
        "or be connected to a support engineer. They may say 'transfer to agent', 'talk to "
        "someone', 'speak to a human', or 'connect me to support'."
    ),
    instructions=(
        "You are helping transfer the user to a human support engineer.\n\n"
        "1. Call get_user_context to check authentication.\n"
        "   - If NOT_AUTHENTICATED: call emit_event with LOGIN_REQUESTED and ask them to log in.\n"
        "   - Wait for the 'Automated message: log in successful' before proceeding.\n"
        "2. Once authenticated, show tenant details and ask the user to confirm.\n"
        "3. Call validate_and_transfer to check eligibility and initiate the transfer.\n"
        "   - If eligible: inform the user they are being transferred.\n"
        "   - If not eligible: explain why and suggest alternatives (create a case, try KB).\n"
        "4. Respond in the same language the user writes in."
    ),
    tools=["get_user_context", "validate_and_transfer", "emit_event"],
)
