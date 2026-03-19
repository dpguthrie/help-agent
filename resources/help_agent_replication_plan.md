# Help Agent Replication Plan (Single-Agent Priority)

## Goal
Build one Help Agent that mimics Salesforce Help Agent behavior as closely as possible for a single use case, with Braintrust tracing from day one.

## Priority Order
1. Build the agent behavior and workflows (primary).
2. Add robust Braintrust trace instrumentation (primary).
3. Build evals/scorers with Salesforce team input (secondary, later).

## Scope Decisions
- In scope now:
  - single-agent behavior replication
  - runtime orchestration, tools, guardrails, state handling
  - trace-quality observability in Braintrust
- Explicitly not a current priority:
  - multi-product variants (Tableau/Informatica/etc.)
  - full scorer suite and heavy offline eval framework

## Inputs Used
- `traces.jsonl` (100 sessions)
- `how_agentforce_works.md`
- `example_agentforce_flow.png`
- `resources.md`
- your call notes

## Behavioral Fidelity Targets (From Traces)

### Core flow types to preserve
- Knowledge-answer flows (majority)
- Case-intake and case-creation flows
- Transfer-to-human flows
- Scope/safety refusal flows
- Login/org event-handling flows

### Quant profile to guide build focus
- Sessions: `100`
- Flow classes:
  - `knowledge_answer`: `61`
  - `case_creation`: `16`
  - `transfer`: `8`
  - `scope_guardrail`: `6`
  - `greeting`: `2`
  - `other`: `7`
- Avg turns: `~3.97` (long-tail up to `10-12`)

### Tooling priorities observed
- High priority:
  - `HC_ASA_Knowledge*`
  - `HC_ASA_UserContext_V2*`
  - `HC_ASA_CreateCase*`
  - `HC_ASA_ValidateAndTransfer_V2*`
- Important supporting tools:
  - `HC_ASA_Event*`
  - `HC_ASA_Get_Recent_Cases*`
  - `HC_ASA_Get_Case*`
  - `HC_ASA_Perform_Case_Action*`
  - `RaiseFlagForSupervisor*`

## Runtime Model to Implement

### Modes
- `knowledge_assist`
- `case_intake`
- `transfer_intake`
- `case_followup`
- `scope_guardrail`
- `session_event_handling`

### Case state machine (must match behavior)
- Confirm tenant/org context
- Collect missing required fields (timezone, issue description, severity, phone if required)
- Show confirmation summary
- Call create-case tool
- Return structured success response

### Transfer state machine (must match behavior)
- Detect transfer intent
- Validate eligibility
- Transfer if eligible
- Clear fallback if not eligible
- Supervisor escalation path when applicable

### Guardrails
- Refuse out-of-scope and unsafe requests
- Redirect to supported scope
- Prevent repeated non-progress loops

### Event handling
- Handle login/org events as state transitions
- Resume pending workflow after event completion

## Canonical Tool Interfaces
Use stable internal names with adapter mapping to environment-specific tool IDs.
- `get_datetime`
- `get_user_context`
- `search_knowledge`
- `create_case`
- `validate_transfer`
- `emit_event`
- `get_recent_cases`
- `get_case`
- `perform_case_action`
- `raise_supervisor_flag`
- `get_personalization`

## Required Session State
- Identity/context:
  - `tenant`, `product`, `org_id`, `locale`, `timezone`, `is_authenticated`
- Case intake:
  - `issue_summary`, `description`, `severity`, `phone`, `confirmation`
- Transfer:
  - `transfer_requested`, `transfer_eligible`, `validation_passed`
- Workflow control:
  - `mode`, `pending_action`, `last_tool_outcome`, `event_state`, `loop_count`

Observed context fields that should be first-class:
- `canCreateCase`
- `isSeverityQuestionRequired`
- `isChatTransferAllowed`
- `isTenantConfirmationRequired`
- `isOrgIdRequired`
- `isLoginRequired`
- `hasPhoneNumber`
- `endUserLanguage`

## Architecture (Single Agent)
- Orchestrator:
  - explicit mode transitions
  - topic/instruction/action policy routing
- Retrieval:
  - source-grounded responses
  - clarification-first when confidence is low
- Guardrail layer:
  - scope + safety checks
  - loop breaker
- Tool adapter layer:
  - canonical tool API
  - retries/timeouts/error normalization
- Memory/state store:
  - durable session slots
  - event-aware workflow continuation

## Workstream A (Now): Build Agent + Tracing

### A0: Spec lock (minimal)
- Freeze mode/state/tool contracts.
- Freeze response templates for:
  - knowledge answers
  - case confirmations/success
  - transfer responses
  - guardrails

### A1: Core behavior
- Implement orchestrator modes.
- Implement retrieval and guardrail behavior.
- Implement anti-loop + clarification logic.

### A2: Case + transfer
- Implement case intake/create flow.
- Implement transfer validation/escalation flow.
- Include ArcGIS escalation event mapping in traces.

### A3: Braintrust tracing (required now)
- Instrument full trace/span hierarchy.
- Capture structured metadata:
  - mode transitions
  - tool calls/results
  - slot state changes
  - escalation outcomes
  - latency/token usage

### A4: Trace replay hardening
- Replay sample traces against implementation.
- Close biggest behavioral gaps first (case + transfer + guardrail correctness).

## Workstream B (Later, Secondary): Evals/Scorers
This can be done with Salesforce team collaboration.
- Add online scorers (trace/span).
- Add topic clustering and annotation workflows.
- Add offline experiments and version comparisons.

## Immediate Next Step
Implement Workstream A0-A1 artifacts first:
- canonical JSON contracts (`session_state`, `tool_io`, `event_types`)
- orchestrator skeleton with modes and transitions
- Braintrust trace schema and instrumentation hooks

## References (Implementation-Relevant)
- `/Users/dpg/repos/sfdc/traces.jsonl`
- `/Users/dpg/repos/sfdc/how_agentforce_works.md`
- `/Users/dpg/repos/sfdc/resources.md`
- https://www.salesforce.com/ap/agentforce/how-it-works/
- https://www.salesforce.com/artificial-intelligence/trusted-ai/
- https://www.salesforceben.com/agentforce-is-now-available-on-salesforce-help-but-is-it-actually-helpful/
