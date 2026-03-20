# OTEL + GenAI Semantic Conventions Tracing - Design Spec

> Replace Braintrust SDK tracing with standard OpenTelemetry tracing using GenAI semantic conventions. Traces send directly to Braintrust's OTEL endpoint, producing spans that structurally match the real Agentforce agent.

## Goals

- **Primary:** Make our traces look structurally identical to the real agent's traces in the `synthetic-data-otel` Braintrust project.
- **Secondary:** Comply with OpenTelemetry GenAI semantic conventions so traces are portable and standardized.
- **Constraint:** No OTEL collector needed - send directly to Braintrust's OTEL endpoint.

## Reference

- Braintrust OTEL docs: https://www.braintrust.dev/docs/integrations/sdk-integrations/opentelemetry#manual-tracing
- Real agent spans: `resources/trace-analysis.md` (Deep OTEL Analysis section)
- Current tracing: `src/tracing/braintrust.py`

---

## Architecture

### Current

```
Orchestrator → Braintrust SDK (init_logger, start_span) → Braintrust API
```

Span names: `session`, `turn.N`, `classify`, `execute`, `validate`, `tool_call.X`

### New

```
Orchestrator → OTEL TracerProvider + OTLPSpanExporter → Braintrust OTEL endpoint
```

Span names match real agent: `gen_ai.chat_turn.N`, `agent.step.llm_step.*`, `agent.step.action_step.*`, etc.

### Connection

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(
    OTLPSpanExporter(
        endpoint="https://api.braintrust.dev/otel/v1/traces",
        headers={
            "Authorization": f"Bearer {BRAINTRUST_API_KEY}",
            "x-bt-parent": f"project_id:{PROJECT_ID}",
        },
    )
))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("sfdc-help-agent", "1.0.0")
```

No collector. Direct HTTP export to Braintrust.

---

## Span Hierarchy

### Real Agent (from OTEL data)

```
Session Help Agent                                          (root, task)
  Pipeline                                                  (task)
    gen_ai.chat_turn.N                                      (task)
      Topics                                                (task)
        agent.step.llm_step.AiCopilot__ReactTopicPrompt     (llm)
      agent.step.topic_step.<TopicName>                      (task)
        agent.step.llm_step.AiCopilot__ReactInitialPrompt   (llm)
        agent.step.action_step.<Topic>.<ToolName>            (tool)
      agent.step.llm_step.AiCopilot__ReactValidationPrompt  (llm)
    agent.step.session_end.CLOSED_*                          (task)
```

### Our New Hierarchy

```
Session Help Agent                                          (root, task)
  gen_ai.chat_turn.N                                        (task)
    agent.step.llm_step.AiCopilot__ReactTopicPrompt         (llm)  ← classifier
    agent.step.topic_step.<ClassifiedTopic>                  (task)  ← topic step
      agent.step.llm_step.AiCopilot__ReactInitialPrompt     (llm)  ← executor
      agent.step.action_step.<Topic>.<ToolName>              (tool) ← tool calls
    agent.step.llm_step.AiCopilot__ReactValidationPrompt    (llm)  ← validator (optional)
  agent.step.session_end.<EndType>                           (task)  ← on session end
```

We skip the `Pipeline` wrapper for simplicity (it's a container span with no logic).

---

## Span Type Mapping

Braintrust determines span type from `gen_ai.operation.name` or explicit `braintrust.span_attributes`:

| Span | Type | How to Set |
|---|---|---|
| Session root | `task` | `braintrust.span_attributes = {"type": "task"}` |
| `gen_ai.chat_turn.N` | `task` | `braintrust.span_attributes = {"type": "task"}` |
| `agent.step.llm_step.*` | `llm` | `gen_ai.operation.name = "chat"` (auto-maps to llm) |
| `agent.step.action_step.*` | `tool` | `gen_ai.operation.name = "execute_tool"` (auto-maps to tool) |
| `agent.step.topic_step.*` | `task` | `braintrust.span_attributes = {"type": "task"}` |
| `agent.step.session_end.*` | `task` | `braintrust.span_attributes = {"type": "task"}` |

---

## GenAI Semantic Attributes per Span Type

### LLM Spans (classifier, executor, validator)

```python
span.set_attribute("gen_ai.operation.name", "chat")
span.set_attribute("gen_ai.request.model", "claude-haiku-4-5")
span.set_attribute("gen_ai.request.temperature", 0.0)
span.set_attribute("gen_ai.request.max_tokens", 4096)

