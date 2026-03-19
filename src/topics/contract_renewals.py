from topics.base import Topic

CONTRACT_RENEWALS = Topic(
    id="contract_renewals",
    name="Contract Renewals",
    classification_description=(
        "The user is seeking help or information about their active contract renewals, "
        "especially when they haven't found answers from the knowledge base. This includes "
        "questions about renewal dates, terms, pricing, or connecting with their Renewal Manager."
    ),
    instructions=(
        "You are helping the user with contract renewal information. Follow a step-by-step "
        "approach, presenting one question at a time.\n\n"
        "1. Call get_user_context to check authentication.\n"
        "   - If NOT_AUTHENTICATED: ask the user to log in first.\n"
        "2. Call retrieve_account_contracts to get their active contracts.\n"
        "3. Present the contract list and ask which one they need help with.\n"
        "4. Call retrieve_contract_details for the selected contract.\n"
        "5. Present the renewal details (dates, terms, renewal manager).\n"
        "6. If requested, offer to connect them with their Renewal Manager.\n\n"
        "Respond in the same language the user writes in."
    ),
    tools=["get_user_context", "retrieve_account_contracts", "retrieve_contract_details"],
)
