# AI Governance Proof (AGP)

**An open specification for capturing cryptographic proof of every AI agent governance action.**

AGP is not a product feature — it's a proposal for a common language that any platform, framework, or organization can adopt. We don't claim it's the final answer. We offer it as a starting point, and we welcome anyone who wants to help shape it.

**Specification Version:** 0.2.0 (Draft)
**Formal Specification:** [`spec/agp-spec.md`](./spec/agp-spec.md)
**License:** Apache 2.0

---

## Why AGP?

AI Agents are being deployed across every industry. They access company data, make decisions, and interact with customers. Regulators, auditors, and security teams all need to answer the same fundamental question:

> "Prove to me that your AI agent accessed the right data, used the approved prompt, and didn't violate any policy."

Today, every team answers this differently. Some grep through logs. Some build custom audit tables. Some don't track it at all. There is no shared format for what an AI governance proof should look like.

AGP is our attempt — however small — to start that conversation. It's a structured, cryptographic event format that captures what happened, who did it, what data was involved, and whether it was allowed.

---

## Design Principles

1. **Open and protocol-agnostic.** AGP events can be produced by any system — whether your agents use A2A, MCP, REST, gRPC, or something else entirely. The format doesn't assume a specific transport.

2. **Tamper-evident by default.** Every event includes a SHA-256 `governance_hash` computed at the source. If content changes between creation and storage, the hash won't match.

3. **Traceable end-to-end.** Every event carries a `trace_id` for distributed correlation. A single query can reconstruct the full chain: which agent, which prompt, which context, and what happened.

4. **Flat and queryable.** AGP uses a single wide event table — no joins needed for governance queries. Designed for OLAP engines like ClickHouse, but works with any store that can hold JSON or columnar data.

5. **Extensible, not rigid.** Required fields capture the essentials. The `metadata` object and `ext_`-prefixed extension fields allow any implementation to attach domain-specific data without breaking the schema.

---

## AGP Event Schema

An AGP event is a flat record with the following fields. Fields marked **Required** must be present in every event. All other fields are optional but encouraged.

### Event Identity

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_id` | UUID | **Yes** | Unique identifier for this event |
| `event_type` | String | **Yes** | What happened (e.g. `INJECT_SUCCESS`, `PROMPT_USED`, `AGENT_REGISTERED`) |
| `event_category` | String | **Yes** | Grouping (e.g. `inject`, `audit`, `agent-lifecycle`) |
| `event_time` | DateTime (ms) | **Yes** | When the governance action occurred (UTC, millisecond precision) |

### Agent & Organization

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_id` | String | **Yes** | The agent that triggered this governance action |
| `agent_name` | String | No | Human-readable agent name |
| `org_id` | String | No | Organization the agent belongs to (used for data locality and partitioning) |
| `org_name` | String | No | Human-readable organization name |

### Governance Proof

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `governance_hash` | String | **Yes** | SHA-256 hash of the governed content at the time of the action. This is the cryptographic proof. |
| `hash_type` | String | No | Hash algorithm used (default: `sha256`). Allows future migration to stronger algorithms. |
| `trace_id` | String | **Yes** | Distributed trace ID for end-to-end correlation across systems |
| `data_classification` | String | No | Classification of the data involved (`public`, `internal`, `confidential`, `restricted`) |

### Context & Prompt

| Field | Type | Description |
|-------|------|-------------|
| `context_id` | String | ID of the context that was accessed or injected |
| `context_name` | String | Human-readable context name |
| `context_version` | Integer | Version of the context at the time of this governance action |
| `prompt_id` | String | ID of the prompt that was used |
| `prompt_name` | String | Human-readable prompt name |
| `prompt_version` | Integer | Version of the prompt at the time of this governance action |

### Denial & Policy Violation

| Field | Type | Description |
|-------|------|-------------|
| `denial_reason` | String | Why access was denied (human-readable) |
| `violation_type` | String | Category of policy violation |
| `severity` | String | Impact level (`critical`, `high`, `medium`, `low`) |

### Request & Metadata

| Field | Type | Description |
|-------|------|-------------|
| `source_ip` | String | IP address of the requesting agent or service |
| `request_method` | String | HTTP method or protocol action that triggered the event |
| `request_path` | String | API path or skill name |
| `template_rendered` | Boolean | Whether the context was rendered with variables before delivery |
| `ingested_at` | DateTime (ms) | When the event was received by the analytics store (allows freshness measurement) |
| `metadata` | JSON Object | Extensible object for domain-specific data. Implementations may add regulatory hooks, custom tags, or framework-specific context here. |

