# Salesforce Session Help Agent - Trace Analysis

> Analysis of 100 OpenTelemetry traces from the `session-help-agent` service in the `salesforce.agentforce` namespace.

## Trace Format

The traces use **OpenTelemetry OTLP JSON** (one trace per line), enriched with **Langfuse** observation attributes. Each trace represents a complete multi-turn customer support conversation.

### Resource Metadata (consistent across all traces)

| Field | Value |
|---|---|
| `service.name` | `session-help-agent` |
| `service.version` | `1.0.0` |
| `service.namespace` | `salesforce.agentforce` |
| `telemetry.sdk.name` | `opentelemetry` (Python SDK v1.27.0) |
| Schema | `https://opentelemetry.io/schemas/1.27.0` |

---

## Agent Architecture

### Single Agent with Topic-Based Intent Classification (Atlas Reasoning Engine)

This is a **single agent** (`Session Help Agent`) built on the **Agentforce platform** and powered by the **Atlas Reasoning Engine**. It is not a multi-agent system with separate sub-agents, but it does have an important layer of internal structure: **topic-based intent classification and action scoping**.

#### How Atlas Orchestrates

Atlas uses a **ReAct (Reason -> Act -> Observe) loop** rather than generating a fixed plan upfront. On each turn:
1. **Classify intent** into a Topic (which scopes available actions and instructions)
2. **Reason** about which action to take from the scoped set
3. **Act** by calling a tool
4. **Observe** the result and loop back to reasoning

