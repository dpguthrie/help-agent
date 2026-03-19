from topics.base import Topic

KNOWLEDGE_FAQ = Topic(
    id="knowledge_faq",
    name="Knowledge & FAQ",
    classification_description=(
        "The user is asking a how-to question, troubleshooting an error, asking about "
        "Salesforce features or configuration, or requesting documentation. They want "
        "information, not to create a case or talk to a human."
    ),
    instructions=(
        "You are a Salesforce help agent answering questions using the knowledge base.\n\n"
        "1. Search the knowledge base using the search_knowledge tool with the user's question.\n"
        "2. You may call search_knowledge up to 3 times per turn to gather comprehensive results.\n"
        "3. Synthesize the results into a clear, helpful answer.\n"
        "4. Always cite your sources with article URLs.\n"
        "5. If the knowledge base has no relevant results, say so honestly and suggest "
        "the user create a support case or transfer to a human agent.\n"
        "6. Respond in the same language the user writes in."
    ),
    tools=["search_knowledge"],
)
