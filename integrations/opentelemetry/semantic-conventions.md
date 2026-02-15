# AIGP Semantic Conventions for OpenTelemetry

**Version:** 0.3.0 (Draft)

**Status:** Experimental

**Companion to:** [AIGP Specification v0.3.0](../../spec/aigp-spec.md)

---

## Overview

This document defines the semantic conventions for representing AI Governance Proof (AIGP) data within OpenTelemetry (OTel) signals. AIGP provides the governance-proof semantic payload; OTel provides the transport, context propagation, and correlation layer.

**Design principle:** AIGP events and OTel spans are complementary. An AIGP event is the cryptographic receipt. An OTel span is the operational record. The same governance action produces both: the AIGP event goes to the compliance store, the OTel span (enriched with `aigp.*` attributes) goes to the observability backend.

---

## 1. Attribute Namespace

All AIGP attributes use the `aigp.*` namespace prefix, following OTel's hierarchical naming conventions.

Characters: lowercase Latin alphabet, numeric characters, underscore (`_`), and dot (`.`) as namespace delimiter.

---

## 2. Resource Attributes

Resource attributes represent identity that is constant for the lifetime of the agent process. They SHOULD be set once on the OTel `Resource` and automatically propagated to all spans, metrics, and logs from that process.

| Attribute | Type | Required | Description | Example |
|---|---|---|---|---|
| `aigp.agent.id` | String | Yes | AGRN-format agent identifier | `agent.trading-bot-v2` |
| `aigp.agent.name` | String | No | Human-readable agent display name | `Trading Bot` |
| `aigp.org.id` | String | Recommended | AGRN-format organization identifier | `org.finco` |
| `aigp.org.name` | String | No | Human-readable organization name | `FinCo` |

### Example: Resource initialization

```python
from opentelemetry.sdk.resources import Resource

resource = Resource.create({
    "aigp.agent.id": "agent.trading-bot-v2",
    "aigp.agent.name": "Trading Bot",
    "aigp.org.id": "org.finco",
    "aigp.org.name": "FinCo",
    "service.name": "trading-bot-v2",
})
```

---

## 3. Span Attributes

Span attributes capture per-operation governance metadata. They are set on the span that performs or triggers the governance action.

### 3.1 Core Governance Attributes

| Attribute | Type | Required | Description | Example |
|---|---|---|---|---|
| `aigp.event.id` | String | Yes | UUID of the AIGP event | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| `aigp.event.type` | String | Yes | AIGP event type | `INJECT_SUCCESS` |
| `aigp.event.category` | String | Yes | AIGP event category | `inject` |
| `aigp.governance.hash` | String | Conditional | SHA-256 hash of governed content (flat or Merkle root) | `a3f2b8c1d4e5...` |
| `aigp.governance.hash_type` | String | No | Hash algorithm (`sha256` or `merkle-sha256`) | `sha256` |
| `aigp.governance.merkle.leaf_count` | Int | Conditional | Number of leaves in Merkle tree (when `hash_type` is `merkle-sha256`) | `5` |
| `aigp.data.classification` | String | Recommended | Data sensitivity level | `confidential` |
| `aigp.enforcement.result` | String | Recommended | Governance decision | `allowed` or `denied` |

### 3.2 Policy Attributes

| Attribute | Type | Required | Description | Example |
|---|---|---|---|---|
| `aigp.policy.name` | String | Conditional | AGRN-format policy name | `policy.trading-limits` |
| `aigp.policy.version` | Int | Conditional | Policy version snapshot | `4` |
| `aigp.policy.id` | String | No | Internal policy identifier | `pol-001` |

### 3.3 Prompt Attributes

| Attribute | Type | Required | Description | Example |
|---|---|---|---|---|
| `aigp.prompt.name` | String | Conditional | AGRN-format prompt name | `prompt.customer-support-v3` |
| `aigp.prompt.version` | Int | Conditional | Prompt version snapshot | `2` |
| `aigp.prompt.id` | String | No | Internal prompt identifier | `pmt-042` |

### 3.4 Denial and Violation Attributes

| Attribute | Type | Required | Description | Example |
|---|---|---|---|---|
| `aigp.severity` | String | Conditional | Impact level | `critical` |
| `aigp.violation.type` | String | Conditional | Machine-readable violation category | `DATA_CLASSIFICATION_BREACH` |
| `aigp.denial.reason` | String | No | Human-readable denial explanation | `Agent clearance below data classification` |

