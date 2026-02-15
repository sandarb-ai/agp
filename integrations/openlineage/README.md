# AIGP OpenLineage Integration

AIGP defines custom OpenLineage facets that attach AI governance metadata to OpenLineage RunEvents, connecting cryptographic governance proof to data lineage.

## Three Layers, One `trace_id`

| Layer | Standard | What It Shows |
|---|---|---|
| **AI Governance** | AIGP | Cryptographic proof, enforcement, audit trail, AI governance evidence |
| **Observability** | OTel | Agent latency, errors, trace topology, AI governance attributes |
| **Lineage** | OpenLineage | What data flowed where, governed by what, produced what |

## Custom Facets

### AIGPGovernanceRunFacet

Attaches to `run.facets.aigp_governance`. Captures the aggregate governance proof for the entire run.

Schema: [`facets/AIGPGovernanceRunFacet.json`](facets/AIGPGovernanceRunFacet.json)

### AIGPResourceInputFacet

Attaches to `inputs[].inputFacets.aigp_resource`. Models each governed resource (policy, prompt, tool, context, lineage) as an OpenLineage InputDataset.

Schema: [`facets/AIGPResourceInputFacet.json`](facets/AIGPResourceInputFacet.json)

## Python SDK

The `aigp_otel.openlineage` module builds OpenLineage-compatible dicts with zero OpenLineage library dependency:

```python
from aigp_otel.openlineage import (
    build_governance_run_facet,
    build_resource_input_facets,
    build_openlineage_run_event,
)

# From an existing AIGP event:
run_facet = build_governance_run_facet(aigp_event)
input_facets = build_resource_input_facets(aigp_event)

# Or build a complete RunEvent:
ol_event = build_openlineage_run_event(
    aigp_event,
    job_namespace="finco.trading",
    job_name="trading-bot-v2.invoke",
)
```

## Architectural Constraints

1. **Emission Granularity:** Emit one OpenLineage RunEvent per governance session/task (using `trace_id` as `runId`), not per agent step.
2. **Dataset Abstraction:** Governed resources appear as generic datasets in standard lineage UIs. Use `aigp_resource.resourceType` for native rendering.
3. **Active vs. Passive:** OpenLineage is passive (eventually consistent). Enforcement uses the AIGP + OTel path. Pre-execution data lineage is snapshotted and hashed as a `"lineage"` resource (AIGP-defined, specific meaning). General pre-execution context uses `"context"` (agent-defined — AIGP hashes it but doesn't prescribe what goes inside).

## Related Documentation

- [Semantic Conventions](semantic-conventions.md) -- Facet mapping guide
- [AIGP Specification Section 11.8](../../spec/aigp-spec.md) -- Normative integration spec
- [Python SDK](../../sdks/python/README.md) -- SDK documentation
- [OTel Integration](../opentelemetry/README.md) -- OpenTelemetry integration
