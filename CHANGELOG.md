# Changelog

All notable changes to the AIGP specification will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.0] - 2026-02-15

### Added
- **Memory resource type** — 7th standard governed resource type for agent dynamic state (conversation history, RAG retrieval, session state, vector store queries/writes). AGRN prefix `memory.`. Agent-defined content structure.
- **Model resource type** — 8th standard governed resource type for inference engine identity (model card, weights hash, LoRA config, quantization settings). AGRN prefix `model.`. Agent-defined content structure.
- `query_hash` field — SHA-256 hash of a retrieval query, used in `MEMORY_READ` events to prove what the agent asked for
- `previous_hash` field — SHA-256 hash of resource state before a write operation, used in `MEMORY_WRITTEN` and `MODEL_SWITCHED` events for diff tracking
- **14 new event types** (total 30 across 14 categories):
  - `MEMORY_READ`, `MEMORY_WRITTEN` — memory governance events
  - `TOOL_INVOKED`, `TOOL_DENIED` — tool governance events
  - `CONTEXT_CAPTURED` — context snapshot event
  - `LINEAGE_SNAPSHOT` — lineage snapshot event
  - `INFERENCE_STARTED`, `INFERENCE_COMPLETED`, `INFERENCE_BLOCKED` — inference lifecycle events
  - `HUMAN_OVERRIDE`, `HUMAN_APPROVAL` — human-in-the-loop events
  - `CLASSIFICATION_CHANGED` — data classification change event
  - `MODEL_LOADED`, `MODEL_SWITCHED` — model governance events
- OTel semantic attributes: `aigp.memories.names`, `aigp.models.names` — array-valued attributes for memory and model resources
- 14 new OTel span event names (e.g., `aigp.memory.read`, `aigp.model.loaded`)
- Python SDK: 14 new `AIGPInstrumentor` convenience methods (one per new event type)
- Example events: `memory-read.json`, `memory-written.json`, `tool-invoked.json`, `inference-completed.json`, `model-loaded.json`
- End-to-end example Scenarios 10-13: Memory Governance, Tool Governance, Inference Lifecycle, Model Governance
- Comprehensive test suite for all new events (test_new_events.py)

### Changed
- Standard resource types expanded from 5 to 7 (added memory, model)
- Resource type ordering: policy, prompt, tool, lineage, context, memory, model
- Event type count: 16 → 30 across 14 categories (was 8)
- Merkle tree example expanded from 7 to 9 leaves (added memory and model)
- Domain separation tests cover all 7 standard types
- BLOCKED event type handling added to enforcement result derivation (joins DENIED and VIOLATION)
- All OpenLineage facet schema URLs updated to v0.7.0
- Spec version bumped to 0.7.0
- Backward compatible: existing events and hashes unchanged

## [0.6.0] - 2026-02-15

### Added
- **Resources + Annotations extensibility model** — AIGP's two-primitive approach to forward-compatible extensibility
- `annotations` field — informational context for governance events (NOT included in governance hashes, NOT governed). Replaces `metadata`.
- `spec_version` optional field — declares which AIGP specification version the producer implemented
- Open `resource_type` pattern — implementations MAY define custom resource types matching `^[a-z][a-z0-9]*(-[a-z0-9]+)*$` without a specification change
- Must-ignore rule — consumers MUST ignore unknown resource types and annotation keys
- Additive-only minor version guarantee — minor versions MUST NOT remove, rename, or change semantics of existing fields
- Custom resource type tests (e.g., `"compliance"`, `"approval"`, `"audit-log"`)

### Changed
- **Breaking:** `metadata` field renamed to `annotations` (schema, spec, SDK, all examples)
- **Breaking:** `ext_` extension field prefix mechanism removed (patternProperties removed from JSON schema, Section 5.8 removed from spec)
- `resource_type` validation changed from closed enum to open pattern (Python SDK uses regex instead of tuple)
- Principle 5 rewritten as "Forward-Compatible Extensibility" with Resources + Annotations
- Security Section 14.2: `ext_signature` / `ext_key_id` → `annotations.signature` / `annotations.key_id`
- Conformance levels updated for `annotations` and `spec_version`
- All OpenLineage facet schema URLs updated to v0.6.0
- Spec version bumped to 0.6.0
- Standard resource type documentation order: policy, prompt, tool, lineage, context (context always last)

