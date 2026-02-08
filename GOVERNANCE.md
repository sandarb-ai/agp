# AGP Governance

This document describes how the **Audit Governance Protocol (AGP)** specification is governed. AGP is an open specification licensed under the [Apache License 2.0](LICENSE).

## Principles

- **Open participation** -- Anyone can propose changes, review proposals, and participate in discussions.
- **Transparency** -- All decisions are made in public GitHub issues and pull requests.
- **Pragmatism** -- We favor working implementations over theoretical perfection.
- **Backward compatibility** -- Breaking changes require strong justification and a clear migration path.

## Decision-Making

AGP uses a **lazy consensus** model:

- **Minor changes** (typos, clarifications, editorial fixes) are merged after one approving review with no objections within 72 hours.
- **Specification changes** (new event types, schema modifications, behavioral requirements) require a formal review process through an AGP Enhancement Proposal (AEP).
- **Breaking changes** require unanimous approval from active maintainers and a minimum 14-day review period.

Silence is interpreted as agreement for minor changes. For spec changes, explicit approval from at least two maintainers is required.

## AGP Enhancement Proposals (AEPs)

An **AEP** is the formal mechanism for proposing changes to the AGP specification. AEPs are used for:

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
5. **Accept or Reject** -- Maintainers make a final decision based on community feedback, technical merit, and alignment with AGP principles.

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

AGP uses two versioning schemes:

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

> **Note:** Working groups have not yet been formed. This section is a placeholder for future governance structure.

As the AGP community grows, we anticipate forming working groups to focus on specific areas:

- **Schema Working Group** -- Responsible for the JSON Schema definition and validation tooling.
- **Events Working Group** -- Responsible for defining and maintaining the standard event type taxonomy.
- **Compliance Working Group** -- Responsible for conformance levels, test suites, and certification.
- **Integrations Working Group** -- Responsible for reference implementations and platform integrations.

Working groups will be established when there is sufficient community interest and participation. If you are interested in leading or joining a working group, please open a GitHub issue.

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
