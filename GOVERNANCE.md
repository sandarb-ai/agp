# AIGP Governance

This document describes how the **AI Governance Proof (AIGP)** specification is governed. AIGP is an open specification licensed under the [Apache License 2.0](LICENSE). The AIGP name and logo are trademarks of Sandarb AI (see [TRADEMARK.md](TRADEMARK.md)).

## Principles

- **Open participation** -- Anyone can propose changes, review proposals, and participate in discussions.
- **Transparency** -- All decisions are made in public GitHub issues and pull requests.
- **Pragmatism** -- We favor working implementations over theoretical perfection.
- **Backward compatibility** -- Breaking changes require strong justification and a clear migration path.

## Decision-Making

AIGP uses a **lazy consensus** model:

- **Minor changes** (typos, clarifications, editorial fixes) are merged after one approving review with no objections within 72 hours.
- **Specification changes** (new event types, schema modifications, behavioral requirements) require a formal review process through an AIGP Enhancement Proposal (AEP).
- **Breaking changes** require unanimous approval from active maintainers and a minimum 14-day review period.

Silence is interpreted as agreement for minor changes. For spec changes, explicit approval from at least two maintainers is required.

## AIGP Enhancement Proposals (AEPs)

An **AEP** is the formal mechanism for proposing changes to the AIGP specification. AEPs are used for:

- Adding or modifying event types
- Changing the JSON Schema
- Altering conformance requirements
- Introducing new specification sections
- Deprecating or removing existing features

### AEP Process

1. **Discuss** -- Open a GitHub issue using the `spec_change` template to gauge interest and gather feedback.
2. **Draft** -- Write the AEP as a pull request. Include:
   - A clear problem statement
   - The proposed solution with exact schema/spec changes
   - Backward compatibility analysis
   - Example events demonstrating the change
3. **Review** -- The AEP enters a minimum 7-day review period. All community members are encouraged to review and comment.
4. **Revise** -- Address feedback and update the proposal as needed.
5. **Accept or Reject** -- Maintainers make a final decision based on community feedback, technical merit, and alignment with AIGP principles.

### AEP States

| State | Description |
|-------|-------------|
| **Draft** | Initial proposal, open for discussion |
| **Under Review** | Formal review period (minimum 7 days) |
| **Accepted** | Approved, awaiting implementation |
| **Implemented** | Merged into the specification |
| **Rejected** | Not accepted (with documented rationale) |
| **Withdrawn** | Withdrawn by the author |

## Versioning

AIGP uses two versioning schemes:

### Schema Versioning (SemVer)

The JSON Schema follows [Semantic Versioning 2.0.0](https://semver.org/):

- **MAJOR** version for incompatible schema changes
- **MINOR** version for backward-compatible additions (e.g., new event types)
- **PATCH** version for backward-compatible fixes (e.g., clarifications, regex corrections)

### Specification Versioning

Specification releases use **dated versions** in the format `YYYY-MM-DD`, corresponding to the date of release. Each spec release references the specific schema version it covers.

## Release Process

Specification releases follow a three-stage process:

1. **Draft** -- Work-in-progress specification. May change at any time. Not suitable for production use.
2. **Release Candidate** -- Feature-complete specification undergoing final review. Only critical fixes are accepted. Minimum 14-day review period.
3. **Released** -- Stable specification. Only backward-compatible changes are permitted until the next major version.

### Release Cadence

- Minor releases are published as needed when sufficient improvements accumulate.
- Major releases are planned with at least 90 days advance notice to allow adopters to prepare.

## Working Groups

As the AIGP community grows, working groups focus on specific areas of the specification. Each working group has a charter, a lead maintainer, and reports to the project maintainers.

- **Schema Working Group** -- Responsible for the JSON Schema definition and validation tooling.
- **Events Working Group** -- Responsible for defining and maintaining the standard event type taxonomy.
- **Compliance Working Group** -- Responsible for conformance levels, test suites, certification criteria, and trademark enforcement (see below).
- **Integrations Working Group** -- Responsible for reference implementations and platform integrations.

Working groups are established when there is sufficient community interest and participation. If you are interested in leading or joining a working group, please open a GitHub issue.

## Trademark and Compliance

The AIGP specification is open — anyone can read it, implement it, and build on it under the Apache 2.0 license. The AIGP **brand** (the names "AI Governance Proof," "AIGP," and associated logos) is controlled by the project maintainers to ensure that the name continues to mean one interoperable standard, not a fragmented set of incompatible forks.

Full trademark policy: [TRADEMARK.md](TRADEMARK.md)

### Compliance Working Group

The **Compliance Working Group** is the governing body responsible for:

1. **Conformance test suite** -- Defining, maintaining, and publishing the official AIGP conformance tests. These tests verify that an implementation correctly produces and/or consumes events conforming to the AIGP schema and behavioral requirements.

2. **Certification criteria** -- Establishing the requirements an implementation must meet to use the reserved terms "AIGP Certified," "AIGP Compliant," or "AIGP Conformant." No implementation may use these terms without passing the official conformance tests.

3. **Trademark enforcement** -- Reviewing reported trademark concerns and recommending action to the project maintainers in accordance with the [Trademark Policy](TRADEMARK.md).

4. **Compatibility levels** -- Defining tiers of AIGP compatibility (e.g., "AIGP Producer," "AIGP Consumer," "AIGP Full") as the specification matures.

### Principles

- **The spec is open; the brand is governed.** Anyone can implement AIGP. Only conforming implementations may claim certification.
- **Self-testing first.** The conformance test suite will be open source. Implementers can self-test before requesting formal certification.
- **No pay-to-play.** Certification will be based on technical conformance, not commercial relationships.
- **Transparency.** All certified implementations will be listed publicly in [ADOPTERS.md](ADOPTERS.md) with their certification status and version.

## Roles

### Maintainers

Maintainers have merge access and are responsible for the overall direction of the specification. Current maintainers:

- **Sandarb** ([@sandarb-ai](https://github.com/sandarb-ai)) -- Project creator and lead maintainer

### Contributors

Anyone who has had a pull request merged is a contributor. Contributors are listed in the GitHub contributor graph and acknowledged in release notes.

### Community Members

Anyone participating in issues, discussions, or reviews is a valued community member.

## Amendments

This governance document may be amended through the standard AEP process. Changes to governance require a minimum 14-day review period and approval from all active maintainers.

---

*This governance model is inspired by open specification projects such as OpenTelemetry, CloudEvents, and the OpenAPI Initiative.*
