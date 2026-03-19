import uuid
from tools.base import Tool, ToolResult


class ScheduleAppointmentTool(Tool):
    name = "schedule_appointment"
    description = "Schedules a support appointment with Salesforce."
    parameters = {
        "type": "object",
        "properties": {
            "appointment_type": {"type": "string", "description": "Type of appointment."},
            "preferred_date": {"type": "string", "description": "Preferred date (YYYY-MM-DD)."},
            "preferred_time": {"type": "string", "description": "Preferred time."},
        },
        "required": ["appointment_type", "preferred_date"],
    }

    async def execute(self, params, session):
        if session is None or session.auth_state is None:
            return ToolResult(status="ok", output="NOT_AUTHENTICATED")
        appointment_id = f"APT-{uuid.uuid4().hex[:8].upper()}"
        return ToolResult(status="ok", output={
            "appointment_id": appointment_id,
            "appointment_type": params["appointment_type"],
            "date": params["preferred_date"],
            "time": params.get("preferred_time", "TBD"),
            "tenant_name": session.auth_state.tenant_name,
            "message": f"Appointment {appointment_id} scheduled for {params['preferred_date']}.",
        })