---

## Standard Event Types

The AGP specification defines 16 event types across 7 categories. Implementations may extend these with additional types using the same naming convention (`RESOURCE_ACTION`).

| Category | Event Types | When emitted |
|----------|------------|--------------|
| Context Injection | `INJECT_SUCCESS`, `INJECT_DENIED` | Agent requests governed context |
| Prompt Usage | `PROMPT_USED`, `PROMPT_DENIED` | Agent pulls an approved prompt |
| Agent Lifecycle | `AGENT_REGISTERED`, `AGENT_APPROVED`, `AGENT_DEACTIVATED` | Agent joins, is approved, or leaves the registry |
| Context Lifecycle | `CONTEXT_CREATED`, `CONTEXT_VERSION_APPROVED`, `CONTEXT_ARCHIVED` | Context is created, versioned, or archived |
| Prompt Lifecycle | `PROMPT_VERSION_CREATED`, `PROMPT_VERSION_APPROVED` | Prompt is created or a new version is approved |
| Governance Proof | `GOVERNANCE_PROOF` | Cryptographic proof-of-delivery is recorded |
| Policy | `POLICY_VIOLATION` | A governance policy is violated |
| A2A | `A2A_CALL` | Agent-to-agent protocol call is made |

---

## Instrumentation Conventions

A common event format only works if the *values inside the events* follow shared conventions. Without naming rules, one team writes `trading-bot-v2` while another writes `TradingBot_V2` — and cross-organization queries break.

These conventions are inspired by [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/) and adapted for AI governance.

### Resource Naming (AGRN)

Every governed resource — agents, contexts, and prompts — should follow a typed, kebab-case naming convention we call **Agent Governance Resource Names (AGRN)**. The format ensures names are globally unique, human-readable, and queryable.

| Resource | AGRN Format | Example |
|----------|-----------|---------|
| Agent | `agent.<kebab-name>` | `agent.trading-bot-v2` |
| Context | `context.<kebab-name>` | `context.eu-refund-policy` |
| Prompt | `prompt.<kebab-name>` | `prompt.customer-support-v3` |
| Organization | `org.<kebab-name>` | `org.finco` |

**Rules:** Lowercase only. Letters, numbers, and hyphens. No underscores, no double hyphens, no trailing hyphens. The type prefix (`agent.`, `context.`, etc.) is part of the name and makes the resource self-describing in any AGP event or log line.

### Event Type Naming

Event types follow a `RESOURCE_ACTION` convention in **UPPER_SNAKE_CASE**. This makes events greppable, sortable, and self-describing.

| Convention | Pattern | Examples |
|-----------|---------|---------|
| Success actions | `RESOURCE_SUCCESS` or `RESOURCE_USED` | `INJECT_SUCCESS`, `PROMPT_USED` |
| Denial actions | `RESOURCE_DENIED` | `INJECT_DENIED`, `PROMPT_DENIED` |
| Lifecycle events | `RESOURCE_LIFECYCLE_ACTION` | `AGENT_REGISTERED`, `CONTEXT_ARCHIVED` |
| Versioned events | `RESOURCE_VERSION_ACTION` | `PROMPT_VERSION_CREATED`, `CONTEXT_VERSION_APPROVED` |

Custom event types should follow the same convention. For example, a healthcare implementation might add `PATIENT_DATA_ACCESSED` or `CONSENT_VERIFIED`.

### Data Classification

The `data_classification` field uses a four-tier model aligned with common enterprise data governance frameworks:

| Level | Value | Meaning | Example |
|-------|-------|---------|---------|
| 1 | `public` | Safe for external sharing | Product FAQ, public docs |
| 2 | `internal` | For company use only | Engineering runbooks, internal policies |
| 3 | `confidential` | Restricted, need-to-know | Trading limits, customer PII |
| 4 | `restricted` | Highest sensitivity, regulatory implications | MNPI, pre-release financials |

### Severity Levels

For denial and policy violation events, the `severity` field follows a four-tier model consistent with common incident management frameworks:

| Value | When to use |
|-------|-------------|
| `critical` | Regulatory breach, MNPI exposure, unauthorized access to restricted data |
| `high` | Policy violation with business impact, confidential data accessed by wrong agent |
| `medium` | Access denied by policy (expected behavior), classification mismatch |
| `low` | Informational denial, rate limiting, non-material policy flag |

