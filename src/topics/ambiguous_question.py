from topics.base import Topic

AMBIGUOUS_QUESTION = Topic(
    id="ambiguous_question",
    name="Ambiguous Question",
    classification_description=(
        "Used when the last message from the user asks about multiple, diverse topics "
        "in a single message that would require different tools or workflows to address."
    ),
    instructions=(
        "The user asked about multiple topics at once. Ask them to clarify which topic "
        "they'd like to address first. List the distinct topics you identified in their "
        "message and let them choose. Handle one topic at a time.\n\n"
        "Respond in the same language the user writes in."
    ),
    tools=[],
)
