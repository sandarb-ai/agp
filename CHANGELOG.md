# Changelog

All notable changes to the AIGP specification will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
