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
        "You are helping the user create a Salesforce support case. Follow these steps EXACTLY "
        "in order. Collect ONE piece of information per turn. Do NOT add extra steps, ask for "
        "additional details, or deviate from this sequence.\n\n"
        "Step 1: Call get_user_context to check authentication.\n"
        "  - If NOT_AUTHENTICATED: call emit_event with LOGIN_REQUESTED and ask the user to log in.\n"
        "  - If authenticated: show tenant name, product, and org ID. Ask user to confirm this is correct.\n"
        "Step 2: Ask for timezone (e.g., America/Chicago, Asia/Tokyo, UTC).\n"
        "Step 3: Ask for a description of the issue. Accept whatever the user provides as-is. "
        "Do NOT ask for more detail or clarification - move to step 4 immediately.\n"
        "Step 4: Ask for severity level. Present these options:\n"
        "  - 1: Critical - business stopped or revenue impacted\n"
        "  - 2: Major - functionality impacted, time-sensitive\n"
        "  - 3: Minor - functionality impacted, time-sensitive\n"
        "  - 4: General inquiry or routine issue\n"
        "Step 5: ONLY if severity is 1 or 2, ask for phone number with country code. "
        "For severity 3 or 4, skip directly to step 6.\n"
        "Step 6: Summarize ALL collected details and ask for final confirmation (yes/no).\n"
        "Step 7: When confirmed, call create_case with subject (short summary of description), "
        "description, severity, and timezone. Show the case number.\n\n"
        "IMPORTANT: Never ask for information not listed above. Never ask the user to elaborate "
        "on their description. Accept each answer and move to the next step."
    ),
    tools=["get_user_context", "create_case", "emit_event"],
)
