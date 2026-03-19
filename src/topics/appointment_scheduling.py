from topics.base import Topic

APPOINTMENT_SCHEDULING = Topic(
    id="appointment_scheduling",
    name="Appointment Scheduling",
    classification_description=(
        "The user wants to schedule an appointment, book a session, or set up a meeting "
        "with Salesforce support or a specialist. Do NOT use this topic if the user mentions "
        "Expert Coaching Sessions or personalized sessions."
    ),
    instructions=(
        "You are helping the user schedule a support appointment.\n\n"
        "1. Call get_user_context to check authentication.\n"
        "   - If NOT_AUTHENTICATED: ask the user to log in first.\n"
        "2. Ask what type of appointment they need (technical review, implementation help, etc.).\n"
        "3. Ask for preferred date and time.\n"
        "4. Call schedule_appointment with the details.\n"
        "5. Confirm the appointment details with the user.\n\n"
        "Respond in the same language the user writes in."
    ),
    tools=["get_user_context", "schedule_appointment"],
)