### 3.5 Multi-Policy and Multi-Prompt Attributes

When a single governance operation involves multiple policies, prompts, or tools, implementations SHOULD use array-valued attributes:

| Attribute | Type | Description | Example |
|---|---|---|---|
| `aigp.policies.names` | String[] | All active policies in this operation | `["policy.trading-limits", "policy.risk-controls"]` |
| `aigp.policies.versions` | Int[] | Corresponding versions (positional) | `[4, 2]` |
| `aigp.prompts.names` | String[] | All active prompts in this operation | `["prompt.customer-support-v3", "prompt.escalation-v1"]` |
| `aigp.prompts.versions` | Int[] | Corresponding versions (positional) | `[3, 1]` |
| `aigp.tools.names` | String[] | Governed tools invoked | `["tool.web-search", "tool.database-query"]` |

When only a single policy or prompt is involved, implementations MAY use the singular form (`aigp.policy.name`) instead of the array form.

### 3.6 Merkle Tree Governance Attributes

When `hash_type` is `"merkle-sha256"`, the governance hash is a Merkle root computed over individual resource leaf hashes. The following attribute provides observability into the Merkle structure:

| Attribute | Type | Required | Description | Example |
|---|---|---|---|---|
| `aigp.governance.merkle.leaf_count` | Int | Conditional | Number of governed resources in the Merkle tree. Present when `aigp.governance.hash_type` is `"merkle-sha256"`. | `5` |

The full Merkle tree structure (leaf hashes, resource names, resource types) is carried in the AIGP event's `governance_merkle_tree` field rather than as OTel span attributes, to avoid excessive attribute cardinality in observability backends. The `leaf_count` attribute provides sufficient signal for dashboards and alerts (e.g., "alert when leaf_count > 10" or "histogram of resources per governance action").

### 3.7 Context and Lineage Resource Attributes

When governance operations include context or lineage resources, implementations SHOULD use the array-valued attributes:

| Attribute | Type | Required | Description | Example |
|---|---|---|---|---|
| `aigp.contexts.names` | String[] | Conditional | Governed context resource names. Present when context resources participate in the governance action. | `["context.env-config", "context.runtime-params"]` |
| `aigp.lineages.names` | String[] | Conditional | Governed lineage resource names. Present when lineage snapshots participate in the governance action. | `["lineage.upstream-orders", "lineage.credit-scores"]` |

Context resources capture general pre-execution state (env config, runtime params). Lineage resources capture data lineage snapshots (upstream dataset provenance, DAG state). Both participate in the Merkle tree alongside policies, prompts, and tools. The `aigp.governance.merkle.leaf_count` attribute reflects the total count including context and lineage leaves.

---

## 4. Span Events

AIGP governance actions SHOULD be emitted as OTel span events. Each span event represents one AIGP event within the lifecycle of an OTel span.

### 4.1 Event Names

| OTel Span Event Name | AIGP Event Types | Description |
|---|---|---|
| `aigp.inject.success` | `INJECT_SUCCESS` | Policy successfully delivered to agent |
| `aigp.inject.denied` | `INJECT_DENIED` | Policy injection denied |
| `aigp.prompt.used` | `PROMPT_USED` | Prompt successfully retrieved and used |
| `aigp.prompt.denied` | `PROMPT_DENIED` | Prompt retrieval denied |
| `aigp.policy.violation` | `POLICY_VIOLATION` | Governance policy violated |
| `aigp.governance.proof` | `GOVERNANCE_PROOF` | Cryptographic proof-of-delivery recorded |
| `aigp.a2a.call` | `A2A_CALL` | Agent-to-agent protocol call |

### 4.2 Event-to-Span Mapping

Different AIGP event types map to different OTel span operation types:

| AIGP Event Type | OTel Span `gen_ai.operation.name` | Rationale |
|---|---|---|
| `INJECT_SUCCESS` / `INJECT_DENIED` | `invoke_agent` | Policy injection occurs during agent invocation |
| `PROMPT_USED` / `PROMPT_DENIED` | `chat` | Prompt is consumed during inference |
| `A2A_CALL` | `execute_tool` | Agent-to-agent is a tool-level operation |
| `POLICY_VIOLATION` | *(any span)* | Violations can occur at any point; set `otel.status = ERROR` |
| `GOVERNANCE_PROOF` | *(root span)* | Proof attestation spans the governance workflow |

