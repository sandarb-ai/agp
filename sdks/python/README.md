# AIGP-OpenTelemetry Python SDK

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)

**Bridge between AIGP governance events and OpenTelemetry spans.**

AIGP is the governance-proof semantic payload. OpenTelemetry is the transport and correlation layer. This SDK handles dual-emit: every governance action produces both an AIGP event (compliance store) and an OTel span event (observability backend).

---

## Installation

```bash
pip install opentelemetry-api opentelemetry-sdk

# Then add this package to your project
# (from the AIGP repo root)
pip install -e sdks/python/
```

## Quick Start

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource

from aigp_otel import AIGPInstrumentor

# 1. Initialize with AIGP Resource attributes
instrumentor = AIGPInstrumentor(
    agent_id="agent.trading-bot-v2",
    agent_name="Trading Bot",
    org_id="org.finco",
    event_callback=send_to_kafka,  # your compliance store
)

resource = Resource.create({
    **instrumentor.get_resource_attributes(),
    "service.name": "trading-bot-v2",
})
provider = TracerProvider(resource=resource)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("aigp.example")

# 2. Emit governance events within OTel spans
with tracer.start_as_current_span("invoke_agent") as span:
    event = instrumentor.inject_success(
        policy_name="policy.trading-limits",
        policy_version=4,
        content="Max position: $10M...",
        data_classification="confidential",
    )
    # -> AIGP event sent to Kafka (compliance)
    # -> OTel span event with aigp.* attributes (observability)
```

## Features

### Dual-Emit Architecture

Every call produces two outputs automatically:

```
instrumentor.inject_success(...)
    |
    +---> AIGP Event (JSON) ---> event_callback (Kafka/ClickHouse)
    |
    +---> OTel Span Event -----> OTel backend (Datadog/Grafana)
```

### Supported Event Types

| Method | AIGP Event Type | OTel Span Event |
|--------|----------------|-----------------|
| `inject_success()` | `INJECT_SUCCESS` | `aigp.inject.success` |
| `inject_denied()` | `INJECT_DENIED` | `aigp.inject.denied` |
| `prompt_used()` | `PROMPT_USED` | `aigp.prompt.used` |
| `prompt_denied()` | `PROMPT_DENIED` | `aigp.prompt.denied` |
| `policy_violation()` | `POLICY_VIOLATION` | `aigp.policy.violation` |
| `a2a_call()` | `A2A_CALL` | `aigp.a2a.call` |
| `governance_proof()` | `GOVERNANCE_PROOF` | `aigp.governance.proof` |
| `multi_policy_inject()` | `INJECT_SUCCESS` | `aigp.inject.success` (with array attributes) |
| `multi_resource_governance_proof()` | `GOVERNANCE_PROOF` | `aigp.governance.proof` (with Merkle tree) |

### Multi-Policy / Multi-Prompt Support

When an agent is governed by multiple policies simultaneously:

```python
event = instrumentor.multi_policy_inject(
    policies=[
        {"name": "policy.trading-limits", "version": 4},
        {"name": "policy.risk-controls", "version": 2},
    ],
    content="Combined governed content...",
    data_classification="confidential",
)
```

This produces OTel array-valued attributes:
```
aigp.policies.names = ["policy.trading-limits", "policy.risk-controls"]
aigp.policies.versions = [4, 2]
```

### Merkle Tree Governance Hash

When an agent is governed by multiple resources (policies, prompts, tools), compute a Merkle tree for per-resource verification:

```python
from aigp_otel.events import compute_merkle_governance_hash

resources = [
    ("policy", "policy.refund-limits", "Refund max: $500..."),
    ("prompt", "prompt.customer-support-v3", "You are a helpful..."),
    ("tool", "tool.order-lookup", '{"name": "order-lookup", "scope": "read"}'),
]

