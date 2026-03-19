from topics.base import Topic

INAPPROPRIATE_CONTENT = Topic(
    id="inappropriate_content",
    name="Inappropriate Content",
    classification_description=(
        "Used when a message contains any of the following content: violence, sexual, "
        "misinformation, harassment, illegal activities, suicide and self harm, sensitive "
        "events, harmful behaviors, bias, toxicity, or offensive language"
    ),
    instructions=(
        "The user's message contains inappropriate content. Do not engage with or repeat "
        "the inappropriate content. Respond briefly and professionally: acknowledge that "
        "you cannot assist with this type of request, and offer to help with Salesforce-related "
        "topics instead. Do not lecture or moralize."
    ),
    tools=[],
)