### Trace ID Convention

The `trace_id` should be a stable identifier that correlates all AGP events from a single user request or agent execution. Recommended formats:

- **UUID v4** — `550e8400-e29b-41d4-a716-446655440000`
- **OpenTelemetry trace ID** — 32-char hex, e.g. `4bf92f3577b34da6a3ce929d0e0e4736`
- **Prefixed** — `trace-<uuid>` or `req-<uuid>` for human readability

The same `trace_id` should be used across the full chain: the agent's prompt pull, context injection, LLM inference, and audit log — so a single query can reconstruct the entire governance path.

### Governance Hash

The `governance_hash` is computed over the *governed content at the time of delivery*. For context injection, this is the context body (after template rendering if applicable). For prompt usage, this is the prompt content. The hash proves the exact content that was delivered.

```python
# Computing a governance hash
import hashlib

content = "You are a trading assistant. Max position: $10M..."
governance_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
# → "a3f2b8c1d4e5f67890abcdef1234567890abcdef1234567890abcdef12345678"
```

If the same context is delivered to two agents, they will produce the same `governance_hash` — proving identical content. If the content is modified (even by one character), the hash changes, making tampering detectable.

---

## Example AGP Event

A minimal AGP event when an agent successfully injects governed context:

```json
{
  "event_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "event_type": "INJECT_SUCCESS",
  "event_category": "inject",
  "event_time": "2025-01-15T14:30:00.123Z",

  "agent_id": "agent.trading-bot-v2",
  "agent_name": "Trading Bot",
  "org_id": "org.finco",

  "context_name": "context.trading-limits",
  "context_version": 4,
  "prompt_version": 0,
  "data_classification": "confidential",

  "governance_hash": "a3f2b8c1d4e5f678...sha256...",
  "hash_type": "sha256",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",

  "severity": "",
  "template_rendered": true,
  "metadata": {"regulatory_hooks": ["FINRA", "SEC"]}
}
```

More examples can be found in the [`examples/`](./examples/) directory.

---

## Reference Implementation

[Sandarb](https://sandarb.ai) is the first reference implementation of AGP. It produces AGP events across every integration path (A2A, MCP, REST API, SDK) and streams them through a scalable data platform (Kafka + ClickHouse) for real-time analytics.

But AGP doesn't require Sandarb. Any platform that produces events conforming to the schema above is AGP-compliant. The format is deliberately simple — a JSON object with well-defined fields — so that adoption is a low barrier.

```python
# Any system can produce AGP events — just emit JSON
import json, hashlib, uuid, datetime

def create_agp_event(agent_id, event_type, category, content, trace_id):
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "event_category": category,
        "event_time": datetime.datetime.utcnow().isoformat() + "Z",
        "agent_id": agent_id,
        "governance_hash": hashlib.sha256(content.encode()).hexdigest(),
        "hash_type": "sha256",
        "trace_id": trace_id,
        "metadata": {}
    }
```

---

## How to Collaborate

We don't have all the answers. AI governance is a new field, and the right format will emerge from real-world use across different industries, regulatory regimes, and agent architectures. Here's how we hope this can evolve:

- **Use it and tell us what's missing.** If you implement AGP and find the schema doesn't capture something your regulators need, that's exactly the feedback we want.

- **Propose new event types.** The 16 standard types cover what we've seen so far. Healthcare, autonomous vehicles, and other domains will have governance actions we haven't imagined.

- **Challenge the design.** If you think the schema should be nested instead of flat, or that `governance_hash` should use a Merkle tree, or that events should be signed — open an issue. We'd rather get it right than get it first.

- **Build your own implementation.** AGP is Apache 2.0 licensed. Build a Go producer, a Rust consumer, a Spark connector. The more implementations exist, the more useful the format becomes.

---

AI governance is too important to be owned by any single company. We started AGP because we needed it for Sandarb, and we're sharing it because we believe the industry needs a common language. This is a small step. We hope others will take the next ones with us.

- [Open an Issue](https://github.com/sandarb-ai/agp/issues)
- [Start a Discussion](https://github.com/sandarb-ai/agp/discussions)
- [Sandarb Platform](https://sandarb.ai)
- [AGP Specification (Web)](https://sandarb.ai/agp)
