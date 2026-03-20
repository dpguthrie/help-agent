from topics.base import Topic

AMBIGUOUS_QUESTION = Topic(
    id="ambiguous_question",
    name="Ambiguous Question",
    classification_description=(
        "Used when the last message from the user asks about multiple, diverse topics "
        "in a single message that would require different tools or workflows to address.\n\n"
        "Do NOT use this topic if:\n"
        "- The user is in the middle of a case creation, transfer, appointment, or other multi-step flow\n"
        "- The user is providing information that was requested (severity, timezone, description, etc.)\n"
        "- The user is responding to a confirmation question with details\n"
        "- The message is a short response like 'yes', 'no', a number, or a timezone\n"
        "Only use this topic for the FIRST message in a conversation that genuinely covers "
        "multiple unrelated topics."
    ),
    instructions=(
        "The user asked about multiple topics at once. Ask them to clarify which topic "
        "they'd like to address first. List the distinct topics you identified in their "
        "message and let them choose. Handle one topic at a time.\n\n"
        "Respond in the same language the user writes in."
    ),
    tools=[],
)
