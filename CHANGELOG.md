# Changelog

All notable changes to the AGP specification will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-02-08

### Added
- Formal specification document (`spec/agp-spec.md`) with RFC 2119 normative language
- Security considerations section (integrity vs authentication, threat model)
- Privacy considerations section (GDPR/CCPA, data minimization, PII handling)
- Conformance levels: Core, Extended, Full
- Transport bindings outline (HTTP, Kafka, gRPC)
- All 16 event types covered with example files
- GitHub Actions CI for JSON Schema validation
- Community governance model (`GOVERNANCE.md`)
- Contributor Covenant Code of Conduct
- Issue and PR templates
- `ADOPTERS.md` for tracking organizations using AGP

### Changed
- **Renamed SRN to AGRN** (Agent Governance Resource Names) — vendor-neutral naming
- `metadata` field type changed from `string` to `object` (breaking change)
- Added `pattern` validation for `governance_hash`: `^([a-f0-9]{64})?$`
- Added `ext_` prefixed extension fields via `patternProperties`
- Schema `$id` updated to `https://agp.sandarb.ai/schema/agp-event.schema.json`
- Version bumped to 0.2.0

### Fixed
- `additionalProperties: false` now coexists with extensibility via `patternProperties`

## [0.1.0] - 2025-01-15

### Added
- Initial draft specification
- 16 standard event types across 7 categories
- JSON Schema (`schema/agp-event.schema.json`)
- 4 example events (inject-success, inject-denied, agent-registered, policy-violation)
- SRN (Sandarb Resource Names) naming convention
- Apache 2.0 license
- Contributing guidelines