### 4.3 Example: Span Event

```python
from opentelemetry import trace

span = trace.get_current_span()
span.add_event("aigp.inject.success", attributes={
    "aigp.event.id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "aigp.event.type": "INJECT_SUCCESS",
    "aigp.policy.name": "policy.trading-limits",
    "aigp.policy.version": 4,
    "aigp.governance.hash": "a3f2b8c1d4e5f67890abcdef1234567890abcdef1234567890abcdef12345678",
    "aigp.data.classification": "confidential",
    "aigp.enforcement.result": "allowed",
})
```

---

## 5. Baggage Propagation

When an agent invokes another agent, governance context travels via OTel Baggage.

### 5.1 Propagated Items

| Baggage Key | Source | Purpose |
|---|---|---|
| `aigp.policy.name` | `policy_name` | Active governed policy |
| `aigp.data.classification` | `data_classification` | Data sensitivity level |
| `aigp.org.id` | `org_id` | Organizational affiliation |

### 5.2 Security Constraints

- `governance_hash`, `denial_reason`, and raw policy content MUST NOT be placed in Baggage.
- Baggage values are transmitted in HTTP headers and MAY be visible to intermediaries.

---

## 6. W3C `tracestate` Vendor Key

The `aigp` vendor key in `tracestate` provides lightweight governance context that survives through proxies and load balancers.

### Format

```
tracestate: aigp=cls:{classification};pol:{policy_name};ver:{policy_version}
```

### Abbreviations

| `data_classification` | `cls` abbreviation |
|---|---|
| `public` | `pub` |
| `internal` | `int` |
| `confidential` | `con` |
| `restricted` | `res` |

### Example

```
tracestate: aigp=cls:con;pol:policy.trading-limits;ver:4
```

---

## 7. Dual-Emit Architecture

Every governance action produces two outputs:

```
Governance Action
    |
    +---> AIGP Event (JSON) ---> Compliance Store (Kafka -> ClickHouse)
    |                            Purpose: Audit, regulatory, cryptographic proof
    |
    +---> OTel Span Event -----> Observability Backend (Datadog/Grafana/Honeycomb)
                                 Purpose: Latency, error rates, trace visualization
```

The same data, two destinations, two purposes. The AIGP event is the authoritative governance record. The OTel span event is the operational view.

Implementations SHOULD produce both outputs for every governance action. If only one output is possible, the AIGP event MUST be preferred (governance is the primary purpose).

---

## 8. OTel Collector Integration

The OTel Collector can bridge OTel telemetry and AIGP events without modifying application code.

### 8.1 Architecture

```
Receivers            Processors                  Exporters
-----------    -------------------------    ----------------------
OTLP (gRPC) -> aigp-governance-processor -> AIGP store (Kafka)
                                         -> OTel backend (OTLP)
```

### 8.2 Processor Behavior

The `aigp-governance-processor` (custom Collector processor):

1. **Inspect**: Detect spans with `gen_ai.*` or `aigp.*` attributes.
2. **Enrich**: Look up applicable policies from governance platform.
3. **Generate**: Produce AIGP events from governance-relevant spans.
4. **Attach**: Add `aigp.*` attributes back to spans for observability.
5. **Route**: Send AIGP JSON to compliance storage via exporter.

See [`collector-config.yaml`](./collector-config.yaml) for a reference configuration.

---

## 9. Mapping to OTel GenAI Semantic Conventions

AIGP attributes complement (not replace) the existing `gen_ai.*` namespace:

| Concern | Namespace | Example |
|---|---|---|
| What model was used? | `gen_ai.*` | `gen_ai.request.model: gpt-4` |
| Was this governed? | `aigp.*` | `aigp.enforcement.result: allowed` |
| How many tokens? | `gen_ai.*` | `gen_ai.usage.input_tokens: 1200` |
| What policy applied? | `aigp.*` | `aigp.policy.name: policy.trading-limits` |
| What was the latency? | OTel span duration | `duration: 340ms` |
| Is there cryptographic proof? | `aigp.*` | `aigp.governance.hash: a3f2b8c1...` |

---

## References

- [AIGP Specification v0.3.0](../../spec/aigp-spec.md)
- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
- [OpenTelemetry GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
- [OpenTelemetry Baggage](https://opentelemetry.io/docs/concepts/signals/baggage/)
