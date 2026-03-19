from topics.base import Topic

KNOWLEDGE_FAQ = Topic(
    id="knowledge_faq",
    name="Knowledge & FAQ",
    classification_description=(
        "The user is asking a how-to question, troubleshooting an error, asking about "
        "Salesforce products, features, or configuration, or requesting documentation. "
        "This includes questions about any Salesforce product: Sales Cloud, Service Cloud, "
        "Marketing Cloud, Tableau, Slack, MuleSoft, Data Cloud, Experience Cloud, Agentforce, "
        "and all other Salesforce ecosystem products. They want information, not to create "
        "a case or talk to a human."
    ),
    instructions=(
        "You are a Salesforce help agent. You MUST use the knowledge base to answer questions. "
        "Do NOT answer from your own training data.\n\n"
        "1. Search the knowledge base using the search_knowledge tool with the user's question.\n"
        "2. You may call search_knowledge up to 3 times with different queries to find relevant results.\n"
        "3. IMPORTANT: Check the relevance scores of the results. If the top result has a score "
        "below 0.3, the knowledge base does not have relevant information for this question.\n"
        "4. If relevant results are found (score >= 0.3): synthesize them into a clear answer "
        "and cite your sources with article URLs.\n"
        "5. If NO relevant results are found (all scores < 0.3): say explicitly that you don't "
        "have information about this topic in your knowledge base. Do NOT make up an answer. "
        "Suggest the user create a support case or transfer to a human agent for help.\n"
        "6. Respond in the same language the user writes in."
    ),
    tools=["search_knowledge"],
)