# Input: serialized messages array
span.set_attribute("gen_ai.prompt", json.dumps(messages))

# Output: serialized completion
span.set_attribute("gen_ai.completion", json.dumps([{"role": "assistant", "content": response}]))

# Token usage (set after LLM call returns)
span.set_attribute("gen_ai.usage.prompt_tokens", usage.prompt_tokens)
span.set_attribute("gen_ai.usage.completion_tokens", usage.completion_tokens)
```

### Tool Spans

```python
span.set_attribute("gen_ai.operation.name", "execute_tool")
span.set_attribute("gen_ai.tool.name", "HC_ASA_Knowledge")
span.set_attribute("braintrust.input", json.dumps(tool_input))
span.set_attribute("braintrust.output", json.dumps(tool_output))
span.set_attribute("braintrust.metrics.latency_ms", latency_ms)
```

### Task Spans (session, turn, topic_step, session_end)

```python
span.set_attribute("braintrust.span_attributes", json.dumps({"type": "task"}))
span.set_attribute("braintrust.input", user_message)
span.set_attribute("braintrust.output", agent_response)
span.set_attribute("braintrust.metadata", json.dumps({
    "topic": topic_id,
    "topic_changed": True,
}))
```

---

## Additional OTEL Attributes (from real traces)

These attributes appear on the real agent's spans and should be included for fidelity:

| Attribute | Source | Value |
|---|---|---|
| `interaction.step.id` | Generated UUID per step | Unique step identifier |
| `interaction.step.name` | Span name | e.g., `AiCopilot__ReactInitialPrompt` |
| `interaction.step.type` | Step category | `LLM_STEP`, `ACTION_STEP`, `TOPIC_STEP` |
| `service.name` | Resource attribute | `session-help-agent` |
| `service.version` | Resource attribute | `1.0.0` |
| `service.namespace` | Resource attribute | `salesforce.agentforce` |

### On LLM Spans (from real `langfuse.observation.input/output`)

The real agent logs rich structured data on LLM spans:

**Input attributes:**
- `enableCitations`: true
- `enableOutputSafetyScoring`: true
- `intentLabel`: the classified topic ID
- `promptName`: the prompt template name
- `stepType`: `LLM_STEP`
- `toolConfig`: `{"mode": "auto", "parallel_calls": true}`
- `tools`: array of available tool schemas

**Output attributes:**
- `historyEntryType`: `LLM_COMPLETION_RESPONSE`
- `llmResponse`: the actual response text
- `plannerMessageType`: `LLM_COMPLETION_RESPONSE`
- `toolInvocations`: array of tool calls made

We map these to `braintrust.metadata.*` attributes.

---

## Implementation

### New Dependencies

```toml
# Add to pyproject.toml
"opentelemetry-api>=1.27.0",
"opentelemetry-sdk>=1.27.0",
"opentelemetry-exporter-otlp-proto-http>=1.27.0",
```

Remove `braintrust` from required dependencies (move to optional if needed for evals later).

### Files Changed

**Replace:** `src/tracing/braintrust.py` → Complete rewrite using OTEL SDK

```python
# src/tracing/braintrust.py
from __future__ import annotations
import json
import os
from typing import Any
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


class TracingManager:
    def __init__(self, project: str, api_key: str, project_id: str = ""):
        self._project = project
        self._api_key = api_key
        self._tracer = None

        if api_key:
            try:
                resource = Resource.create({
                    "service.name": "session-help-agent",
                    "service.version": "1.0.0",
                    "service.namespace": "salesforce.agentforce",
                })
                provider = TracerProvider(resource=resource)
                provider.add_span_processor(BatchSpanProcessor(
                    OTLPSpanExporter(
                        endpoint="https://api.braintrust.dev/otel/v1/traces",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "x-bt-parent": f"project_id:{project_id}" if project_id else f"project_name:{project}",
                        },
                    )
                ))
                trace.set_tracer_provider(provider)
                self._tracer = trace.get_tracer("sfdc-help-agent", "1.0.0")
            except Exception:
                pass

    def start_session(self, session_id: str) -> OtelSpan:
        if self._tracer is None:
            return NoopSpan()
        span = self._tracer.start_span(
            name="Session Help Agent",
            attributes={
                "braintrust.span_attributes": json.dumps({"type": "task"}),
                "session.id": session_id,
            },
        )
        return OtelSpan(span, self._tracer)
