from topics.base import Topic

OFF_TOPIC = Topic(
    id="off_topic",
    name="Off Topic",
    classification_description=(
        "The user's request is completely unrelated to Salesforce or any of its products. "
        "Examples: asking about the weather, sports, non-Salesforce software, or general "
        "knowledge questions with no Salesforce connection. Also use for simple greetings "
        "like 'hi' or 'hello' with no specific request."
    ),
    instructions=(
        "You are a Salesforce help agent. If the user is greeting you, respond warmly and "
        "let them know what you can help with. If their request is outside your scope, "
        "politely redirect them.\n\n"
        "You can help with:\n"
        "- Answering questions about Salesforce products and features\n"
        "- Creating support cases\n"
        "- Transferring to a human support agent\n"
        "- Looking up existing cases\n\n"
        "Do not attempt to answer questions unrelated to Salesforce."
    ),
    tools=[],
)
