from topics.base import Topic

OFF_TOPIC = Topic(
    id="off_topic",
    name="Off Topic",
    classification_description=(
        "The user's request is outside the scope of Salesforce product support. This includes "
        "requests unrelated to Salesforce, general chitchat, or anything the agent is not "
        "designed to handle."
    ),
    instructions=(
        "The user's request is outside your scope. You are a Salesforce help agent that can:\n"
        "- Answer questions about Salesforce products and features\n"
        "- Create support cases\n"
        "- Transfer to a human support agent\n"
        "- Look up existing cases\n\n"
        "Politely redirect the user to one of these approved topics. Do not attempt to "
        "answer questions outside your scope."
    ),
    tools=[],
)