```

**New class: `OtelSpan`** - Wraps OTEL spans with our convenience methods:

```python
class OtelSpan:
    """Wrapper around OTEL span with convenience methods matching our existing interface."""

    def __init__(self, span, tracer):
        self._span = span
        self._tracer = tracer
        self._context = trace.set_span_in_context(span)

    def start_span(self, name: str, span_attributes: dict | None = None, **kwargs) -> OtelSpan:
        attrs = {}
        if span_attributes:
            attrs["braintrust.span_attributes"] = json.dumps(span_attributes)
        child = self._tracer.start_span(name=name, context=self._context, attributes=attrs)
        return OtelSpan(child, self._tracer)

    def log(self, input: Any = None, output: Any = None, metadata: dict | None = None,
            metrics: dict | None = None, **kwargs) -> None:
        if input is not None:
            self._span.set_attribute("braintrust.input", json.dumps(input) if not isinstance(input, str) else input)
        if output is not None:
            self._span.set_attribute("braintrust.output", json.dumps(output) if not isinstance(output, str) else output)
        if metadata:
            self._span.set_attribute("braintrust.metadata", json.dumps(metadata))
        if metrics:
            for k, v in metrics.items():
                self._span.set_attribute(f"braintrust.metrics.{k}", v)

    def set_llm_attributes(self, model: str, temperature: float, messages: list,
                           completion: str, prompt_tokens: int = 0,
                           completion_tokens: int = 0, **kwargs) -> None:
        """Set GenAI semantic convention attributes for LLM spans."""
        self._span.set_attribute("gen_ai.operation.name", "chat")
        self._span.set_attribute("gen_ai.request.model", model)
        self._span.set_attribute("gen_ai.request.temperature", temperature)
        self._span.set_attribute("gen_ai.prompt", json.dumps(messages))
        self._span.set_attribute("gen_ai.completion", json.dumps([{"role": "assistant", "content": completion}]))
        if prompt_tokens:
            self._span.set_attribute("gen_ai.usage.prompt_tokens", prompt_tokens)
        if completion_tokens:
            self._span.set_attribute("gen_ai.usage.completion_tokens", completion_tokens)

    def set_tool_attributes(self, tool_name: str, input_data: dict, output_data: Any,
                            latency_ms: float = 0) -> None:
        """Set attributes for tool execution spans."""
        self._span.set_attribute("gen_ai.operation.name", "execute_tool")
        self._span.set_attribute("gen_ai.tool.name", tool_name)
        self._span.set_attribute("braintrust.input", json.dumps(input_data))
        self._span.set_attribute("braintrust.output", json.dumps(output_data) if isinstance(output_data, dict) else str(output_data))
        if latency_ms:
            self._span.set_attribute("braintrust.metrics.latency_ms", latency_ms)

    def set_step_attributes(self, step_name: str, step_type: str) -> None:
        """Set interaction step attributes matching real agent traces."""
        self._span.set_attribute("interaction.step.id", str(uuid4()))
        self._span.set_attribute("interaction.step.name", step_name)
        self._span.set_attribute("interaction.step.type", step_type)

    def export(self) -> str:
        """Return empty string - not needed for OTEL (parent context handled by context propagation)."""
        return ""

    def end(self) -> None:
        self._span.end()


class NoopSpan:
    """No-op span for when tracing is disabled."""
    def start_span(self, **kwargs) -> NoopSpan:
        return NoopSpan()
    def log(self, **kwargs) -> None:
        pass
    def set_llm_attributes(self, **kwargs) -> None:
        pass
    def set_tool_attributes(self, **kwargs) -> None:
        pass
    def set_step_attributes(self, **kwargs) -> None:
        pass
    def export(self) -> str:
        return ""
    def end(self) -> None:
        pass
```

### Orchestrator Changes

Update span creation calls to use new names and attributes:

```python
# Session span (unchanged location, new name)
session_span = self._tracing.start_session(session_id)

# Turn span
turn_span = session_span.start_span(
    name=f"gen_ai.chat_turn.{session.turn_count}",
    span_attributes={"type": "task"},
)

