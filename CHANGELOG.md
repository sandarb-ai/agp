# Changelog

All notable changes to the AIGP specification will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
