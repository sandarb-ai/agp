# AIGP Semantic Conventions for OpenLineage

This document defines how AIGP AI governance metadata maps to OpenLineage facets.

---

## 1. Overview

AIGP and OpenLineage serve orthogonal purposes:

- **AIGP** captures AI governance proof: what policies, prompts, tools, contexts, and lineage governed an agent, with cryptographic hashes.
- **OpenLineage** captures data lineage: what data flowed where, consumed by what, produced by what.

When both are present, AIGP governance metadata attaches to OpenLineage events via custom facets, and `trace_id` correlates records across AIGP, OTel, and OpenLineage.

---

## 2. Facet Architecture

AIGP defines two custom facets:

| Facet | Type | Attachment Point | Purpose |
|---|---|---|---|
| `aigp_governance` | RunFacet | `run.facets.aigp_governance` | Aggregate governance proof for the run |
| `aigp_resource` | InputDatasetFacet | `inputs[].inputFacets.aigp_resource` | Per-resource governance metadata |

The run facet provides the summary (hash, enforcement result, classification). The input facets provide the detail (each governed resource as a dataset).

---

## 3. AIGPGovernanceRunFacet

| Property | Type | Required | Description | Example |
|---|---|---|---|---|
| `_producer` | String (URI) | Yes | URI identifying the producer | `"https://github.com/sandarb-ai/aigp"` |
| `_schemaURL` | String (URI) | Yes | JSON Pointer to schema version | `"https://github.com/sandarb-ai/aigp/blob/v0.5.0/..."` |
| `governanceHash` | String | Yes | SHA-256 governance hash (flat or Merkle root) | `"a3f8..."` |
| `hashType` | String | Yes | `"sha256"` or `"merkle-sha256"` | `"merkle-sha256"` |
| `agentId` | String | Yes | AGRN agent identifier | `"agent.credit-scorer-v2"` |
| `traceId` | String | Yes | Correlation key across AIGP, OTel, OpenLineage | `"4bf92f35..."` |
| `leafCount` | Int | No | Number of governed resources | `3` |
| `enforcementResult` | String | No | `"allowed"` or `"denied"` | `"allowed"` |
| `dataClassification` | String | No | Highest classification level | `"confidential"` |
| `specVersion` | String | No | AIGP specification version | `"0.5.0"` |

---

## 4. AIGPResourceInputFacet

| Property | Type | Required | Description | Example |
|---|---|---|---|---|
| `_producer` | String (URI) | Yes | URI identifying the producer | `"https://github.com/sandarb-ai/aigp"` |
| `_schemaURL` | String (URI) | Yes | JSON Pointer to schema version | `"https://github.com/sandarb-ai/aigp/blob/v0.5.0/..."` |
| `resourceType` | String | Yes | `"policy"`, `"prompt"`, `"tool"`, `"context"`, `"lineage"`, `"memory"`, or `"model"` | `"memory"` |
| `resourceName` | String | Yes | AGRN-format resource name | `"lineage.upstream-orders"` |
| `resourceVersion` | Int | No | Version at time of governance action | `4` |
| `leafHash` | String | No | Merkle leaf hash (64-char hex) | `"b2e4..."` |

---

## 5. Context, Lineage, Memory, and Model Resources as Governed Inputs

Four resource types enable pre-execution and runtime inputs to participate in the Merkle tree:

- **`"context"`** — agent-defined, general-purpose. AIGP does not prescribe what goes inside — each AI agent or framework determines the semantics (env config, runtime params, session state, etc.). AIGP hashes it; the agent owns the meaning.
- **`"lineage"`** — AIGP-defined, specific meaning. Data lineage snapshots: upstream dataset provenance, DAG state, OpenLineage graph context. Used for bidirectional sync between AIGP and OpenLineage.
- **`"memory"`** — agent-defined, like context. Agent memory state: conversation history, RAG retrieval context, vector store contents, session state. AIGP hashes it; the agent defines the semantics.
- **`"model"`** — agent-defined. Inference engine identity: model card, weights hash, configuration, LoRA adapters. Provides cryptographic proof of which model was used at decision time.

Before an agent runs, you can:

1. Query the OpenLineage lineage graph for upstream data provenance.
2. Serialize the lineage snapshot as JSON.
3. Hash it as a `"lineage"` Merkle leaf: `SHA-256("lineage:lineage.upstream-orders:" + json)`.
4. Include it in the governance Merkle tree alongside policies, prompts, tools, and contexts.

The governance hash now covers data lineage as a first-class governed resource. If the upstream data changes after the snapshot, the hash won't match.

```python
resources = [
    ("policy", "policy.fair-lending", policy_content),
    ("prompt", "prompt.scoring-v3", prompt_content),
    ("context", "context.env-config", env_config_json),
    ("lineage", "lineage.upstream-orders", lineage_snapshot_json),
    ("memory", "memory.conversation-history", memory_json),
    ("model", "model.gpt4-trading-v2", model_config_json),
]
root, tree = compute_merkle_governance_hash(resources)
```

---

## 6. Triple-Emit Architecture

```
AI Agent Invocation
    |
    +--> AIGP Event (JSON) --> AI Governance Store
    |    Full Merkle tree, all leaf hashes, complete proof
    |
    +--> OTel Span Event --> Observability Backend
    |    governance_hash, leaf_count, trace context
    |
    +--> OpenLineage RunEvent with AIGP Facets --> Lineage Backend
         Governance summary + resources as InputDatasets
```

Triple-emit is OPTIONAL. Implementations MAY use any subset.

---

## 7. Correlation: `trace_id` as the Key

The same `trace_id` appears in all three records:

| System | Location |
|---|---|
| AIGP event | `trace_id` field |
| OTel span | `trace_id` in span context |
| OpenLineage RunEvent | `run.facets.aigp_governance.traceId` |

One query joins all three views:

```sql
-- AIGP: full proof
SELECT * FROM aigp_events WHERE trace_id = '4bf92f35...';

-- OTel: operational view
-- (query your observability backend by trace_id)

-- OpenLineage: lineage view
-- (query lineage backend by run facet traceId)
```

---

## 8. Emission Granularity

OpenLineage was designed for discrete Job Runs in a DAG (an Airflow task, a Spark job, a dbt model) with clear start/end boundaries. AI agents are conversational and iterative.

**Rule:** Emit at most one OpenLineage RunEvent per governance session or task, using `trace_id` as the `runId`. Individual agent steps are OTel spans, not OpenLineage runs.

---

## References

- [AIGP Specification](../../spec/aigp-spec.md) -- Section 11.8: OpenLineage Integration
- [AIGPGovernanceRunFacet Schema](facets/AIGPGovernanceRunFacet.json)
- [AIGPResourceInputFacet Schema](facets/AIGPResourceInputFacet.json)
- [OpenLineage Specification](https://openlineage.io/docs/spec/object-model/)
- [OpenLineage Custom Facets](https://openlineage.io/docs/spec/facets/custom-facets/)