### Removed
- `metadata` field (replaced by `annotations`)
- `ext_` extension field prefix mechanism (Section 5.8 and patternProperties)

## [0.5.0] - 2026-02-15

### Added
- **OpenLineage integration** for connecting AI governance proof to data lineage (Spec Section 11.8)
- `"context"` resource type for Merkle tree leaves — general pre-execution context (environment config, runtime params) as governed resources
- `"lineage"` resource type for Merkle tree leaves — data lineage snapshots (upstream dataset provenance, DAG state) as governed resources
- AGRN `context.` prefix for context resources (e.g., `context.env-config`)
- AGRN `lineage.` prefix for lineage resources (e.g., `lineage.upstream-orders`)
- Custom facet schemas: `AIGPGovernanceRunFacet` (run facet), `AIGPResourceInputFacet` (input dataset facet)
- Python SDK: `openlineage` module with `build_governance_run_facet()`, `build_resource_input_facets()`, `build_openlineage_run_event()`
- Python SDK: `openlineage_callback` parameter on `AIGPInstrumentor` for optional triple-emit
- OTel semantic attribute: `aigp.contexts.names` — array-valued attribute for context resources
- OTel semantic attribute: `aigp.lineages.names` — array-valued attribute for lineage resources
- OTel semantic conventions Section 3.7: Context and Lineage Resource Attributes
- Spec Section 11.8: OpenLineage Data Lineage Integration (context and lineage resources, custom facets, emission granularity, active vs. passive lineage, triple-emit architecture)
- OpenLineage semantic conventions document (`integrations/openlineage/semantic-conventions.md`)
- OpenLineage example RunEvent with AIGP governance facets
- OpenLineage test suite (`tests/test_openlineage.py`)
- Context and lineage resource type tests in `test_merkle.py`
- End-to-end example Scenario 9: OpenLineage triple-emit with context + lineage resources

### Changed
- `resource_type` enum now includes `"context"` and `"lineage"` (schema, spec, Python SDK)
- `compute_leaf_hash()` accepts `"context"` and `"lineage"` as valid resource_types
- `multi_resource_governance_proof()` docstring updated for `"context"` and `"lineage"` types
- `_dual_emit()` renamed from "compliance store" to "AI governance store" in comments
- AGRN regex updated to include `context` and `lineage` prefixes
- Spec version bumped to 0.5.0
- Backward compatible: existing events and hashes unchanged

## [0.4.0] - 2026-02-15

### Added
- **Merkle tree governance hash** for multi-resource operations (Spec Section 8.8)
- `governance_merkle_tree` optional field — per-resource leaf hashes enabling independent verification of policies, prompts, and tools
- `hash_type` value `"merkle-sha256"` — indicates Merkle tree root as `governance_hash`
- Spec Section 8.8: Merkle Tree Hash Computation (leaf construction with domain separators, tree algorithm with odd-promotion, verification, backward compatibility)
- Python SDK: `compute_leaf_hash()` — domain-separated SHA-256 for individual governed resources
- Python SDK: `compute_merkle_governance_hash()` — computes Merkle root + tree structure from resource list
- Python SDK: `multi_resource_governance_proof()` instrumentor method with OTel dual-emit
- OTel semantic attribute: `aigp.governance.merkle.leaf_count` — span attribute for Merkle tree observability
- OTel semantic conventions Section 3.6: Merkle Tree Governance Attributes
- OTel Collector OTTL rule to tag Merkle-tree governance spans
- Example event: `merkle-governance-proof.json` (5-leaf tree with real computed hashes)
- Merkle tree test suite (`tests/test_merkle.py`, ~20 test cases)
- End-to-end example Scenario 7: Merkle tree governance proof

### Changed
- `multi_policy_inject()` now accepts optional `resource_contents` parameter for Merkle tree construction
- `create_aigp_event()` accepts optional `governance_merkle_tree` parameter
- Schema updated with `governance_merkle_tree` object definition (optional, backward compatible)
- Backward compatible: single-resource events produce identical hashes to v0.3.0

## [0.3.0] - 2026-02-15

