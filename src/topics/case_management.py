from topics.base import Topic

CASE_MANAGEMENT = Topic(
    id="case_management",
    name="Case Management",
    classification_description=(
        "The user is asking about an existing case, wants to check case status, look up "
        "a case number, see recent cases, or perform an action on an existing case "
        "(reopen, update). They are NOT trying to create a new case."
    ),
    instructions=(
        "You are helping the user manage their existing support cases.\n\n"
        "1. Call get_user_context to check authentication.\n"
        "   - If NOT_AUTHENTICATED: ask the user to log in first.\n"
        "2. Based on the user's request:\n"
        "   - To list recent cases: call get_recent_cases.\n"
        "   - To look up a specific case: call get_case with the case number.\n"
        "   - To perform an action (reopen, update): call perform_case_action.\n"
        "3. Present the results clearly.\n"
        "4. Respond in the same language the user writes in."
    ),
    tools=["get_user_context", "get_recent_cases", "get_case", "perform_case_action"],
)
