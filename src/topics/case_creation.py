from topics.base import Topic

CASE_CREATION = Topic(
    id="case_creation",
    name="Case Creation",
    classification_description=(
        "The user wants to create a support case, log a case, open a ticket, or report "
        "an issue that needs formal tracking. They may say 'create case', 'open a case', "
        "'log a case', or express that they need to escalate beyond self-service."
    ),
    instructions=(
        "You are helping the user create a Salesforce support case. Follow this process:\n\n"
        "1. Call get_user_context to check authentication and get tenant details.\n"
        "   - If NOT_AUTHENTICATED: call emit_event with LOGIN_REQUESTED and ask the user to log in.\n"
        "   - If authenticated: show the tenant details and ask the user to confirm.\n"
        "2. Ask for the user's timezone.\n"
        "3. Ask for a brief description of the issue.\n"
        "4. Ask for severity level (1-4):\n"
        "   - Severity 1: Critical production issue - business completely stopped or revenue impacted\n"
        "   - Severity 2: Major functionality impacted and time-sensitive\n"
        "   - Severity 3: Minor functionality impacted and time-sensitive\n"
        "   - Severity 4: General inquiry, how-to or routine technical issue\n"
        "5. For severity 1 or 2: ask for a phone number with country code (format: +[code] [number]).\n"
        "6. Summarize all details and ask for final confirmation.\n"
        "7. Call create_case with all collected information.\n"
        "8. Return the case number and tracking link.\n\n"
        "Collect one piece of information per turn. Do not skip steps."
    ),
    tools=["get_user_context", "create_case", "emit_event"],
)