### Added
- **OpenTelemetry integration** — AIGP is the governance-proof semantic payload; OTel is the transport and correlation layer
- `span_id` field — 16-character lowercase hexadecimal, links AIGP events to specific OTel spans (W3C Trace Context parent-id)
- `parent_span_id` field — enables AIGP events to participate in OTel span trees
- `trace_flags` field — preserves OTel sampling decisions in governance records (W3C Trace Context trace-flags)
- Spec Section 11.4: OpenTelemetry Span Correlation (span_id, parent_span_id, trace_flags, traceparent reconstruction)
- Spec Section 11.5: AIGP Semantic Attributes for OpenTelemetry (`aigp.*` namespace with Resource, Span, and Span Event mappings)
- Spec Section 11.6: Baggage Propagation for agent-to-agent governance context
- Spec Section 11.7: W3C `tracestate` Vendor Key (`aigp=cls:{classification};pol:{policy};ver:{version}`)
- `integrations/opentelemetry/semantic-conventions.md` — full AIGP OTel semantic conventions document
- `integrations/opentelemetry/collector-config.yaml` — reference OTel Collector configuration with dual-pipeline (observability + compliance)
- Multi-policy and multi-prompt array-valued OTel attributes (`aigp.policies.names`, `aigp.policies.versions`, `aigp.prompts.names`, etc.)
- Python SDK (`sdks/python/aigp_otel`) — AIGP-OTel bridge library with:
  - `AIGPInstrumentor`: dual-emit (AIGP event + OTel span event) for all governance event types
  - `AIGPAttributes`: constants for all `aigp.*` semantic attributes
  - `AIGPBaggage`: OTel Baggage propagation for cross-agent governance context
  - `AIGPTraceState`: W3C tracestate vendor key encoding/decoding
  - `multi_policy_inject()`: array-valued attribute support for multi-policy operations
  - Tests and end-to-end example
- Example events: `inject-success-otel.json`, `multi-policy-inject-otel.json`

### Changed
- `trace_id` description updated: prefer 32-character lowercase hexadecimal (W3C Trace Context) when integrating with OTel
- Schema version bumped to 0.3.0

## [0.2.1] - 2026-02-09

### Added
- `policy_version` field — point-in-time snapshot of the policy version used during a governance action
- `prompt_version` field — point-in-time snapshot of the prompt version used during a governance action

### Changed
- `ORDER BY` key changed from `(org_id, event_type, event_time, event_id)` to `(agent_id, event_time, event_id)` — better distribution for sharding
- Recommended shard key changed from `org_id` to `cityHash64(agent_id)` — agents >> orgs, more even distribution
- TTL extended from 2 years to 3 years
- Engine recommendation changed from MergeTree to ReplicatedMergeTree for production deployments

### Removed
- `version_id` and `version_number` fields — superseded by `policy_version` and `prompt_version`

## [0.2.0] - 2026-02-08

### Added
- Formal specification document (`spec/aigp-spec.md`) with RFC 2119 normative language
- Security considerations section (integrity vs authentication, threat model)
- Privacy considerations section (GDPR/CCPA, data minimization, PII handling)
- Conformance levels: Core, Extended, Full
- Transport bindings outline (HTTP, Kafka, gRPC)
- All 16 event types covered with example files
- GitHub Actions CI for JSON Schema validation
- Community governance model (`GOVERNANCE.md`)
- Contributor Covenant Code of Conduct
- Issue and PR templates
- `ADOPTERS.md` for tracking organizations using AIGP

### Changed
- **Renamed SRN to AGRN** (Agent Governance Resource Names) — vendor-neutral naming
- `metadata` field type changed from `string` to `object` (breaking change)
- Added `pattern` validation for `governance_hash`: `^([a-f0-9]{64})?$`
- Added `ext_` prefixed extension fields via `patternProperties`
- Schema `$id` updated to `https://aigp.sandarb.ai/schema/aigp-event.schema.json`
- Version bumped to 0.2.0

### Fixed
- `additionalProperties: false` now coexists with extensibility via `patternProperties`

## [0.1.0] - 2025-01-15

### Added
- Initial draft specification
- 16 standard event types across 7 categories
- JSON Schema (`schema/aigp-event.schema.json`)
- 4 example events (inject-success, inject-denied, agent-registered, policy-violation)
- SRN (Sandarb Resource Names) naming convention
- Apache 2.0 license
- Contributing guidelines