This means the agent can dynamically adjust mid-conversation - reclassifying topics when user intent shifts, incorporating new information, and self-correcting. The reasoning itself is not visible in these traces (it happens inside the LLM call), but its effects are observable through topic reclassification patterns (see [Topic Map](#topic-map-inferred-from-traces) below).

#### What IS and IS NOT Visible in Traces

- **Not visible:** System prompts, reasoning/chain-of-thought, conversation history accumulation (each turn's `gen_ai.prompt` contains only the current user message - the platform manages context externally)
- **Visible:** Topic classification via tool name suffixes, action selection, tool inputs/outputs, topic reclassification across turns

#### Einstein Trust Layer

Not instrumented in traces, but a critical architectural component. Evidence of its operation is visible in the trace data through **data masking**: company names appear as `COMPANY_716d8357a670`, org IDs as `SFID_8029d5d124d8`, phone numbers as `PHONE_a0387962fa87`. The Trust Layer also provides:
- **Zero data retention** - prompts/responses never stored or used to train LLMs
- **Prompt injection defense** - built-in detection and rejection
- **Toxicity detection** - real-time content scanning before display
- **Dynamic grounding** - forces citation of sources from trusted data (visible in KB responses always including article URLs)

For reconstruction, the Trust Layer should be noted as a **needed component** but is not the primary focus.

### Model

- **Model ID:** `agentforce-v1`
- **Temperature:** `0.2`
- **Max tokens:** `4096`
- **Finish reason:** `stop` (100% of 397 chat turns - no truncations or errors)

### Span Hierarchy

Each trace has a clear 3-level tree:

```
Session Help Agent           (root span, kind=SERVER)
  gen_ai.chat_turn.N         (child of root, kind=CLIENT, one per conversation turn)
    tool_call.<ToolName>     (child of the turn that invoked it, kind=INTERNAL)
```

---

## Tool Inventory

### Summary Table

| Tool | Calls | Description |
|---|---|---|
| `GetDateTime` | 99 | Returns current UTC timestamp. Called as the first action in virtually every session. |
| `HC_ASA_Knowledge` | 115 | Vector search over Salesforce knowledge base. Returns scored articles with URLs. |
| `HC_ASA_UserContext_V2` | 77 | Retrieves authenticated user context: tenant name, org ID, product, success plan, timezone. Returns `NOT_AUTHENTICATED` for unauthenticated users. |
| `HC_ASA_CreateCase` | 17 | Creates a support case. Returns case number and tracking URL. |
| `HC_ASA_ValidateAndTransfer_V2` | 15 | Validates session eligibility and initiates transfer to a human support engineer. |
| `HC_ASA_Event` | 5 | Triggers client-side UI events (e.g., `LOGIN_REQUESTED`, `showOrgPickerModalForASA`). |
| `HC_ASA_Personalization_Solution` | 3 | Looks up Customer Success Manager info and personalized solutions for an account. |
| `HC_ASA_Get_Recent_Cases` | 1 | Retrieves a list of recent cases for the user. |
| `HC_ASA_Get_Case` | 1 | Looks up a specific case by case number. |
| `HC_ASA_Perform_Case_Action` | 1 | Performs an action on an existing case (e.g., reopen, update). |
| `RaiseFlagForSupervisor` | 1 | Escalates the conversation by raising a flag for a supervisor. |

**Total: 335 tool calls across 100 sessions (11 distinct tools).**

### Tool Name Suffixes as Topic Identifiers

Many tool names carry Salesforce record ID suffixes (e.g., `HC_ASA_Knowledge_179Ek000000DZb8`). These are **Topic record IDs** from the Agentforce platform configuration - they reveal which Topic the agent was operating under when it invoked a given tool. There are 21 raw tool name variants mapping to the 11 logical tools above. See [Topic Map](#topic-map-inferred-from-traces) for the full mapping.

### Tool Detail

#### `GetDateTime`
- **Input:** `{"tool_call_id": "datetime-example", "tool_name": "GetDateTime"}`
- **Output:** `{"output": "2025-07-11T20:05:10.129454409Z"}`
- Always the first tool called, always with a hardcoded `tool_call_id` of `"datetime-example"`.

#### `HC_ASA_Knowledge`
- **Input:** Implicitly takes the user's question (no explicit query parameter visible in traces).
- **Output:** `{"summary": "{\"searchResults\": [{\"vectorSearchScore\": ..., \"score\": ..., \"result\": [{\"value\": \"https://help.salesforce.com/s/articleView?id=...\", ...}]}]}"}`
- Returns vector search results with relevance scores, article URLs, and content snippets from multiple data sources (`CSG_CSG_Citations_ASA__dlm`, `CSG_UnifiedContent_Ext_V1_0_Meta__dlm`, etc.).
- Often called multiple times per turn (1-3 calls) to gather comprehensive results.

#### `HC_ASA_UserContext_V2`
- **Input:** No explicit parameters - reads from the session context.
- **Output (authenticated):** JSON with `tenantName`, `product`, `orgIdHelpText`, `timezone`, `successPlan`, `tenantConfirmationText`, `showDisclaimer`, `phoneNumberForSev1`, `validationErrorMessage`, etc.
- **Output (unauthenticated):** `"NOT_AUTHENTICATED"`
- Often called twice in a single turn (get context, then validate).

#### `HC_ASA_CreateCase`
- **Input:** Case details collected through conversation (description, severity, timezone, phone number).
- **Output:** Confirmation message with case number, subject, description, success plan, severity, and a tracking URL.

#### `HC_ASA_ValidateAndTransfer_V2`
- Validates whether the session is eligible for human agent transfer, then initiates the transfer.
- Returns session ID and validation status.

#### `HC_ASA_Event`
- Fires client-side UI events. Known events:
  - `LOGIN_REQUESTED` - prompts the user to authenticate
  - `showOrgPickerModalForASA` - opens org/tenant selection UI

---

## Conversation Flow Patterns

### Turn Distribution

| Turns | Traces | % |
|---|---|---|
| 2 | 43 | 43% |
| 3 | 17 | 17% |
| 4 | 14 | 14% |
| 5-7 | 10 | 10% |
| 8-12 | 16 | 16% |

Median: 2 turns. Mean: ~4 turns. Range: 2-12 turns.

### Turn 0: Bootstrap (Every Session)

Every session starts with an automated first turn:
- **User message:** `"What's the current date and time?"`
- **Tool call:** `GetDateTime`
- **Response:** The current UTC timestamp.

This is **not a real user question** - it's a platform-injected bootstrap turn to establish the session timestamp and warm up the agent.

### Pattern 1: Knowledge Answer (~50% of traces)

The most common flow. The agent searches the knowledge base and returns article links.

```
Turn 0: GetDateTime (bootstrap)
Turn 1: User asks question -> HC_ASA_Knowledge (1-3 calls) -> Answer with KB article links
```

Example topics: login errors, MFA setup, API limits, report issues, data loader problems.

### Pattern 2: Case Creation (~11% of traces)

A structured multi-turn data collection flow:

```
Turn 0: GetDateTime (bootstrap)
Turn 1: "create case" -> HC_ASA_UserContext_V2 -> Show tenant details, ask for confirmation
Turn 2: User confirms tenant -> Ask for timezone
Turn 3: User provides timezone -> Ask for issue description
Turn 4: User describes issue -> Ask for severity (1-4 scale)
Turn 5: User selects severity -> [If severity 1-2: ask for phone number]
Turn 6: User provides phone -> Show summary, ask for final confirmation
Turn 7: User confirms -> HC_ASA_CreateCase -> Show case number and tracking link
```

The severity scale is:
1. Critical production issue - business completely stopped or revenue impacted
2. Major functionality impacted and time-sensitive
3. Minor functionality impacted and time-sensitive
4. General inquiry, how-to or routine technical issue

Phone number is required for severity 1-2 (urgent issues).

### Pattern 3: Transfer to Human Agent (~7% of traces)

```
Turn 0: GetDateTime (bootstrap)
Turn 1: [Optional KB search] -> User requests transfer
Turn 2: HC_ASA_UserContext_V2 -> Check auth status
        If not authenticated: HC_ASA_Event (LOGIN_REQUESTED) -> Ask user to log in
Turn 3: "Automated message: log in successful" -> HC_ASA_UserContext_V2 -> Show tenant details
Turn 4: User confirms -> HC_ASA_ValidateAndTransfer_V2 -> "Transferring you now"
```

### Pattern 4: Mixed (Knowledge -> Escalation)

```
Turn 0: GetDateTime (bootstrap)
Turn 1: User asks question -> HC_ASA_Knowledge -> Provide answer
Turn 2: User not satisfied / requests more help -> HC_ASA_UserContext_V2
Turn 3: HC_ASA_CreateCase or HC_ASA_ValidateAndTransfer_V2
```

---

## Platform-Injected Automated Messages

The platform sends synthetic "user" messages to signal lifecycle events:

| Message | Meaning |
|---|---|
| `"Automated message: log in successful"` | User completed authentication |
| `"Automated message: Tenant Id Changed."` | User switched to a different org/tenant |
| `"Automated message: org selection cancelled"` | User dismissed the org picker modal |

These are not real user inputs - they're platform signals that the agent processes as conversation turns.

---

## Session Statistics

| Metric | Min | Max | Mean |
|---|---|---|---|
| Turn count | 2 | 12 | ~4 |
| Session duration | 24.8s | 149.1s | ~57s |
| Input tokens (per session) | 17 | 10,116 | 2,405 |
| Output tokens (per session) | 25 | 2,175 | 563 |
| Spans per trace | 4 | 18 | 8.3 |

- 100 unique session IDs, 88 unique conversation IDs
- All 832 spans across all traces have status code `1` (OK) - no errors in this dataset
- ~10% of traces contain Japanese responses (multilingual support)

---

## Topic Map (Inferred from Traces)

Topics are how Agentforce defines the jobs an agent will and won't do. Each topic carries natural-language instructions, a scope description, and a set of available actions. In the Agentforce platform, topics are configured by admins - the LLM classifies user intent into a topic, which then constrains available actions and provides topic-specific instructions.

The tool name suffixes in the traces are Salesforce record IDs that correspond to topic configurations. By analyzing which tools appear with which suffixes, and how suffixes change within a session, we can infer the topic structure.

### Suffix-to-Topic Mapping

| Suffix | Available Actions | Inferred Topic |
|---|---|---|
| `_179Ek000000GAvd` | `HC_ASA_UserContext_V2` | **User Context / Authentication** - Initial auth check and tenant identification. Often the first topic classified when a user's question requires knowing who they are. |
| `_179Ek000000DZb8` | `HC_ASA_Knowledge` | **Knowledge / FAQ** - General knowledge base search. The most common topic, handling how-to questions, error troubleshooting, and product documentation lookups. |
| `_179Ek000000DZb3` | `HC_ASA_CreateCase`, `HC_ASA_Event`, `HC_ASA_UserContext_V2`, `HC_ASA_ValidateAndTransfer_V2` | **Case Management / Support** - Full support operations: case creation, user context validation, transfer to human agents, and UI events. The broadest action set. |
| `_179Ek000000DZb5` | `HC_ASA_UserContext_V2`, `HC_ASA_ValidateAndTransfer_V2` | **Agent Transfer** - Focused on validating and transferring to a human support engineer. A narrower scope than DZb3. |
| `_179Ek000000DZb9` | `HC_ASA_Event` | **UI Events** - Triggers client-side UI events only. |
| `_179Ek000000DZbA` | `HC_ASA_Event`, `HC_ASA_Personalization_Solution` | **Personalization** - CSM lookup and personalized solutions, plus UI events. |
| `_179Ea0000058Pnx` | `HC_ASA_Get_Recent_Cases`, `HC_ASA_Perform_Case_Action` | **Existing Case Management** - Retrieve and perform actions on existing cases (distinct from case creation). |
| `_179Ea000005A3gD` | `RaiseFlagForSupervisor` | **Supervisor Escalation** - Raise a flag for supervisor review. |
| `_179Em00000080Kg` | `HC_ASA_Get_Case` | **Case Lookup** - Look up a specific case by number. |

Note: Some tools also appear **without suffixes** (e.g., plain `GetDateTime`, `HC_ASA_Knowledge`). `GetDateTime` is always unsuffixed (it's a global utility, not topic-scoped). Other unsuffixed tool calls appear in earlier traces and may represent a version of the agent before topic IDs were fully instrumented.

### Topic Reclassification (Observed in Traces)

A key behavior visible in the traces is **mid-conversation topic reclassification**. When user intent shifts, Atlas reclassifies to a new topic, changing the available action set. This directly mirrors the Agentforce demo behavior where the agent "pivots and reclassifies the topic" when a user changes what they're asking for.

Common reclassification patterns:

| Flow | Example |
|---|---|
| **Auth -> Knowledge** | User asks a question -> agent checks auth first (`GAvd`), then searches KB (`DZb8`). Seen in ~15 traces. |
| **Knowledge -> Case Creation** | KB answer insufficient -> user escalates to case creation (`DZb8` -> `DZb3`). Seen in ~7 traces. |
| **Knowledge -> Transfer** | KB answer insufficient -> user requests human agent (`DZb8` -> `DZb5`). Seen in ~3 traces. |
| **Auth -> Knowledge -> Case Creation** | Full escalation path: check auth, try KB, then create case (`GAvd` -> `DZb8` -> `DZb3`). Seen in ~3 traces. |
| **Existing Cases -> Case Creation -> Case Lookup** | User asks about existing cases, creates a new one, then looks it up (`58Pnx` -> `DZb3` -> `80Kg`). Seen in 1 trace. |

The "off-topic" classification mentioned in Agentforce documentation (where the agent redirects users back to approved topics) is not directly visible in these traces but would be an additional topic to configure.

### Topics Inferred from Public Documentation

Based on the Agentforce platform documentation and demo transcript, topics are configured with:

1. **A natural-language description** of the job to be done (e.g., "appointment management")
2. **A classification description** that helps the agent know when to enter this topic
3. **Scope and instructions** - natural language rules like "get the customer's email before scheduling" or "confirm the appointment once booked"
4. **Actions** - the tools available within this topic (flows, apex classes, prompts)

For the help agent specifically, we can infer these approximate topic configurations:

| Topic | Classification Trigger | Key Instructions (inferred from behavior) |
|---|---|---|
| Knowledge/FAQ | User asks a how-to question, troubleshooting query, or product question | Search knowledge base, provide article links, cite sources |
| Case Creation | User says "create case", "open a case", "log a case", or agent determines KB is insufficient | Get tenant confirmation, collect timezone, description, severity (1-4), phone for sev 1-2, confirm before creating |
| Agent Transfer | User says "transfer to agent", "talk to someone", or issue requires human support | Check auth status, prompt login if needed, validate session, initiate transfer |
| Existing Case Management | User asks about existing cases, case status, or case actions | Retrieve recent cases, look up specific cases, perform actions (reopen, update) |
| Personalization | User context suggests personalized solutions are available | Look up CSM info, provide tailored solutions |
| Off-Topic | User asks something outside the agent's scope | Redirect to approved topics |
| Harmful/Toxic | Prompt injection, inappropriate content, or malicious intent | Detect, classify, refuse to engage |

---

## Inferences About Agent Construction

### 1. Agentforce Platform Agent (Atlas Reasoning Engine)

The agent runs on the **Salesforce Agentforce** platform, powered by the **Atlas Reasoning Engine**. The platform provides:
- **Topic-based intent classification** - Atlas classifies user intent into Topics, which scope available actions and instructions (see [Topic Map](#topic-map-inferred-from-traces))
- **ReAct orchestration loop** - Reason -> Act -> Observe cycle with dynamic replanning (not a fixed action sequence)
- Session management and context (user auth state, tenant info)
- Tool/action registry with topic-scoped configuration (the `_179E...` suffixes)
- UI event system for triggering client-side interactions (login modals, org pickers)
- Conversation history management (not visible in individual turn prompts)
- Automated lifecycle messages injected as synthetic user turns
- **Einstein Trust Layer** - data masking, prompt injection defense, toxicity detection, grounding enforcement (needed but not primary reconstruction focus)

### 2. Topic-Based Action Scoping and Reclassification

Topics are configured with natural-language descriptions, classification triggers, scope constraints, and action sets. The LLM classifies intent into a topic, which then constrains available actions. When user intent shifts mid-conversation, Atlas reclassifies to a different topic - observable in the traces as tool suffix changes (e.g., `_179Ek000000DZb8` -> `_179Ek000000DZb3` when a knowledge query escalates to case creation).

This is fundamentally different from a traditional chatbot with dialogue trees. As the Agentforce documentation states: "There are no dialogue trees, just natural language descriptions that help the agent understand the job to be done." The LLM has agency to reason within the guardrails established by topic instructions.

### 3. Retrieval-Augmented Generation (RAG) via Data Cloud

The `HC_ASA_Knowledge` tool implements RAG via vector search backed by **Salesforce Data Cloud (Data 360)**. Data Cloud serves as the unified data foundation, connecting structured and unstructured data sources:
- `CSG_CSG_Citations_ASA__dlm` - Salesforce Help article citations
- `CSG_UnifiedContent_Ext_V1_0_Meta__dlm` - Unified content metadata (structured)
- `CSG_UnifiedContent_Ext_Unstruct_V1_0_Met__dlm` - Unstructured content metadata

Results include vector similarity scores, relevance scores, URLs, and content snippets. Data Cloud provides identity resolution, zero-copy data access, and 200+ connectors to external sources.

### 4. Stateful Session Model

The agent maintains state across turns without including conversation history in prompts. This implies the **platform handles context windowing** - the model likely receives the full conversation history injected at a layer not visible in these traces (possibly as part of a system prompt or via the model's own context management).

### 5. Natural Language Instructions Drive Structured Workflows

Case creation follows a rigid step-by-step flow (confirm tenant -> timezone -> description -> severity -> phone -> confirm -> create). Based on how Agentforce topics work, this behavior is driven by **natural language instructions within the Case Creation topic**, not hard-coded logic. The instructions likely read something like:

> "Get the customer's tenant confirmation before proceeding. Collect the timezone, issue description, and severity level (1-4). For severity 1-2, require a phone number with country code. Confirm all details with the customer before creating the case."

The LLM follows these instructions with agency to reason about edge cases (e.g., re-prompting when phone format is invalid), which is why it feels structured but handles curveballs naturally.

### 6. Authentication-Aware Branching

The agent checks authentication status via `HC_ASA_UserContext_V2` and branches accordingly:
- **Authenticated:** Proceeds with tenant-specific operations (case creation, transfer)
- **Unauthenticated:** Triggers `LOGIN_REQUESTED` event via `HC_ASA_Event`, then waits for the platform to inject the "log in successful" automated message before continuing

### 7. Low Temperature, Conservative Generation

Temperature `0.2` indicates the agent is configured for **deterministic, consistent responses** rather than creative variation - appropriate for a customer support context where accuracy and consistency matter.

---

## Reconstruction Notes

To reconstruct this agent, you would need:

### Core: LLM + ReAct Loop

1. **An LLM with tool-calling capability** configured at temperature 0.2, max_tokens 4096
2. **A ReAct orchestration loop** that on each turn: classifies intent into a topic, reasons about which action to take from the topic's scoped set, executes it, observes the result, and loops. Must support mid-conversation topic reclassification.

### Topics with Natural Language Instructions

3. **Topic definitions** (see [Topic Map](#topic-map-inferred-from-traces)), each containing:
   - A natural-language description of the job
   - A classification description (when to enter this topic)
   - Scope constraints and behavioral instructions
   - The set of available actions/tools
   - Key topics to define: Knowledge/FAQ, Case Creation, Agent Transfer, Existing Case Management, Personalization, Off-Topic, Harmful/Toxic

### Tools/Actions

4. **11 tools/actions** (see Tool Inventory above) with appropriate API backends:
   - A datetime utility
   - A knowledge base with vector search (RAG), ideally backed by a unified data platform
   - User context/authentication service
   - Case management CRUD operations
   - Session validation and human agent transfer
   - Client-side UI event triggering
   - Supervisor escalation
   - Personalization/CSM lookup

### Platform Layer

5. **Session management layer** that:
   - Injects automated lifecycle messages (login, tenant change, org selection)
   - Maintains conversation history across turns (the agent prompt per-turn only shows the current message, so history must be managed externally)
   - Handles the bootstrap turn (GetDateTime)
   - Manages authentication state

### Guardrails (Needed)

6. **Trust/safety layer** including:
   - Data masking for PII (company names, org IDs, phone numbers)
   - Prompt injection detection and rejection
   - Toxicity/harm detection
   - Off-topic detection and redirection to approved topics
   - Source citation enforcement (grounding)

### Other

7. **Multilingual support** (at minimum English and Japanese)

---

## Sources

This analysis is based on:
- 100 OpenTelemetry traces from the `session-help-agent` service (`resources/traces.jsonl`)
- Salesforce blog: support requests with Agentforce (`resources/resources.md`)
- Atlas Reasoning Engine documentation
- Einstein Trust Layer documentation
- Data Cloud / Data 360 documentation
- SalesforceBen review of the Agentforce help agent
- Agentforce demo transcript (`resources/how_agentforce_works.md`)
