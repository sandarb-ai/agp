# AI Governance Proof (AIGP) Specification

**Version:** 0.4.0 (Draft)

**Status:** Draft

**Editors:** AIGP Community

**License:** Apache 2.0

**Latest published version:** https://github.com/sandarb-ai/aigp

---

## Abstract

The AI Governance Proof (AIGP) specification defines a structured, transport-agnostic event format for capturing cryptographic proof of governance actions performed by or upon AI agents. AIGP events provide a tamper-evident audit trail that records what happened, which agent acted, what data was involved, and whether the action was permitted. This specification establishes the required and optional fields, event types, naming conventions, hash computation rules, and conformance levels that implementations MUST follow to produce interoperable governance records.

---

## Status of This Document

This document is a **Draft** specification. It has not been submitted to any standards body and does not represent a finalized standard. The specification is published to solicit feedback from implementers, governance practitioners, regulators, and the broader AI engineering community.

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.ietf.org/rfc/rfc2119.txt) and [RFC 8174](https://www.ietf.org/rfc/rfc8174.txt) when, and only when, they appear in ALL CAPITALS.

Future versions of this specification may introduce breaking changes. Implementers SHOULD be prepared for schema evolution and SHOULD version their event producers accordingly.

---

## Table of Contents

- [Abstract](#abstract)
- [Status of This Document](#status-of-this-document)
- [1. Introduction](#1-introduction)
- [2. Notational Conventions](#2-notational-conventions)
- [3. Terminology](#3-terminology)
- [4. Design Principles](#4-design-principles)
- [5. AIGP Event Structure](#5-aigp-event-structure)
  - [5.1 Required Fields](#51-required-fields)
  - [5.2 Agent and Organization Fields](#52-agent-and-organization-fields)
  - [5.3 Policy and Prompt Fields](#53-policy-and-prompt-fields)
  - [5.4 Governance Proof Fields](#54-governance-proof-fields)
  - [5.5 Denial and Policy Fields](#55-denial-and-policy-fields)
  - [5.6 Request Fields](#56-request-fields)
  - [5.7 Metadata and Timestamps](#57-metadata-and-timestamps)
  - [5.8 Extension Fields](#58-extension-fields)
- [6. Event Types](#6-event-types)
  - [6.1 Policy Injection Events](#61-policy-injection-events)
  - [6.2 Prompt Usage Events](#62-prompt-usage-events)
  - [6.3 Agent Lifecycle Events](#63-agent-lifecycle-events)
  - [6.4 Policy Lifecycle Events](#64-policy-lifecycle-events)
  - [6.5 Prompt Lifecycle Events](#65-prompt-lifecycle-events)
  - [6.6 Governance Proof Events](#66-governance-proof-events)
  - [6.7 Policy Events](#67-policy-events)
  - [6.8 Agent-to-Agent Events](#68-agent-to-agent-events)
- [7. Agent Governance Resource Names (AGRN)](#7-governance-resource-names-grn)
- [8. Governance Hash Computation](#8-governance-hash-computation)
- [9. Data Classification Levels](#9-data-classification-levels)
- [10. Severity Levels](#10-severity-levels)
- [11. Trace ID Conventions](#11-trace-id-conventions)
  - [11.1 Accepted Formats](#111-accepted-formats)
  - [11.2 Consistency Requirements](#112-consistency-requirements)
  - [11.3 Generation](#113-generation)
  - [11.4 OpenTelemetry Span Correlation](#114-opentelemetry-span-correlation)
  - [11.5 AIGP Semantic Attributes for OpenTelemetry](#115-aigp-semantic-attributes-for-opentelemetry)
  - [11.6 Baggage Propagation](#116-baggage-propagation)
  - [11.7 W3C `tracestate` Vendor Key](#117-w3c-tracestate-vendor-key)
- [12. Conformance Levels](#12-conformance-levels)
- [13. Transport Bindings](#13-transport-bindings)
  - [13.1 HTTP](#131-http)
  - [13.2 Kafka](#132-kafka)
  - [13.3 gRPC](#133-grpc)
- [14. Security Considerations](#14-security-considerations)
- [15. Privacy Considerations](#15-privacy-considerations)
- [16. IANA Considerations](#16-iana-considerations)
- [Appendix A: JSON Schema](#appendix-a-json-schema)
- [Appendix B: Complete Example](#appendix-b-complete-example)
- [Appendix C: Change Log](#appendix-c-change-log)
- [References](#references)

---

## 1. Introduction

### 1.1 Problem Statement

AI agents are being deployed across every industry. They access organizational data, make decisions, and interact with users and other systems. Regulators, auditors, and security teams face a common challenge: there is no shared format for proving that an AI agent accessed the right data, used an approved prompt, and did not violate any policy.

Today, governance evidence is captured inconsistently. Some organizations search through unstructured logs. Some build custom audit tables. Some do not capture governance events at all. The lack of a common event format makes cross-organization auditing impractical, regulatory compliance difficult to demonstrate, and incident investigation slow.

### 1.2 Motivation

The AIGP specification addresses this gap by defining a structured, cryptographic event format for AI agent governance actions. The format captures:

- **What happened** -- the event type and category.
- **Who acted** -- the agent, its organization, and trace context.
- **What data was involved** -- the policy or prompt, its version, and classification.
- **Whether it was allowed** -- denial reasons, violation types, and severity.
- **Cryptographic proof** -- a hash of the governed content at the time of the action.

AIGP is designed to be adopted by any platform, framework, or organization regardless of the agent protocol (A2A, MCP, REST, gRPC, or others) or storage backend in use.

### 1.3 Scope

This specification defines:

- The structure and semantics of an AIGP event.
- The set of standard event types and their categories.
- Naming conventions for governed resources (Agent Governance Resource Names).
- Rules for computing the governance hash.
- Data classification and severity level taxonomies.
- Conformance levels for implementations.

This specification does not define:

- Transport-layer protocols (these are deferred to Section 13 and future companion specifications).
- Authentication or authorization mechanisms for event producers or consumers.
- Storage schemas or query languages for governance analytics.
- Agent orchestration or execution semantics.

---

## 2. Notational Conventions

### 2.1 RFC 2119 Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119][rfc2119] and [RFC 8174][rfc8174].

### 2.2 JSON Conventions

- All AIGP events MUST be representable as JSON objects conforming to [RFC 8259][rfc8259].
- String values MUST be encoded as UTF-8.
- DateTime values MUST be represented as strings in [RFC 3339][rfc3339] format with millisecond precision and the UTC time zone designator `Z` (e.g., `2025-01-15T14:30:00.123Z`).
- UUID values MUST conform to [RFC 9562][rfc9562] (UUID version 4).
- Integer values MUST be represented as JSON numbers without fractional parts.
- Boolean values MUST be represented as JSON `true` or `false`.
- The `metadata` field MUST be a JSON-encoded string (i.e., a serialized JSON object within a string value), not a nested JSON object.

### 2.3 String Conventions

- Empty optional string fields SHOULD be represented as the empty string `""` rather than JSON `null`.
- Implementations MUST NOT treat the absence of an optional field and the presence of an empty string as semantically different.

---

## 3. Terminology

**AIGP Event**
: A single structured record that captures a governance action performed by or upon an AI agent. An AIGP event contains identity, proof, classification, and metadata fields as defined in this specification.

**Governance Hash**
: A cryptographic digest (by default SHA-256) computed over the governed content at the time of an action. The governance hash provides tamper evidence: if the content changes after hash computation, the hash will no longer match the content.

**AGRN (Agent Governance Resource Name)**
: A typed, kebab-case identifier for a governed resource. The format is `type.kebab-name`, where `type` is one of `agent`, `policy`, `prompt`, or `org`. AGRNs provide globally unique, human-readable, self-describing identifiers for use in AIGP events.

**Governance Action**
: An operation that is subject to governance controls, such as delivering a policy to an agent, using a prompt, registering an agent, or detecting a policy violation.

**Agent**
: A software entity (typically an AI agent or autonomous system) that performs governance actions or is the subject of governance actions. Each agent is identified by a unique `agent_id`.

**Policy**
: A governed body of content (such as a policy document, configuration, knowledge base entry, or instruction set) that is delivered to an agent under governance controls. Policies are versioned and may be classified by sensitivity.

**Prompt**
: A governed template or instruction set used to direct an agent's behavior. Prompts are versioned and subject to approval workflows.

**Trace**
: A correlation identifier (`trace_id`) that links all AIGP events arising from a single user request, agent execution, or governance workflow. A single trace enables end-to-end reconstruction of the governance path.

**Data Classification**
: A label indicating the sensitivity level of the data involved in a governance action. This specification defines a four-tier model: `public`, `internal`, `confidential`, and `restricted`.

---

## 4. Design Principles

The following principles inform the design of the AIGP specification. Conforming implementations SHOULD adhere to these principles.

**Principle 1: Open and Protocol-Agnostic.**
AIGP events MUST NOT assume a specific transport protocol. Implementations MUST be able to produce AIGP events regardless of whether the underlying agent communication uses A2A, MCP, REST, gRPC, or any other protocol. The event format is independent of the wire protocol.

**Principle 2: Tamper-Evident by Default.**
Every AIGP event MUST include a `governance_hash` field. When governed content is present, the hash MUST be computed over that content at the source. If the content is altered between creation and verification, the hash mismatch provides evidence of tampering.

**Principle 3: Traceable End-to-End.**
Every AIGP event MUST carry a `trace_id` for distributed correlation. A single trace identifier MUST be reused across all related events (prompt retrieval, policy injection, inference, audit) so that the full governance chain can be reconstructed from a single query.

**Principle 4: Flat and Queryable.**
AIGP events SHOULD use a flat (non-nested) record structure. All governance-relevant fields SHOULD be top-level keys. This design enables direct querying without joins, making AIGP events suitable for OLAP engines, columnar stores, and streaming analytics. Implementations MAY use nested structures in the `metadata` field for domain-specific extensions.

**Principle 5: Extensible, Not Rigid.**
The specification defines required fields that capture the essentials of every governance action. The `metadata` field and extension field prefix (`ext_`) provide mechanisms for implementations to attach domain-specific data without breaking the core schema. Implementations MUST NOT require consumers to understand extension fields in order to process core AIGP events.

---

## 5. AIGP Event Structure

An AIGP event is a flat JSON object. This section defines all fields, their types, and their requirements.

### 5.1 Required Fields

The following fields MUST be present in every AIGP event. An event missing any required field is non-conforming.

| Field | Type | Description |
|---|---|---|
| `event_id` | String (UUID v4) | A globally unique identifier for this event. Implementations MUST generate a new UUID v4 for each event. |
| `event_type` | String | The type of governance action that occurred. MUST be one of the standard event types defined in Section 6, or a custom type following the `RESOURCE_ACTION` naming convention in UPPER_SNAKE_CASE. MUST match the pattern `^[A-Z][A-Z0-9_]*$`. |
| `event_category` | String | A grouping label for the event type. Standard categories are defined in Section 6. MUST be a non-empty lowercase string. |
| `event_time` | String (DateTime) | The time at which the governance action occurred. MUST be in RFC 3339 format with millisecond precision and UTC timezone designator `Z`. |
| `agent_id` | String | The identifier of the agent that triggered or is the subject of this governance action. SHOULD follow AGRN format (`agent.kebab-name`). MUST be a non-empty string. |
| `governance_hash` | String | The SHA-256 hash of the governed content, computed as specified in Section 8. For events where no content is governed (e.g., `AGENT_REGISTERED`), this field MUST be present but SHOULD be the empty string `""`. |
| `trace_id` | String | A distributed trace identifier for end-to-end correlation. MUST be a non-empty string. SHOULD conform to one of the formats specified in Section 11. |

### 5.2 Agent and Organization Fields

The following fields provide human-readable context about the agent and its organizational affiliation. These fields are OPTIONAL.

| Field | Type | Default | Description |
|---|---|---|---|
| `agent_name` | String | `""` | Human-readable display name of the agent. |
| `org_id` | String | `""` | Identifier of the organization the agent belongs to. SHOULD follow AGRN format (`org.kebab-name`). Used for data locality, partitioning, and multi-tenant governance. |
| `org_name` | String | `""` | Human-readable display name of the organization. |

### 5.3 Policy and Prompt Fields

The following fields identify the governed policy or prompt involved in the governance action. These fields are OPTIONAL but SHOULD be populated when the event involves a policy or prompt resource.

| Field | Type | Default | Description |
|---|---|---|---|
| `policy_id` | String | `""` | Unique identifier of the policy that was accessed, injected, or governed. |
| `policy_name` | String | `""` | Human-readable name of the policy. SHOULD follow AGRN format (`policy.kebab-name`). |
| `policy_version` | Integer | `0` | Version of the policy at the time of this governance action. This is a point-in-time snapshot — if the policy is later updated, this field records the exact version that was used. MUST be a non-negative integer. |
| `prompt_id` | String | `""` | Unique identifier of the prompt that was used or governed. |
| `prompt_name` | String | `""` | Human-readable name of the prompt. SHOULD follow AGRN format (`prompt.kebab-name`). |
| `prompt_version` | Integer | `0` | Version of the prompt at the time of this governance action. This is a point-in-time snapshot — if the prompt is later updated, this field records the exact version that was used. MUST be a non-negative integer. |

### 5.4 Governance Proof Fields

The following fields relate to the cryptographic proof and traceability of the governance action. The `governance_hash` and `trace_id` fields are required (see Section 5.1). The remaining fields in this group are OPTIONAL unless noted.

| Field | Type | Default | Description |
|---|---|---|---|
| `governance_hash` | String | *(required)* | See Section 5.1 and Section 8. |
| `hash_type` | String | `"sha256"` | The hash algorithm used to compute `governance_hash`. MUST be a recognized algorithm identifier. Default is `"sha256"`. Implementations MAY support `"sha384"`, `"sha512"`, or `"merkle-sha256"` (Merkle tree root). See Section 8.8. |
| `governance_merkle_tree` | Object | *(none)* | When `hash_type` is `"merkle-sha256"`, this OPTIONAL field contains the Merkle tree structure enabling per-resource verification of governed content. See Section 8.8. |
| `trace_id` | String | *(required)* | See Section 5.1 and Section 11. |
| `span_id` | String | `""` | The OpenTelemetry span ID identifying the specific operation that produced this governance event. When present, MUST be a 16-character lowercase hexadecimal string conforming to the W3C Trace Context `parent-id` format. See Section 11.4. |
| `parent_span_id` | String | `""` | The OpenTelemetry parent span ID. When present, MUST be a 16-character lowercase hexadecimal string. Enables AIGP events to participate in OTel span trees, connecting governance actions to the calling operation. See Section 11.4. |
| `trace_flags` | String | `""` | W3C Trace Context trace-flags. When present, MUST be a 2-character lowercase hexadecimal string. `"01"` indicates the trace is sampled. Preserves OTel sampling decisions in governance records. See Section 11.4. |
| `data_classification` | String | `""` | The classification level of the data involved in this governance action. When present, MUST be one of the values defined in Section 9. An empty string indicates that classification is not specified. |

### 5.5 Denial and Policy Fields

The following fields are OPTIONAL and are used for events that record access denials or policy violations. They SHOULD be populated for `INJECT_DENIED`, `PROMPT_DENIED`, and `POLICY_VIOLATION` event types.

| Field | Type | Default | Description |
|---|---|---|---|
| `denial_reason` | String | `""` | A human-readable explanation of why access was denied or why a policy violation was flagged. |
| `violation_type` | String | `""` | A machine-readable category of the policy violation (e.g., `ACCESS_CONTROL`, `DATA_CLASSIFICATION_BREACH`). Implementations MAY define their own violation type vocabulary. |
| `severity` | String | `""` | The impact level of the denial or violation. When present, MUST be one of the values defined in Section 10. |

### 5.6 Request Fields

The following fields are OPTIONAL and capture information about the request that triggered the governance action.

| Field | Type | Default | Description |
|---|---|---|---|
| `source_ip` | String | `""` | The IP address of the requesting agent or service. See Section 15 for privacy considerations regarding this field. |
| `request_method` | String | `""` | The protocol method or action that triggered the event (e.g., `GET`, `POST`, `A2A`, `MCP`). |
| `request_path` | String | `""` | The API path, endpoint, or skill name associated with the request. |

### 5.7 Metadata and Timestamps

The following fields are OPTIONAL and provide extensibility and operational metadata.

| Field | Type | Default | Description |
|---|---|---|---|
| `template_rendered` | Boolean | `false` | Indicates whether the policy content was rendered with template variables before delivery. When `true`, the `governance_hash` MUST be computed over the rendered (post-substitution) content. |
| `ingested_at` | String (DateTime) | *(none)* | The time at which the event was received by the analytics or storage system. MUST be in RFC 3339 format with millisecond precision and UTC timezone designator `Z`. This field enables measurement of ingestion latency (`ingested_at` minus `event_time`). |
| `metadata` | String (JSON) | `"{}"` | An extensible field for domain-specific data. The value MUST be a valid JSON string (a serialized JSON object). Implementations MAY use this field to attach regulatory hooks, custom tags, framework-specific data, or other non-standard data. Consumers MUST NOT require specific keys within `metadata` to process core AIGP events. |

### 5.8 Extension Fields

Fields prefixed with `ext_` are reserved for implementation-specific extensions. Extension fields allow implementations to add domain-specific top-level fields without conflicting with current or future standard fields.

- Extension field names MUST begin with `ext_` followed by one or more lowercase alphanumeric characters or underscores.
- Extension field names MUST match the pattern `^ext_[a-z][a-z0-9_]*$`.
- Implementations MUST NOT require consumers to understand extension fields in order to process core AIGP events.
- Consumers MUST ignore extension fields they do not recognize.
- The AIGP JSON Schema (Appendix A) MAY be configured to permit additional properties prefixed with `ext_` while rejecting other unknown fields.

---

## 6. Event Types

The AIGP specification defines 16 standard event types across 8 categories. Implementations MUST use the standard event types for the governance actions described below. Implementations MAY define additional custom event types following the naming conventions in this section.

### 6.1 Policy Injection Events

**Category:** `inject`

#### INJECT_SUCCESS

- **Emitted when:** An agent successfully receives a governed policy. Implementations MUST emit this event when a policy injection request is fulfilled.
- **Required fields:** All fields from Section 5.1.
- **SHOULD be present:** `policy_id`, `policy_name`, `policy_version`, `data_classification`, `governance_hash` (non-empty, computed over delivered content), `template_rendered`.
- **MAY be present:** `org_id`, `org_name`, `agent_name`, `source_ip`, `request_method`, `request_path`, `metadata`.

#### INJECT_DENIED

- **Emitted when:** An agent's request for a governed policy is denied by access control or policy enforcement. Implementations MUST emit this event when a policy injection request is rejected.
- **Required fields:** All fields from Section 5.1.
- **SHOULD be present:** `policy_id`, `policy_name`, `data_classification`, `denial_reason`, `violation_type`, `severity`.
- **Notes:** The `governance_hash` SHOULD be the empty string, as no content was delivered. The `policy_version` and `prompt_version` MAY be zero if the denial occurred before version resolution.

### 6.2 Prompt Usage Events

**Category:** `audit`

#### PROMPT_USED

- **Emitted when:** An agent successfully retrieves and uses an approved prompt. Implementations MUST emit this event when a prompt is delivered to an agent.
- **Required fields:** All fields from Section 5.1.
- **SHOULD be present:** `prompt_id`, `prompt_name`, `governance_hash` (non-empty, computed over the prompt content), `data_classification`.
- **MAY be present:** `prompt_version`, `org_id`, `agent_name`, `template_rendered`.

#### PROMPT_DENIED

- **Emitted when:** An agent's request for a prompt is denied. Implementations MUST emit this event when a prompt retrieval request is rejected.
- **Required fields:** All fields from Section 5.1.
- **SHOULD be present:** `prompt_id`, `prompt_name`, `denial_reason`, `violation_type`, `severity`.
- **Notes:** The `governance_hash` SHOULD be the empty string.

### 6.3 Agent Lifecycle Events

**Category:** `agent-lifecycle`

#### AGENT_REGISTERED

- **Emitted when:** A new agent is registered in the governance registry. Implementations MUST emit this event when an agent is added to the system.
- **Required fields:** All fields from Section 5.1.
- **SHOULD be present:** `agent_name`, `org_id`, `org_name`.
- **Notes:** The `governance_hash` SHOULD be the empty string, as no governed content is involved. Implementations MAY include agent metadata (e.g., A2A endpoint URL, owner team) in the `metadata` field.

#### AGENT_APPROVED

- **Emitted when:** A registered agent is approved for operation. Implementations MUST emit this event when an agent transitions from a pending state to an approved state.
- **Required fields:** All fields from Section 5.1.
- **SHOULD be present:** `agent_name`, `org_id`.

#### AGENT_DEACTIVATED

- **Emitted when:** An agent is deactivated or removed from the governance registry. Implementations MUST emit this event when an agent is deactivated.
- **Required fields:** All fields from Section 5.1.
- **SHOULD be present:** `agent_name`, `org_id`.
- **Notes:** Implementations MAY record the reason for deactivation in the `metadata` field.

### 6.4 Policy Lifecycle Events

**Category:** `policy-lifecycle`

#### POLICY_CREATED

- **Emitted when:** A new governed policy is created. Implementations MUST emit this event when a policy resource is first created.
- **Required fields:** All fields from Section 5.1.
- **SHOULD be present:** `policy_id`, `policy_name`, `data_classification`, `governance_hash` (computed over the initial content).

#### POLICY_VERSION_APPROVED

- **Emitted when:** A new version of a governed policy is approved for use. Implementations MUST emit this event when a policy version transitions to an approved state.
- **Required fields:** All fields from Section 5.1.
- **SHOULD be present:** `policy_id`, `policy_name`, `policy_version`, `governance_hash` (computed over the approved version content), `data_classification`.

#### POLICY_ARCHIVED

- **Emitted when:** A governed policy is archived and is no longer available for injection. Implementations MUST emit this event when a policy is archived.
- **Required fields:** All fields from Section 5.1.
- **SHOULD be present:** `policy_id`, `policy_name`.

### 6.5 Prompt Lifecycle Events

**Category:** `prompt-lifecycle`

#### PROMPT_VERSION_CREATED

- **Emitted when:** A new version of a governed prompt is created. Implementations MUST emit this event when a new prompt version is authored.
- **Required fields:** All fields from Section 5.1.
- **SHOULD be present:** `prompt_id`, `prompt_name`, `prompt_version`, `governance_hash` (computed over the prompt version content).

#### PROMPT_VERSION_APPROVED

- **Emitted when:** A prompt version is approved for use. Implementations MUST emit this event when a prompt version transitions to an approved state.
- **Required fields:** All fields from Section 5.1.
- **SHOULD be present:** `prompt_id`, `prompt_name`, `prompt_version`, `governance_hash` (computed over the approved prompt content).

### 6.6 Governance Proof Events

**Category:** `governance-proof`

#### GOVERNANCE_PROOF

- **Emitted when:** A cryptographic proof-of-delivery is explicitly recorded, independent of any specific injection or usage event. Implementations MAY emit this event as a standalone attestation of governance.
- **Required fields:** All fields from Section 5.1.
- **SHOULD be present:** `governance_hash` (non-empty), `policy_id` or `prompt_id` (whichever is applicable), `data_classification`.
- **Notes:** This event type enables implementations to produce proof records that are decoupled from the operational events. It is useful for batch attestation, offline auditing, and regulatory reporting.

### 6.7 Policy Events

**Category:** `policy`

#### POLICY_VIOLATION

- **Emitted when:** A governance policy is violated. Implementations MUST emit this event when a policy violation is detected, whether or not the violating action was blocked.
- **Required fields:** All fields from Section 5.1.
- **SHOULD be present:** `denial_reason`, `violation_type`, `severity`, `data_classification`.
- **MAY be present:** `policy_id`, `policy_name`, `policy_version`, `prompt_id`, `prompt_name`, `prompt_version`.
- **Notes:** The `governance_hash` SHOULD contain the hash of the content involved in the violation, if available. The `severity` field SHOULD reflect the impact level as defined in Section 10.

### 6.8 Agent-to-Agent Events

**Category:** `a2a`

#### A2A_CALL

- **Emitted when:** An agent-to-agent protocol call is made. Implementations SHOULD emit this event when an agent invokes another agent via any agent-to-agent protocol.
- **Required fields:** All fields from Section 5.1.
- **SHOULD be present:** `request_method`, `request_path`.
- **MAY be present:** `governance_hash` (if governed content is exchanged), `policy_id`, `prompt_id`, `metadata`.
- **Notes:** Implementations MAY use the `metadata` field to record the target agent identifier, the protocol used (A2A, MCP, etc.), and the outcome of the call.

### 6.9 Custom Event Types

Implementations MAY define custom event types beyond the 16 standard types. Custom event types:

- MUST follow the `RESOURCE_ACTION` naming convention in UPPER_SNAKE_CASE.
- MUST match the pattern `^[A-Z][A-Z0-9_]*$`.
- SHOULD use a category string that groups logically related events.
- MUST NOT redefine the semantics of the 16 standard event types.

Examples of domain-specific custom event types include `PATIENT_DATA_ACCESSED`, `CONSENT_VERIFIED`, `MODEL_INFERENCE_LOGGED`, and `TRADE_EXECUTION_AUDITED`.

---

## 7. Agent Governance Resource Names (AGRN)

### 7.1 Overview

A Agent Governance Resource Name (AGRN) is a typed, kebab-case identifier for a governed resource. AGRNs provide globally unique, human-readable, and self-describing names for agents, policies, prompts, and organizations within AIGP events.

### 7.2 Format

The AGRN format is:

```
type.kebab-name
```

Where:

- `type` is one of the defined resource type prefixes.
- `.` (dot) is the separator between the type and the name.
- `kebab-name` is a lowercase, hyphen-separated identifier.

### 7.3 Resource Type Prefixes

| Resource Type | Prefix | Example |
|---|---|---|
| Agent | `agent.` | `agent.trading-bot-v2` |
| Policy | `policy.` | `policy.eu-refund-policy` |
| Prompt | `prompt.` | `prompt.customer-support-v3` |
| Organization | `org.` | `org.finco` |

### 7.4 Naming Rules

1. The `kebab-name` portion MUST consist only of lowercase ASCII letters (`a-z`), digits (`0-9`), and hyphens (`-`).
2. The `kebab-name` MUST NOT contain underscores, spaces, or uppercase letters.
3. The `kebab-name` MUST NOT begin or end with a hyphen.
4. The `kebab-name` MUST NOT contain consecutive hyphens (`--`).
5. The `kebab-name` MUST be at least one character long.
6. The type prefix (`agent.`, `policy.`, `prompt.`, `org.`) MUST be included as part of the AGRN and makes the resource self-describing in any AIGP event or log line.
7. The complete AGRN MUST match the regular expression: `^(agent|policy|prompt|org)\.[a-z][a-z0-9]*(-[a-z0-9]+)*$`.

### 7.5 Usage

- The `agent_id` field SHOULD contain a AGRN with the `agent.` prefix.
- The `policy_name` field SHOULD contain a AGRN with the `policy.` prefix.
- The `prompt_name` field SHOULD contain a AGRN with the `prompt.` prefix.
- The `org_id` field SHOULD contain a AGRN with the `org.` prefix.
- Implementations at the Full conformance level (Section 12) MUST use AGRN naming for all resource identifier fields.
- Implementations at the Core conformance level MAY use any non-empty string for resource identifier fields.

---

## 8. Governance Hash Computation

### 8.1 Algorithm

Implementations MUST use SHA-256 as the default hash algorithm for computing the `governance_hash` field. When SHA-256 is used, the `hash_type` field SHOULD be set to `"sha256"` (or MAY be omitted, as `"sha256"` is the default).

Implementations MAY support additional hash algorithms (`sha384`, `sha512`) and the Merkle tree construction (`merkle-sha256`, see Section 8.8), and MUST indicate the algorithm used in the `hash_type` field when a non-default algorithm is selected.

### 8.2 Input Encoding

The hash input MUST be the UTF-8 encoded byte representation of the governed content. Implementations MUST NOT apply additional transformations (such as whitespace normalization or key sorting) to the content before hashing, unless such transformations are explicitly documented and consistently applied.

### 8.3 Output Format

The hash output MUST be represented as a lowercase hexadecimal string. For SHA-256, this results in exactly 64 characters. Implementations MUST NOT use uppercase hexadecimal, Base64, or any other encoding for the `governance_hash` value.

**Example:**

```
governance_hash: "a3f2b8c1d4e5f67890abcdef1234567890abcdef1234567890abcdef12345678"
```

### 8.4 Template-Rendered Content

When `template_rendered` is `true`, the `governance_hash` MUST be computed over the rendered (post-substitution) content, not the raw template. This ensures that the hash reflects the actual policy content delivered to the agent, including any variable substitutions.

### 8.5 Events Without Governed Content

For events where no governed content is present (e.g., `AGENT_REGISTERED`, `AGENT_APPROVED`, `AGENT_DEACTIVATED`), the `governance_hash` MUST be present (as it is a required field) but SHOULD be set to the empty string `""`.

### 8.6 Hash Verification

A verifier reconstructs the hash by applying the same algorithm to the same content and comparing the result to the `governance_hash` value in the event. If the values match, the content has not been altered since the event was produced. If the values differ, the content has been modified (or the event has been tampered with).

### 8.7 Reproducibility

If the same content is delivered to multiple agents, each resulting AIGP event MUST produce the same `governance_hash` value (assuming the same algorithm). This property enables auditors to verify that identical content was delivered to different agents.

### 8.8 Merkle Tree Hash Computation

#### 8.8.1 Overview

When a governance action involves multiple governed resources (policies, prompts, tools), implementations MAY compute the `governance_hash` as a Merkle tree root instead of a flat hash over concatenated content. This enables verifiers to independently verify each resource's content without possessing all resources in the bundle.

#### 8.8.2 Leaf Construction

Each leaf in the Merkle tree corresponds to one governed resource. A leaf hash MUST be computed as:

```
leaf_hash = SHA-256(UTF-8(resource_type + ":" + resource_name + ":" + content))
```

Where:
- `resource_type` MUST be one of `"policy"`, `"prompt"`, or `"tool"`.
- `resource_name` is the AGRN-format name (e.g., `"policy.trading-limits"`).
- `content` is the governed content string for that resource.
- The `":"` separator is the literal colon character (U+003A).

The prefix `resource_type:resource_name:` serves as a domain separator preventing cross-resource collision. Two different resource types with identical content MUST produce different leaf hashes.

#### 8.8.3 Tree Construction Algorithm

1. Compute leaf hashes for all governed resources per Section 8.8.2.
2. Sort leaf hashes lexicographically (ascending, lowercase hexadecimal). Sorting ensures deterministic tree construction regardless of input order.
3. If only one leaf exists, the leaf hash IS the root. The `hash_type` MUST be `"sha256"` (not `"merkle-sha256"`). This ensures backward compatibility with single-resource events.
4. If multiple leaves exist, pair them left-to-right: `parent = SHA-256(UTF-8(left_hash + right_hash))` where `+` is string concatenation of the two 64-character hexadecimal strings.
5. If the number of nodes at any level is odd, the last node MUST be promoted to the next level unchanged. Implementations MUST NOT duplicate the last node. This avoids the second-preimage vulnerability present in Bitcoin-style Merkle trees where a tree with N leaves could produce the same root as a tree with N+1 leaves.
6. Repeat steps 4-5 until a single root remains.

**Example (3 leaves):**

```
Sorted leaves: [hash_A, hash_B, hash_C]

Level 0:  hash_A    hash_B    hash_C
              \      /            |
Level 1:    hash_AB          hash_C  (promoted)
                \              /
Level 2:        merkle_root
```

#### 8.8.4 `hash_type` Value

When Merkle tree construction is used (more than one leaf), `hash_type` MUST be set to `"merkle-sha256"`. When only one resource is involved, `hash_type` MUST remain `"sha256"` and the `governance_merkle_tree` field MUST NOT be present.

#### 8.8.5 `governance_merkle_tree` Structure

When `hash_type` is `"merkle-sha256"`, the event SHOULD include a top-level `governance_merkle_tree` object with the following structure:

```json
{
  "governance_merkle_tree": {
    "algorithm": "sha256",
    "leaf_count": 3,
    "leaves": [
      {
        "resource_type": "policy",
        "resource_name": "policy.refund-limits",
        "hash": "1a2b3c4d..."
      },
      {
        "resource_type": "prompt",
        "resource_name": "prompt.customer-support-v3",
        "hash": "5e6f7a8b..."
      },
      {
        "resource_type": "tool",
        "resource_name": "tool.order-lookup",
        "hash": "9c0d1e2f..."
      }
    ]
  }
}
```

- `algorithm` — The hash algorithm used for leaf and internal node computation. MUST be `"sha256"`.
- `leaf_count` — The number of leaves. MUST equal the length of the `leaves` array. MUST be ≥ 2.
- `leaves` — An array of leaf objects sorted by `hash` value (lexicographic ascending). This is the same sort order used during tree construction (Section 8.8.3 step 2).

Each leaf object MUST contain:
- `resource_type` — One of `"policy"`, `"prompt"`, or `"tool"`.
- `resource_name` — AGRN-format resource name.
- `hash` — The 64-character lowercase hexadecimal leaf hash computed per Section 8.8.2.

#### 8.8.6 Verification

A verifier who possesses all governed resources can reconstruct the full Merkle tree and compare the computed root against `governance_hash`. If the values match, no resource content has been altered.

A verifier who possesses only a subset of resources can verify that their resources' leaf hashes appear in the `governance_merkle_tree.leaves` array, providing partial verification. This is useful when different teams own different governed resources and need to verify their portion independently.

Full Merkle proof paths (sibling hashes for inclusion proofs) are not included in this version of the specification but MAY be added in a future version.

#### 8.8.7 Backward Compatibility

- Single-resource events MUST NOT use Merkle tree construction. They produce the same flat SHA-256 hash as in previous AIGP versions.
- The `governance_merkle_tree` field is OPTIONAL. Events without this field are valid under both old and new schema versions.
- Consumers that do not understand Merkle trees can treat `governance_hash` as an opaque integrity token — the field format (64-character lowercase hex) is identical for both flat and Merkle hashes.

---

## 9. Data Classification Levels

The `data_classification` field uses a four-tier model aligned with common enterprise data governance frameworks. When the `data_classification` field is present and non-empty, it MUST contain one of the following values.

| Level | Value | Meaning |
|---|---|---|
| 1 | `public` | Data that is safe for external sharing. No access restrictions beyond standard governance logging. |
| 2 | `internal` | Data intended for organizational use only. Not to be shared externally without authorization. |
| 3 | `confidential` | Data that is restricted to authorized individuals on a need-to-know basis. Unauthorized access may have business impact. |
| 4 | `restricted` | Data of the highest sensitivity with regulatory implications. Unauthorized access may result in legal, financial, or compliance consequences. |

Implementations SHOULD classify all governed content and populate the `data_classification` field for policy injection and prompt usage events. Implementations MAY define sub-classifications within each tier using the `metadata` field.

The classification levels are ordered by sensitivity: `public` < `internal` < `confidential` < `restricted`. Implementations that enforce classification-based access control SHOULD deny access when an agent's clearance level is below the content's classification level and MUST emit an appropriate denial or violation event.

---

## 10. Severity Levels

The `severity` field indicates the impact level of a denial or policy violation event. When the `severity` field is present and non-empty, it MUST contain one of the following values.

| Value | When to Use |
|---|---|
| `critical` | Regulatory breach, exposure of restricted data (e.g., MNPI, pre-release financials), unauthorized access to restricted resources. Implementations SHOULD treat `critical` severity events as requiring immediate attention. |
| `high` | Policy violation with business impact, confidential data accessed by an unauthorized agent, or significant governance control failure. |
| `medium` | Access denied by policy (expected enforcement behavior), classification mismatch, or minor control deviation. |
| `low` | Informational denial, rate limiting, non-material policy flag, or advisory notice. |

Implementations SHOULD assign severity consistently based on the nature and impact of the governance action. The severity taxonomy is intentionally aligned with common incident management frameworks (e.g., ITIL, NIST) to enable integration with existing operational processes.

---

## 11. Trace ID Conventions

The `trace_id` field is REQUIRED (Section 5.1) and provides distributed correlation across all AIGP events arising from a single governance workflow.

### 11.1 Accepted Formats

Implementations SHOULD use one of the following trace ID formats:

| Format | Pattern | Example |
|---|---|---|
| UUID v4 | RFC 9562 UUID | `550e8400-e29b-41d4-a716-446655440000` |
| OpenTelemetry trace ID | 32-character lowercase hexadecimal | `4bf92f3577b34da6a3ce929d0e0e4736` |
| Prefixed | `trace-<uuid>` or `req-<uuid>` | `trace-550e8400-e29b-41d4-a716-446655440000` |

### 11.2 Consistency Requirements

- The same `trace_id` MUST be used across all AIGP events that are part of the same governance workflow (e.g., the prompt retrieval, policy injection, LLM inference, and audit log events for a single agent request).
- Implementations MUST NOT reuse a `trace_id` for unrelated governance workflows.
- Implementations that integrate with OpenTelemetry SHOULD propagate the OpenTelemetry trace ID as the AIGP `trace_id`.

### 11.3 Generation

- Implementations MUST generate trace IDs using a method that provides sufficient uniqueness to avoid collisions in practice (e.g., UUID v4 or cryptographically random 128-bit values).
- Implementations MUST NOT use sequential, predictable, or low-entropy values as trace IDs.

### 11.4 OpenTelemetry Span Correlation

AIGP events capture *governance actions*. OpenTelemetry spans capture *operations*. When both systems are present, they SHOULD be correlated so that a governance proof can be linked to the specific operation that produced it.

#### 11.4.1 Span ID and Parent Span ID

The `span_id` field is OPTIONAL. When present, it MUST be a 16-character lowercase hexadecimal string conforming to the W3C Trace Context `parent-id` format (64-bit, 8 bytes).

- Implementations that integrate with OpenTelemetry SHOULD populate `span_id` with the active span's ID at the time the governance event is produced.
- Implementations SHOULD populate `parent_span_id` with the parent span's ID when the governance action occurs within a nested span.
- When `span_id` is present, `trace_id` MUST use the 32-character lowercase hexadecimal format (W3C Trace Context `trace-id`).

The combination of `trace_id` + `span_id` uniquely identifies the exact position in a distributed trace where the governance action occurred. This enables auditors to correlate governance proof with operational latency, error rates, and call graphs.

#### 11.4.2 Trace Flags

The `trace_flags` field is OPTIONAL. When present, it MUST be a 2-character lowercase hexadecimal string conforming to the W3C Trace Context `trace-flags` format.

- `"01"` indicates the trace is sampled (the span was recorded by the tracing backend).
- `"00"` indicates the trace is not sampled.
- Implementations SHOULD preserve the OTel sampling decision in the `trace_flags` field so that governance events can be correlated with sampled traces.

#### 11.4.3 Reconstructing the W3C `traceparent`

When `trace_id`, `span_id`, and `trace_flags` are all present, the W3C `traceparent` header can be reconstructed:

```
traceparent: 00-{trace_id}-{span_id}-{trace_flags}
```

Example:

```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

This reconstruction enables AIGP events to be re-injected into OTel trace visualization tools (Jaeger, Grafana Tempo, Datadog APM) without data loss.

### 11.5 AIGP Semantic Attributes for OpenTelemetry

When AIGP events are emitted alongside OpenTelemetry spans, implementations SHOULD attach governance metadata as OTel span attributes using the `aigp.*` namespace. This enables OTel backends to query governance data natively.

The following table defines the mapping between AIGP event fields and OTel span attributes:

| OTel Attribute | AIGP Source Field | OTel Attribute Type | When to Set |
|---|---|---|---|
| `aigp.event.id` | `event_id` | String | Every governance span event |
| `aigp.event.type` | `event_type` | String | Every governance span event |
| `aigp.agent.id` | `agent_id` | String | Resource attribute (constant per process) |
| `aigp.agent.name` | `agent_name` | String | Resource attribute (constant per process) |
| `aigp.org.id` | `org_id` | String | Resource attribute (constant per process) |
| `aigp.policy.name` | `policy_name` | String | Span attribute (per-operation) |
| `aigp.policy.version` | `policy_version` | Int | Span attribute (per-operation) |
| `aigp.prompt.name` | `prompt_name` | String | Span attribute (per-operation) |
| `aigp.prompt.version` | `prompt_version` | Int | Span attribute (per-operation) |
| `aigp.governance.hash` | `governance_hash` | String | Span attribute (per-operation) |
| `aigp.governance.hash_type` | `hash_type` | String | Span attribute (per-operation) |
| `aigp.data.classification` | `data_classification` | String | Span attribute (per-operation) |
| `aigp.enforcement.result` | *(derived)* | String | `"allowed"` or `"denied"` based on event type |
| `aigp.severity` | `severity` | String | Span attribute (denial/violation events) |
| `aigp.violation.type` | `violation_type` | String | Span attribute (violation events) |

**Attribute type guidance:**

- **Resource attributes** (`aigp.agent.id`, `aigp.agent.name`, `aigp.org.id`) represent identity that is constant for the lifetime of the agent process. These SHOULD be set once on the OTel Resource and automatically propagated to all spans.
- **Span attributes** (`aigp.policy.name`, `aigp.governance.hash`, `aigp.data.classification`) are specific to a single governance operation and SHOULD be set on the span that performs the governance action.
- **Span events** are the primary mechanism for attaching AIGP governance records to OTel spans. Each AIGP event SHOULD be emitted as an OTel span event with the attributes above.

### 11.6 Baggage Propagation

When an agent invokes another agent (agent-to-agent calls), governance context SHOULD travel with the request using OpenTelemetry Baggage.

#### 11.6.1 Baggage Items

The following AIGP fields SHOULD be propagated as OTel Baggage items during agent-to-agent calls:

| Baggage Key | AIGP Source | Purpose |
|---|---|---|
| `aigp.policy.name` | `policy_name` | The active governed policy |
| `aigp.data.classification` | `data_classification` | Sensitivity level of governed data |
| `aigp.org.id` | `org_id` | Organizational affiliation |

#### 11.6.2 Baggage Rules

- Receiving agents SHOULD extract AIGP Baggage items and include them in any AIGP events they produce.
- Sensitive governance content (`governance_hash`, `denial_reason`, raw policy content) MUST NOT be placed in Baggage, as Baggage values are transmitted in HTTP headers and may be visible to intermediaries.
- Implementations SHOULD use the OTel `BaggageSpanProcessor` to automatically promote Baggage items into span attributes for observability backends.

### 11.7 W3C `tracestate` Vendor Key

Implementations MAY propagate lightweight governance context in the W3C `tracestate` header using the vendor key `aigp`.

#### 11.7.1 Format

```
tracestate: aigp=cls:{classification};pol:{policy_name};ver:{policy_version}
```

Where:

- `cls` is the abbreviated `data_classification` value (`pub`, `int`, `con`, `res`).
- `pol` is the `policy_name` in AGRN format (e.g., `policy.trading-limits`).
- `ver` is the `policy_version` integer.

Semicolons separate key-value pairs within the `aigp` vendor entry. Keys and values MUST NOT contain commas, equals signs, or semicolons (these are reserved by the W3C `tracestate` specification).

#### 11.7.2 Example

```
tracestate: aigp=cls:con;pol:policy.trading-limits;ver:4,dd=s:1
```

#### 11.7.3 Behavior

- The `tracestate` vendor key is OPTIONAL. Implementations that do not use it MUST NOT remove or modify the `aigp` vendor entry if it is already present in an incoming `tracestate` header.
- Unlike Baggage, `tracestate` survives through proxies, load balancers, and service meshes that do not understand OTel Baggage. It provides a minimum viable governance context that travels with every traced request.
- Implementations MUST NOT place sensitive data (hashes, denial reasons, raw content) in `tracestate` values.

---

## 12. Conformance Levels

This specification defines three conformance levels. Implementations MUST declare which level they conform to.

### 12.1 Core Conformance

An implementation conforms to the **Core** level if it satisfies all of the following:

1. Every produced AIGP event MUST contain all required fields as defined in Section 5.1 (`event_id`, `event_type`, `event_category`, `event_time`, `agent_id`, `governance_hash`, `trace_id`).
2. The `event_type` field MUST contain a valid event type: either one of the 16 standard types defined in Section 6, or a custom type conforming to the naming rules in Section 6.9.
3. The `event_id` MUST be a valid UUID v4.
4. The `event_time` MUST be a valid RFC 3339 DateTime with millisecond precision and UTC timezone designator.
5. The `governance_hash`, when non-empty, MUST be a valid lowercase hexadecimal SHA-256 digest (64 characters).

### 12.2 Extended Conformance

An implementation conforms to the **Extended** level if it satisfies all Core requirements and additionally:

1. Events MUST populate the relevant optional fields for their event type, as specified in the "SHOULD be present" lists in Section 6.
2. The `data_classification` field SHOULD be populated for events involving governed content.
3. The `severity` field SHOULD be populated for denial and violation events.
4. Resource identifiers SHOULD follow AGRN naming conventions (Section 7).
5. The `metadata` field SHOULD be a valid JSON-encoded string when present.

### 12.3 Full Conformance

An implementation conforms to the **Full** level if it satisfies all Core and Extended requirements and additionally:

1. All resource identifier fields (`agent_id`, `policy_name`, `prompt_name`, `org_id`) MUST use AGRN naming as specified in Section 7.
2. The `data_classification` field MUST be populated for all events involving governed content (policy injection, prompt usage, governance proof, and policy violation events).
3. Implementations SHOULD compute a non-empty `governance_hash` for all events where governed content is available, including lifecycle events where the content is known at the time of the event.
4. The `metadata` field MUST be a valid JSON-encoded string (defaulting to `"{}"`).
5. The `ingested_at` field SHOULD be populated by the receiving analytics system.

---

## 13. Transport Bindings

This section is a placeholder for future work. Transport bindings define how AIGP events are serialized and transmitted over specific protocols. The AIGP event format is transport-agnostic; the bindings below are informational and will be fully specified in companion documents.

### 13.1 HTTP

AIGP events MAY be transmitted over HTTP using the following conventions:

- Events SHOULD be sent as JSON in the body of an HTTP POST request.
- The `Content-Type` header MUST be `application/json`.
- Batch delivery MAY use a JSON array of AIGP events in a single request body.
- Endpoints receiving AIGP events SHOULD return HTTP 202 (Accepted) upon successful receipt.
- Transport security MUST use TLS 1.2 or later (see Section 14).

### 13.2 Kafka

AIGP events MAY be transmitted via Apache Kafka using the following conventions:

- Each AIGP event SHOULD be a single Kafka message with a JSON-serialized value.
- The message key SHOULD be the `agent_id` or `org_id` to enable partitioning by agent or organization.
- Topic naming conventions are outside the scope of this specification but SHOULD be documented by the implementing organization.

### 13.3 gRPC

AIGP events MAY be transmitted via gRPC using the following conventions:

- A Protocol Buffers (protobuf) message definition corresponding to the AIGP event schema SHOULD be provided by the implementation.
- Streaming RPCs MAY be used for high-throughput event delivery.
- The protobuf field types SHOULD map to the JSON types defined in Section 5.

---

## 14. Security Considerations

### 14.1 Integrity, Not Authentication

The `governance_hash` field provides **integrity verification** (tamper detection). It does NOT provide authentication (proof of who produced the event) or non-repudiation (proof that a specific party produced the event). Consumers MUST NOT rely on the governance hash alone to establish trust in the event producer.

### 14.2 Event Signing

Implementations that require authentication or non-repudiation SHOULD sign AIGP events using a digital signature algorithm. Recommended algorithms include:

- **Ed25519** -- for compact signatures and fast verification.
- **ECDSA with P-256** -- for compatibility with existing PKI infrastructure.

Signed events SHOULD include the signature in an extension field (e.g., `ext_signature`) and the signing key identifier in another (e.g., `ext_key_id`). Key management, certificate issuance, and trust chain establishment are outside the scope of this specification.

### 14.3 Transport Security

AIGP events SHOULD be transported over TLS 1.2 or later. Implementations MUST NOT transmit AIGP events containing `confidential` or `restricted` data over unencrypted channels.

### 14.4 Threat Model

Implementations SHOULD consider the following threats:

- **Replay attacks:** An attacker re-submits a previously captured AIGP event. Implementations SHOULD use the `event_id` (UUID) to detect and reject duplicate events.
- **Hash collision:** An attacker crafts content that produces the same `governance_hash` as different content. For SHA-256, the probability of collision is negligible (approximately 2^-128 for a birthday attack). This threat is not considered material for current deployments.
- **Man-in-the-middle:** An attacker intercepts and modifies AIGP events in transit. TLS transport (Section 14.3) mitigates this threat. Implementations requiring higher assurance SHOULD use event signing (Section 14.2).
- **Event fabrication:** An attacker injects fabricated AIGP events. Implementations SHOULD authenticate event producers and SHOULD validate that the `agent_id` matches an authorized source.

### 14.5 Content Non-Recovery

The `governance_hash` does NOT encrypt the governed content. The original content is not recoverable from the hash. The hash serves only as a fingerprint for integrity verification. Implementations that require content confidentiality MUST encrypt the content separately and MUST NOT rely on hashing for confidentiality.

---

## 15. Privacy Considerations

### 15.1 Personally Identifiable Information

AIGP events MAY contain data that constitutes personally identifiable information (PII) under applicable data protection laws. Fields that may contain PII include, but are not limited to:

- `source_ip` -- may identify an individual or a specific device.
- `agent_id` -- may be correlated with an individual operator.
- `metadata` -- may contain arbitrary data including PII.
- `trace_id` -- may be correlated with a specific user session.

### 15.2 Regulatory Compliance

Implementations MUST comply with all applicable data protection laws and regulations, including but not limited to the General Data Protection Regulation (GDPR), the California Consumer Privacy Act (CCPA), and sector-specific regulations. This specification does not provide legal compliance guidance; implementations SHOULD consult legal counsel.

### 15.3 Data Minimization

Implementations SHOULD follow the principle of data minimization: include only those fields that are necessary for the governance use case. Fields that are not relevant to a particular event SHOULD be omitted or set to their default (empty) values rather than populated with unnecessary data.

### 15.4 Source IP Handling

The `source_ip` field MAY be omitted entirely if it is not required for the governance use case. Implementations MAY anonymize the `source_ip` value (e.g., by truncating the last octet of an IPv4 address or using a privacy-preserving proxy identifier). The choice of anonymization technique is left to the implementing organization.

### 15.5 Retention Policies

Retention policies for AIGP events SHOULD be defined by the implementing organization in accordance with applicable legal, regulatory, and business requirements. This specification does not mandate a specific retention period.

### 15.6 Right to Erasure and Immutable Audit Trails

AIGP events are designed to serve as immutable audit records. Data protection laws such as GDPR grant individuals a right to erasure ("right to be forgotten") that may conflict with the immutability requirement. Implementations SHOULD document their approach to resolving this tension, which may include:

- Pseudonymization of PII fields in older events.
- Cryptographic erasure (destroying the key used to encrypt PII fields).
- Legal basis documentation for retaining audit records.

---

## 16. IANA Considerations

This document has no IANA actions. This section is included as a placeholder for potential future registration of media types, URI schemes, or other IANA-managed registries if the specification progresses toward IETF standardization.

---

## Appendix A: JSON Schema

The normative JSON Schema for AIGP events is maintained at:

```
schema/aigp-event.schema.json
```

The schema is authored in JSON Schema Draft 2020-12 and defines:

- All required and optional fields with their types.
- Enumerated values for `data_classification` and `severity`.
- Format constraints for `event_id` (UUID), `event_time` (date-time), and `ingested_at` (date-time).
- Pattern constraints for `event_type` (`^[A-Z][A-Z0-9_]*$`).
- Default values for optional fields.

Implementations SHOULD validate produced events against this schema. Implementations MAY extend the schema to support extension fields (Section 5.8) by setting `additionalProperties` to allow fields matching `^ext_[a-z][a-z0-9_]*$`.

The canonical JSON Schema is available in the AIGP repository at [schema/aigp-event.schema.json](../schema/aigp-event.schema.json).

---

## Appendix B: Complete Example

The following is a fully annotated AIGP event representing a successful policy injection. All required fields and relevant optional fields are populated.

```json
{
  "event_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "event_type": "INJECT_SUCCESS",
  "event_category": "inject",
  "event_time": "2025-01-15T14:30:00.123Z",

  "agent_id": "agent.trading-bot-v2",
  "agent_name": "Trading Bot",
  "org_id": "org.finco",
  "org_name": "FinCo",

  "policy_id": "pol-001",
  "policy_name": "policy.trading-limits",
  "policy_version": 4,

  "prompt_id": "",
  "prompt_name": "",
  "prompt_version": 0,

  "governance_hash": "a3f2b8c1d4e5f67890abcdef1234567890abcdef1234567890abcdef12345678",
  "hash_type": "sha256",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "data_classification": "confidential",

  "template_rendered": true,

  "denial_reason": "",
  "violation_type": "",
  "severity": "",

  "source_ip": "10.0.1.42",
  "request_method": "GET",
  "request_path": "/api/policies/trading-limits/content",

  "ingested_at": "2025-01-15T14:30:01.456Z",

  "metadata": "{\"regulatory_hooks\": [\"FINRA\", \"SEC\"], \"delivery_latency_ms\": 12}"
}
```

**Field-by-field annotation:**

| Field | Annotation |
|---|---|
| `event_id` | UUID v4, uniquely identifies this event. |
| `event_type` | `INJECT_SUCCESS` -- governed policy was successfully delivered. |
| `event_category` | `inject` -- categorizes this as a policy injection event. |
| `event_time` | UTC timestamp with millisecond precision when the injection occurred. |
| `agent_id` | AGRN identifying the agent: `agent.trading-bot-v2`. |
| `agent_name` | Human-readable name for display purposes. |
| `org_id` | AGRN identifying the organization: `org.finco`. |
| `org_name` | Human-readable organization name. |
| `policy_id` | Internal identifier for the policy resource. |
| `policy_name` | AGRN identifying the policy: `policy.trading-limits`. |
| `policy_version` | Numeric version of the policy at the time of delivery (4th version). |
| `prompt_version` | Numeric version of the prompt (0 = no prompt involved). |
| `prompt_id` / `prompt_name` | Empty -- this event does not involve a prompt. |
| `governance_hash` | SHA-256 hash of the rendered policy content at the time of delivery. |
| `hash_type` | `sha256` -- the algorithm used (default). |
| `trace_id` | UUID v4 correlating all events in this governance workflow. |
| `data_classification` | `confidential` -- this policy content is restricted to need-to-know access. |
| `template_rendered` | `true` -- template variables were substituted before delivery and hashing. |
| `denial_reason` / `violation_type` / `severity` | Empty -- this is a success event, not a denial or violation. |
| `source_ip` | IP address of the requesting agent or service. |
| `request_method` | `GET` -- the HTTP method used to request the policy. |
| `request_path` | The API endpoint that was called to retrieve the policy. |
| `ingested_at` | Timestamp when the analytics system received this event (1.333 seconds after `event_time`). |
| `metadata` | JSON string containing domain-specific data: regulatory hooks and delivery latency. |

---

## Appendix C: Change Log

| Version | Date | Changes |
|---|---|---|
| 0.4.0 | 2026-02-15 | Merkle tree governance hash. Adds `governance_merkle_tree` optional field. New `hash_type` value `"merkle-sha256"`. Section 8.8 defines leaf construction, tree algorithm, and verification. OTel attribute `aigp.governance.merkle.leaf_count`. Backward compatible: single-resource events unchanged. |
| 0.3.0 | 2026-02-15 | OpenTelemetry integration. Adds `span_id`, `parent_span_id`, `trace_flags` fields. Adds spec sections 11.4 (OTel Span Correlation), 11.5 (AIGP Semantic Attributes), 11.6 (Baggage Propagation), 11.7 (W3C tracestate Vendor Key). Companion semantic conventions document and reference OTel Collector configuration. |
| 0.2.1 | 2026-02-09 | Adds `policy_version` and `prompt_version` fields. Removes `version_id` and `version_number`. |
| 0.2.0 | 2026-02-08 | Formal specification with RFC 2119 language. Security and privacy sections. Conformance levels. Transport bindings. AGRN naming. |
| 0.1.0 | 2025-01-15 | Initial draft. Defines AIGP event structure, 16 standard event types, AGRN naming conventions, governance hash computation, data classification and severity levels, trace ID conventions, and three conformance levels. |

---

## References

### Normative References

- **[rfc2119]** Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119, March 1997. https://www.ietf.org/rfc/rfc2119.txt
- **[rfc8174]** Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174, May 2017. https://www.ietf.org/rfc/rfc8174.txt
- **[rfc8259]** Bray, T., Ed., "The JavaScript Object Notation (JSON) Data Interchange Format", STD 90, RFC 8259, December 2017. https://www.ietf.org/rfc/rfc8259.txt
- **[rfc3339]** Klyne, G. and C. Newman, "Date and Time on the Internet: Timestamps", RFC 3339, July 2002. https://www.ietf.org/rfc/rfc3339.txt
- **[rfc9562]** Davis, K., Peabody, B., and P. Leach, "Universally Unique IDentifiers (UUIDs)", RFC 9562, May 2024. https://www.ietf.org/rfc/rfc9562.txt

### Informative References

- **[CloudEvents]** Cloud Native Computing Foundation, "CloudEvents - Version 1.0.2", https://cloudevents.io/
- **[OpenTelemetry]** OpenTelemetry Specification, "Semantic Conventions", https://opentelemetry.io/docs/specs/semconv/
- **[OpenTelemetry-GenAI]** OpenTelemetry Specification, "Semantic Conventions for Generative AI", https://opentelemetry.io/docs/specs/semconv/gen-ai/
- **[W3C-TraceContext]** W3C, "Trace Context", W3C Recommendation, https://www.w3.org/TR/trace-context/
- **[OpenTelemetry-Baggage]** OpenTelemetry Specification, "Baggage", https://opentelemetry.io/docs/concepts/signals/baggage/
- **[FIPS-180-4]** National Institute of Standards and Technology, "Secure Hash Standard (SHS)", FIPS PUB 180-4, August 2015. https://csrc.nist.gov/publications/detail/fips/180/4/final
- **[Sandarb]** Sandarb -- Reference implementation of the AIGP specification. https://sandarb.ai
