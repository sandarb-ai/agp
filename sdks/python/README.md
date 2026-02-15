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

## Modules

| Module | Purpose |
|--------|---------|
| `aigp_otel.instrumentor` | Core dual-emit bridge (`AIGPInstrumentor`) |
| `aigp_otel.attributes` | `aigp.*` semantic attribute constants |
| `aigp_otel.events` | AIGP event creation and hash computation |
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