# Classifier span
classify_span = turn_span.start_span(
    name="agent.step.llm_step.AiCopilot__ReactTopicPrompt",
    span_attributes={"type": "llm"},
)
classify_span.set_step_attributes("AiCopilot__ReactTopicPrompt", "LLM_STEP")
# After LLM call:
classify_span.set_llm_attributes(
    model=settings.classifier_model, temperature=settings.classifier_temperature,
    messages=[...], completion=result_json, prompt_tokens=..., completion_tokens=...,
)

# Topic step span
topic_span = turn_span.start_span(
    name=f"agent.step.topic_step.{topic_id}",
    span_attributes={"type": "task"},
)
topic_span.set_step_attributes(topic_id, "TOPIC_STEP")

# Executor span (nested under topic_step)
execute_span = topic_span.start_span(
    name="agent.step.llm_step.AiCopilot__ReactInitialPrompt",
    span_attributes={"type": "llm"},
)
execute_span.set_step_attributes("AiCopilot__ReactInitialPrompt", "LLM_STEP")

# Tool call span (nested under topic_step)
tool_span = topic_span.start_span(
    name=f"agent.step.action_step.{topic_id}.{tool_name}",
    span_attributes={"type": "tool"},
)
tool_span.set_step_attributes(tool_name, "ACTION_STEP")
tool_span.set_tool_attributes(tool_name, params, result.output, result.latency_ms)

# Validator span
validate_span = turn_span.start_span(
    name="agent.step.llm_step.AiCopilot__ReactValidationPrompt",
    span_attributes={"type": "llm"},
)
validate_span.set_step_attributes("AiCopilot__ReactValidationPrompt", "LLM_STEP")

# Session end span
end_span = session_span.start_span(
    name=f"agent.step.session_end.{end_type}",  # CLOSED_USER_REQUEST, CLOSED_TRANSFERRED, CLOSED_ACTION
    span_attributes={"type": "task"},
)
```

### Executor Changes

The executor currently doesn't have access to token usage from the streaming API (tokens are counted by Braintrust gateway). For OTEL, we need to capture usage from the LLM response:

- For non-streaming: `response.usage.prompt_tokens`, `response.usage.completion_tokens`
- For streaming: accumulate from stream chunks (OpenAI SDK provides usage in the final chunk with `stream_options={"include_usage": True}`)

Add `stream_options={"include_usage": True}` to the streaming create call.

### Classifier Changes

The classifier gets token usage directly from the non-streaming response. Pass usage data back so the orchestrator can set LLM attributes on the classify span.

Update `ClassifierResult` to include token usage:

```python
@dataclass
class ClassifierResult:
    topic_id: str
    confidence: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw_messages: list = field(default_factory=list)  # for tracing
    raw_completion: str = ""  # for tracing
```

---

## Configuration

### New Environment Variables

| Variable | Default | Description |
|---|---|---|
| `BRAINTRUST_PROJECT_ID` | (derived from API) | Project ID for OTEL x-bt-parent header |

The existing `BRAINTRUST_API_KEY` is reused for OTEL auth.

### New Dependencies

```toml
"opentelemetry-api>=1.27.0",
"opentelemetry-sdk>=1.27.0",
"opentelemetry-exporter-otlp-proto-http>=1.27.0",
```

---

## Files Changed

| File | Change |
|---|---|
| `src/tracing/braintrust.py` | **Rewrite** - OTEL TracerProvider + OtelSpan wrapper |
| `src/agent/orchestrator.py` | Update span names and add GenAI/step attributes |
| `src/agent/executor.py` | Add `stream_options`, capture token usage, pass to span |
| `src/agent/classifier.py` | Return token usage in ClassifierResult |
| `src/agent/validator.py` | Return token usage for span attributes |
| `src/agent/models.py` | Add usage fields to ClassifierResult |
| `pyproject.toml` | Add OTEL dependencies |
| `.env.example` | Add `BRAINTRUST_PROJECT_ID` |
| `tests/tracing/test_braintrust.py` | Update for new OTEL-based interface |

## What This Does NOT Change

- `src/tools/` - Tools are unchanged
- `src/topics/` - Topics are unchanged
- `simulator/` - Simulator calls orchestrator which handles tracing internally
- `scraper/` - No tracing involvement
- `src/app.py` - Chainlit app unchanged (orchestrator handles tracing)
