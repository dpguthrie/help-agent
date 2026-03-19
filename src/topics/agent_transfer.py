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
        "   - If isValidationPassed is true: inform the user they are being transferred to a "
        "support engineer. Let them know the expected wait time may vary.\n"
        "   - If isValidationPassed is false: relay the responseMessage from the tool. "
        "It will explain why the transfer isn't available (e.g., tenant not eligible, plan "
        "restrictions). If recommendCaseOnEscalation is true, suggest creating a support "
        "case as an alternative. You can also suggest they try a different tenant if they "
        "have access to one.\n"
        "4. Respond in the same language the user writes in.\n"
        "5. If the user seems frustrated or describes an urgent issue, acknowledge their "
        "urgency and prioritize getting them connected quickly."
    ),
    tools=["get_user_context", "validate_and_transfer", "emit_event"],
)