root_hash, merkle_tree = compute_merkle_governance_hash(resources)
# root_hash: "a3f2b8..." (Merkle root, used as governance_hash)
# merkle_tree: {"algorithm": "sha256", "leaf_count": 3, "leaves": [...]}
```

Or use the instrumentor for dual-emit with Merkle:

```python
event = instrumentor.multi_resource_governance_proof(
    resources=[
        ("policy", "policy.refund-limits", "Refund max: $500..."),
        ("prompt", "prompt.customer-support-v3", "You are a helpful..."),
        ("tool", "tool.order-lookup", '{"name": "order-lookup"}'),
    ],
    data_classification="confidential",
)
# governance_hash is the Merkle root
# hash_type is "merkle-sha256"
# governance_merkle_tree contains per-resource leaf hashes
# OTel span event carries aigp.governance.merkle.leaf_count
```

Single-resource calls continue to produce flat SHA-256 hashes for full backward compatibility.

### Baggage Propagation (Agent-to-Agent)

```python
from aigp_otel.baggage import AIGPBaggage

# Calling agent: inject governance context
ctx = AIGPBaggage.inject(
    policy_name="policy.trading-limits",
    data_classification="confidential",
    org_id="org.finco",
)

# Receiving agent: extract governance context
extracted = AIGPBaggage.extract()
# {'aigp.policy.name': 'policy.trading-limits', ...}
```

### W3C tracestate Vendor Key

```python
from aigp_otel.tracestate import AIGPTraceState

# Encode AIGP into tracestate
tracestate = AIGPTraceState.inject_into_tracestate(
    existing_tracestate="dd=s:1",
    data_classification="confidential",
    policy_name="policy.trading-limits",
    policy_version=4,
)
# "aigp=cls:con;pol:policy.trading-limits;ver:4,dd=s:1"

# Decode on receiving side
context = AIGPTraceState.extract_from_tracestate(tracestate)
# {'data_classification': 'confidential', 'policy_name': 'policy.trading-limits', ...}
```

### OpenLineage Facet Builder

```python
from aigp_otel.openlineage import build_openlineage_run_event
from aigp_otel.events import compute_merkle_governance_hash, create_aigp_event

# Context + lineage resources as governed inputs
resources = [
    ("policy", "policy.fair-lending", policy_content),
    ("prompt", "prompt.scoring-v3", prompt_content),
    ("context", "context.env-config", env_config_json),
    ("lineage", "lineage.upstream-orders", lineage_snapshot_json),
]
root, tree = compute_merkle_governance_hash(resources)

aigp_event = create_aigp_event(
    event_type="GOVERNANCE_PROOF",
    event_category="governance-proof",
    agent_id="agent.credit-scorer-v2",
    trace_id="abc123...",
    governance_hash=root,
    hash_type="merkle-sha256",
    governance_merkle_tree=tree,
)

# Build OpenLineage RunEvent (zero OL dependency)
ol_event = build_openlineage_run_event(
    aigp_event,
    job_namespace="finco.scoring",
    job_name="credit-scorer-v2.invoke",
)
# Send to Marquez, DataHub, or any OpenLineage backend
```

## Modules

| Module | Purpose |
|--------|---------|
| `aigp_otel.instrumentor` | Core triple-emit bridge (`AIGPInstrumentor`) |
| `aigp_otel.attributes` | `aigp.*` semantic attribute constants |
| `aigp_otel.events` | AIGP event creation, hash computation, and Merkle tree |
| `aigp_otel.openlineage` | OpenLineage facet builder (zero OL dependency) |
| `aigp_otel.baggage` | OTel Baggage propagation for A2A calls |
| `aigp_otel.tracestate` | W3C tracestate vendor key encode/decode |

## Running Tests

```bash
cd sdks/python
pip install opentelemetry-api opentelemetry-sdk pytest
PYTHONPATH=. pytest tests/ -v
```

## Running the End-to-End Example

```bash
cd sdks/python
PYTHONPATH=. python examples/end_to_end.py
```

## Related Documentation

- [AIGP Specification](../../spec/aigp-spec.md) (Sections 11.4-11.7)
- [AIGP OTel Semantic Conventions](../../integrations/opentelemetry/semantic-conventions.md)
- [OTel Collector Reference Config](../../integrations/opentelemetry/collector-config.yaml)
