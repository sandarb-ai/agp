# AI Governance Proof (AIGP)&trade;

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Spec](https://img.shields.io/badge/Spec-v0.3.0-violet.svg)](./spec/aigp-spec.md)
[![Schema](https://img.shields.io/badge/JSON_Schema-valid-green.svg)](./schema/aigp-event.schema.json)

**An open specification for capturing cryptographic proof of every AI agent governance action.**

AIGP is not a product feature — it's a proposal for a common language that any platform, framework, or organization can adopt. We don't claim it's the final answer. We offer it as a starting point, and we welcome anyone who wants to help shape it.

---

## Contents

- [Why AIGP?](#why-aigp)
- [Quick Start](#quick-start)
- [Core Schema](#core-schema)
- [Event Types](#event-types)
- [Use Cases](#use-cases)
- [Instrumentation Conventions](#instrumentation-conventions)
- [Example Event](#example-event)
- [OpenTelemetry Integration](#opentelemetry-integration)
- [Reference Implementation](#reference-implementation)
- [Contributing](#contributing)

---

## Why AIGP?

AI agents are being deployed across every industry. They access company data, make decisions, and interact with customers. Regulators, auditors, and security teams all need to answer the same fundamental question:

> **"Prove your AI Agents used the approved Prompts, Tools, and Policies—every single time."**

Today, every team answers this differently. Some grep through logs. Some build custom audit tables. Some don't track it at all. There is no shared format for what an AI governance proof should look like.

AIGP is a structured, cryptographic event format that captures **what happened**, **who did it**, **what data was involved**, and **whether it was allowed**.

---

## Quick Start

An AIGP event is a single JSON record that captures proof of one governance action. Any system can produce them — just emit JSON:

```python
import json, hashlib, uuid, datetime

def create_aigp_event(agent_id, policy_name, content, trace_id):
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "INJECT_SUCCESS",
        "event_category": "inject",
        "event_time": datetime.datetime.utcnow().isoformat() + "Z",
        "agent_id": agent_id,
        "policy_name": policy_name,
        "policy_version": 1,
        "governance_hash": hashlib.sha256(content.encode()).hexdigest(),
        "trace_id": trace_id,
    }

# Emit the event to your log, Kafka, or any store
event = create_aigp_event("agent.trading-bot", "policy.trading-limits", "Max position: $10M", "trace-001")
print(json.dumps(event, indent=2))
```

That's it. No SDK required, no vendor lock-in. If your event conforms to the schema, it's AIGP-compliant.

---

## Core Schema

Every AIGP event has these required fields. The full schema (25+ fields) is in the [formal specification](./spec/aigp-spec.md).

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | UUID | Unique identifier for this event |
| `event_type` | String | What happened (`INJECT_SUCCESS`, `POLICY_VIOLATION`, etc.) |
| `event_category` | String | Grouping (`inject`, `audit`, `agent-lifecycle`, etc.) |
| `event_time` | DateTime | When the governance action occurred (UTC, ms precision) |
| `agent_id` | String | The agent that triggered this action |
| `governance_hash` | String | SHA-256 hash of the governed content — the cryptographic proof |
| `trace_id` | String | Distributed trace ID for end-to-end correlation |

Optional but recommended: `policy_name`, `policy_version`, `prompt_name`, `prompt_version`, `data_classification`, `org_id`, `denial_reason`, `severity`, `metadata`.

> **Full schema:** [`spec/aigp-spec.md`](./spec/aigp-spec.md) | **JSON Schema:** [`schema/aigp-event.schema.json`](./schema/aigp-event.schema.json)

### Design Principles

1. **Open and protocol-agnostic.** Works with A2A, MCP, REST, gRPC, or anything else. The format doesn't assume a transport.
2. **Tamper-evident by default.** Every event includes a `governance_hash`. If content changes between creation and storage, the hash won't match.
3. **Traceable end-to-end.** Every event carries a `trace_id`. One query reconstructs the full chain: which agent, which prompt, which policy, what happened.
4. **Flat and queryable.** Single wide event table — no joins for governance queries. Designed for OLAP engines like ClickHouse but works with any store.
5. **Extensible, not rigid.** The `metadata` object and `ext_`-prefixed fields allow domain-specific data without breaking the schema.

---

## Event Types

AIGP defines 16 event types across 7 categories. Implementations may extend these using the same `RESOURCE_ACTION` naming convention.

| Category | Event Types | When emitted |
|----------|------------|--------------|
| Policy Injection | `INJECT_SUCCESS`, `INJECT_DENIED` | Agent requests governed policy |
| Prompt Usage | `PROMPT_USED`, `PROMPT_DENIED` | Agent pulls an approved prompt |
| Agent Lifecycle | `AGENT_REGISTERED`, `AGENT_APPROVED`, `AGENT_DEACTIVATED` | Agent joins, is approved, or leaves |
| Policy Lifecycle | `POLICY_CREATED`, `POLICY_VERSION_APPROVED`, `POLICY_ARCHIVED` | Policy is created, versioned, or retired |
| Prompt Lifecycle | `PROMPT_VERSION_CREATED`, `PROMPT_VERSION_APPROVED` | Prompt is created or approved |
| Governance Proof | `GOVERNANCE_PROOF` | Cryptographic proof-of-delivery recorded |
| Policy | `POLICY_VIOLATION` | A governance policy is violated |
| A2A | `A2A_CALL` | Agent-to-agent protocol call |

---

## Use Cases

AIGP is designed to work across industries where AI agents handle sensitive data or regulated processes:

- **Financial Services** — Prove trading agents only accessed approved limits and MNPI controls were enforced (SEC, FINRA)
- **Healthcare** — Audit that patient-facing agents used HIPAA-compliant consent rules and PHI access was minimum-necessary
- **Legal** — Track which contract review agents used which prompt versions and whether attorney-client privilege rules were followed (ABA Model Rules)
- **Enterprise AI** — Provide your CISO and compliance team with a single audit trail across all AI agents, regardless of framework

---

## Instrumentation Conventions

A common event format only works if the *values inside the events* follow shared conventions. These are inspired by [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/) and adapted for AI governance.

### Resource Naming (AGRN)

Every governed resource follows a typed, kebab-case naming convention called **Agent Governance Resource Names (AGRN)**:

| Resource | Format | Example |
|----------|--------|---------|
| Agent | `agent.<kebab-name>` | `agent.trading-bot-v2` |
| Policy | `policy.<kebab-name>` | `policy.eu-refund-policy` |
| Prompt | `prompt.<kebab-name>` | `prompt.customer-support-v3` |
| Organization | `org.<kebab-name>` | `org.finco` |

**Rules:** Lowercase only. Letters, numbers, and hyphens. No underscores, no double hyphens, no trailing hyphens.

### Data Classification

| Level | Value | Meaning | Example |
|-------|-------|---------|---------|
| 1 | `public` | Safe for external sharing | Product FAQ, public docs |
| 2 | `internal` | Company use only | Engineering runbooks |
| 3 | `confidential` | Need-to-know | Trading limits, customer PII |
| 4 | `restricted` | Highest sensitivity, regulatory | MNPI, pre-release financials |

### Governance Hash

The `governance_hash` is computed over the governed content at the time of delivery. It proves the exact content that was delivered — if even one character changes, the hash changes.

```python
import hashlib
content = "You are a trading assistant. Max position: $10M..."
governance_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
```

If the same content is delivered to two agents, they produce the same hash — proving identical delivery. Any modification is detectable.

---

## Example Event

A trading bot successfully receives a governed policy:

```json
{
  "event_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "event_type": "INJECT_SUCCESS",
  "event_category": "inject",
  "event_time": "2025-01-15T14:30:00.123Z",
  "agent_id": "agent.trading-bot-v2",
  "org_id": "org.finco",
  "policy_name": "policy.trading-limits",
  "policy_version": 4,
  "governance_hash": "a3f2b8c1d4e5f67890abcdef1234567890abcdef1234567890abcdef12345678",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "data_classification": "confidential",
  "template_rendered": true,
  "metadata": {"regulatory_hooks": ["FINRA", "SEC"]}
}
```

More examples: [`examples/`](./examples/) — including healthcare (HIPAA), financial services (SEC/FINRA), education (FERPA), and policy violations.

---

## OpenTelemetry Integration

AIGP is the governance-proof semantic payload. OpenTelemetry is the transport and correlation layer. They compose — they don't compete.

### Architecture

```
Governance Action
    |
    +---> AIGP Event (JSON) ---> Compliance Store (Kafka -> ClickHouse)
    |                            Purpose: Audit, regulatory, cryptographic proof
    |
    +---> OTel Span Event -----> Observability Backend (Datadog/Grafana/Honeycomb)
                                 Purpose: Latency, error rates, trace visualization
```

### What's included

| Resource | Description |
|----------|-------------|
| [Semantic Conventions](./integrations/opentelemetry/semantic-conventions.md) | `aigp.*` attribute namespace, Resource vs Span vs Event mappings |
| [Collector Config](./integrations/opentelemetry/collector-config.yaml) | Reference OTel Collector with dual-pipeline (observability + compliance) |
| [Python SDK](./sdks/python/) | `aigp-otel` bridge library with dual-emit, Baggage, and tracestate support |
| [OTel Example Events](./examples/inject-success-otel.json) | AIGP events with `span_id`, `parent_span_id`, `trace_flags` |

### Quick example (Python)

```python
from aigp_otel import AIGPInstrumentor

instrumentor = AIGPInstrumentor(
    agent_id="agent.trading-bot-v2",
    org_id="org.finco",
    event_callback=send_to_kafka,  # compliance store
)

# Within an OTel span — dual-emit happens automatically
event = instrumentor.inject_success(
    policy_name="policy.trading-limits",
    policy_version=4,
    content="Max position: $10M...",
    data_classification="confidential",
)
# -> AIGP event sent to Kafka (compliance)
# -> OTel span event with aigp.* attributes (observability)
```

> Full details: [Spec Section 11.4-11.7](./spec/aigp-spec.md#114-opentelemetry-span-correlation)

---

## Reference Implementation

[Sandarb](https://ui.sandarb.ai/) is the first reference implementation of AIGP. It produces AIGP events across every integration path (A2A, MCP, REST API) and streams them through Kafka and ClickHouse for real-time governance analytics.

But AIGP doesn't require Sandarb. Any platform that produces events conforming to the schema is AIGP-compliant. The format is deliberately simple — a JSON object with well-defined fields — so adoption is a low barrier.

---

## Contributing

We don't have all the answers. AI governance is a new field, and the right format will emerge from real-world use across different industries, regulatory regimes, and agent architectures.

- **Use it and tell us what's missing.** If the schema doesn't capture something your regulators need, that's exactly the feedback we want.
- **Propose new event types.** The 16 standard types cover what we've seen so far. Healthcare, autonomous vehicles, and other domains will have governance actions we haven't imagined.
- **Challenge the design.** If events should be signed, or `governance_hash` should use a Merkle tree, or the schema should be nested — [open an issue](https://github.com/sandarb-ai/aigp/issues).
- **Build your own implementation.** AIGP is Apache 2.0. Build a Go producer, a Rust consumer, a Spark connector. The more implementations, the more useful the format.

### Resources

| Resource | Link |
|----------|------|
| Formal Specification | [`spec/aigp-spec.md`](./spec/aigp-spec.md) |
| JSON Schema | [`schema/aigp-event.schema.json`](./schema/aigp-event.schema.json) |
| OTel Semantic Conventions | [`integrations/opentelemetry/`](./integrations/opentelemetry/) |
| Python SDK | [`sdks/python/`](./sdks/python/) |
| Changelog | [`CHANGELOG.md`](./CHANGELOG.md) |
| Example Events | [`examples/`](./examples/) |
| Issues | [github.com/sandarb-ai/aigp/issues](https://github.com/sandarb-ai/aigp/issues) |
| Discussions | [github.com/sandarb-ai/aigp/discussions](https://github.com/sandarb-ai/aigp/discussions) |
| AIGP on the Web | [sandarb.ai/aigp](https://ui.sandarb.ai/aigp) |
| Sandarb Platform | [sandarb.ai](https://ui.sandarb.ai/) |

---

AI governance is too important to be owned by any single company. We started AIGP because we needed it for [Sandarb](https://ui.sandarb.ai/), and we're sharing it because we believe the industry needs a common language. This is a small step. We hope others will take the next ones with us.
