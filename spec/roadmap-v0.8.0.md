# AIGP v0.8.0 Roadmap: Proof Integrity + Production Scale

**Status:** Planning
**Target:** Post v0.7.0
**Theme:** Make governance proofs trustworthy and performant enough that a regulator, auditor, or CISO can rely on them as evidence -- not just as logs.

---

## Motivation

v0.7.0 built the vocabulary: 30 event types, 7 resource types, Merkle tree governance hash, OpenTelemetry + OpenLineage integration. But three trust gaps remain:

1. **Integrity without authentication.** `governance_hash` proves content wasn't altered, but not who produced the proof. Anyone with store access can forge events.
2. **No causal ordering.** `event_time` uses wall clocks with skew. In multi-agent pipelines, you can't prove "the policy was injected before the inference started" when timestamps overlap.
3. **Invisible Dark Nodes.** When an AIGP-governed agent calls an ungoverned system, there's a silent gap in the governance chain. The auditor doesn't even know the gap exists.

Additionally, a performance gap blocks production adoption at scale:

4. **Hashing large content on the hot path.** Memory resources and RAG context can be 100KB+. While SHA-256 itself is fast (~0.3ms for 100KB), the canonical JSON serialization step before hashing scales with content size and adds real overhead in tight loops.

---

## Features

### Feature 1: Event Signing

**Problem:** `governance_hash` proves content integrity but not who produced the proof. A malicious actor with store access can forge AIGP events with valid hashes.

**Solution:** Two new optional fields:

| Field | Type | Description |
|---|---|---|
| `event_signature` | String | JWS Compact Serialization (RFC 7515) over the canonical event JSON (excluding signature fields). ES256 (ECDSA P-256) is mandatory-to-implement. |
| `signature_key_id` | String | AGRN-style identifier for the signing key (e.g., `aigp:org.finco:agent.trading-bot-v2:2026-02`). Enables key rotation and multi-agent key management. |

**Why JWS:** Already the standard for signed JSON payloads. Includes algorithm in header. Every language has libraries. No custom cryptography needed.

**Why optional:** Signing adds key management complexity. Small teams doing internal governance don't need it. Regulated industries (finserv, healthcare) absolutely do.

**What this enables:** An auditor can verify not just "this policy content was used" but "agent.trading-bot-v2, running under org.finco's signing key, attested to this governance action." Forgery requires compromising the private key, not just the store.

**Schema changes:**
- Add `event_signature` field: `{"type": "string", "default": ""}`
- Add `signature_key_id` field: `{"type": "string", "default": ""}`

**Spec changes:**
- New Section 5.8: Event Signing Fields
- Update Section 14.2 (Event Signing) to reference first-class fields instead of annotations
- New Section 8.9: Canonical Event JSON for Signing (define which fields are signed, serialization order)

**SDK changes:**
- `create_aigp_event()`: Add `event_signature` and `signature_key_id` params
- New `sign_event(event, private_key, key_id)` function
- New `verify_event_signature(event, public_key)` function

---

### Feature 2: Causal Ordering

**Problem:** Wall clocks have skew across distributed agents. If Agent A emits `INJECT_SUCCESS` at `14:30:00.123` and Agent B emits `INFERENCE_STARTED` at `14:30:00.120`, did the inference start before the policy was injected? You can't tell.

**Solution:** Two new optional fields:

| Field | Type | Description |
|---|---|---|
| `sequence_number` | Integer | Monotonically increasing, scoped per `(agent_id, trace_id)`. Never resets within a trace. Default: 0 (unset). |
| `causality_ref` | String | Points to the `event_id` that causally precedes this event. Creates a DAG of causal dependencies across agents. Default: "" (unset). |

**What `sequence_number` proves:** "Event 47 happened after event 46 from the same agent" regardless of clock state.

**What `causality_ref` proves:** Cross-agent ordering. Agent B's inference started because Agent A's A2A call completed. The chain a regulator needs to reconstruct.

**Why this matters for multi-agent systems:** `trace_id` tells you all agents participated. `sequence_number` tells you the order within each agent. `causality_ref` tells you the order across agents.

**Schema changes:**
- Add `sequence_number` field: `{"type": "integer", "minimum": 0, "default": 0}`
- Add `causality_ref` field: `{"type": "string", "default": ""}`

**Spec changes:**
- New Section 5.8.3: Causal Ordering Fields (or 5.4 expansion)
- New Section 8.10: Causal Ordering Rules (monotonicity, scope, cross-agent references)

**SDK changes:**
- `create_aigp_event()`: Add `sequence_number` and `causality_ref` params
- `AIGPInstrumentor`: Optional auto-incrementing `sequence_number` per trace

---

### Feature 3: UNVERIFIED_BOUNDARY Event

**Problem:** When an AIGP-governed agent calls an external API, third-party agent, or any system that doesn't emit AIGP events, there's a silent gap in the governance chain. An auditor sees governed -> ??? -> governed, with no record that the gap exists.

**Solution:** New event type `UNVERIFIED_BOUNDARY` in a new `boundary` category.

**Event type:** `UNVERIFIED_BOUNDARY`
**Category:** `boundary`

**When emitted:** An AIGP-governed agent interacts with an external system that does not provide AIGP governance proof.

**Key fields:**
- `governance_hash`: Hash of what was sent to the ungoverned system (proves what left the governed zone)
- Standard annotations:
  - `annotations.target`: Target system URI or identifier
  - `annotations.protocol`: Protocol used (REST, A2A, MCP, gRPC)
  - `annotations.direction`: "outbound" or "inbound"
  - `annotations.input_hash`: Hash of the request sent
  - `annotations.output_hash`: Hash of the response received
  - `annotations.verification_status`: Why it's unverified (`no_aigp_proof_received`, `proof_signature_invalid`, `proof_expired`, `proof_schema_mismatch`)

**What this enables:** The governance chain explicitly documents its own gaps. An auditor sees "Agent B called Equifax API, no governance proof was received, here's the hash of what went out and what came back." The organization can have a policy-level decision about accepting ungoverned boundaries.

**This is the border pattern:** Governance at the boundary between governed and ungoverned space, making Dark Nodes visible without requiring universal AIGP adoption.

**Schema changes:**
- Add `UNVERIFIED_BOUNDARY` to event_type examples
- Add `boundary` to event_category examples

**Spec changes:**
- New Section 6.18: Boundary Events (before Custom Event Types, which becomes 6.19)
- Update Section 6 intro: "30" -> "31" standard event types, "14" -> "15" categories
- Update Section 6.19 (was 6.17): "30" -> "31"

**SDK changes:**
- New `attributes.py` constant: `SPAN_EVENT_UNVERIFIED_BOUNDARY`
- New `instrumentor.py` method: `unverified_boundary(target, protocol, direction, input_content, output_content, verification_status, annotations, span)`

---

### Feature 4: Pointer Pattern

**Problem:** Hashing raw content works for small policies and prompts but creates overhead for large content (100KB+ RAG contexts, conversation histories, model artifacts). The real cost isn't SHA-256 itself (~0.3ms for 100KB) -- it's the canonical JSON serialization before hashing.

**Solution:** An optional content-addressable reference mode for Merkle leaves and governance hashes.

**New field on Merkle tree leaf objects:**

| Field | Type | Description |
|---|---|---|
| `hash_mode` | String | `"content"` (default) or `"pointer"`. When `"pointer"`, the hash was computed over a content-addressable URI, not the raw content. |
| `content_ref` | String | When `hash_mode` is `"pointer"`, the URI of the immutable content blob (e.g., `s3://aigp-governance/sha256:abc123...`). |

**New annotation convention for flat (non-Merkle) events:**

```json
{
  "annotations": {
    "hash_mode": "pointer",
    "content_ref": "s3://aigp-governance/sha256:abc123def456..."
  }
}
```

**How verification works with pointers:**
1. Auditor fetches content from `content_ref` URI
2. Computes `sha256(fetched_content)` -- verifies it matches the object key (content-addressable guarantee)
3. Computes `sha256(URI)` -- verifies it matches the `governance_hash` or leaf `hash` in the AIGP event

**Chain of trust:** AIGP event -> pointer hash -> URI -> immutable blob -> content hash = object key

**Design decisions:**
- Content write to immutable storage MUST happen before AIGP event emission (two-phase commit)
- The AIGP producer computes the hash and uses it as the object key (self-verifying)
- Auditor needs access to the immutable store (creates a dependency that raw hashing avoids)
- Pointer Pattern is OPTIONAL. Raw content hashing remains the default.
- RECOMMENDED for content > 100KB

**Schema changes:**
- Add `hash_mode` and `content_ref` fields to Merkle leaf object (optional)

**Spec changes:**
- New Section 8.9 (or 8.8.8): Pointer Pattern for Large Content
- Guidance on when to use pointers vs. raw content hashing
- Verification algorithm for both modes

**SDK changes:**
- `compute_leaf_hash()`: Support `hash_mode="pointer"` parameter
- `build_openlineage_run_event()`: Pass through pointer fields on leaves
- Implementation guidance in docstrings

---

## What v0.8.0 Does NOT Include

**Content encryption/redaction:** Too complex for one release. Let the storage layer handle encryption. AIGP events are governance proof, not governance data.

**Merkle inclusion proofs:** Useful for selective verification but it's an optimization on existing Merkle trees. Ship when there's demand from real auditors.

**Real-time streaming protocol:** AIGP is a format, not a transport. OTel handles streaming; AIGP handles semantics.

**Universal adoption mandate:** The border pattern + `UNVERIFIED_BOUNDARY` gives audit visibility without requiring every agent to implement AIGP. Adoption should be gravity-based, not gate-based.

---

## Summary

| # | Feature | What It Proves / Solves | New Fields |
|---|---|---|---|
| 1 | Event Signing | **Who** produced the proof | `event_signature`, `signature_key_id` |
| 2 | Causal Ordering | **When** (sequence, not just clock) | `sequence_number`, `causality_ref` |
| 3 | `UNVERIFIED_BOUNDARY` | **What couldn't be proven** (Dark Nodes) | New event type + `boundary` category |
| 4 | Pointer Pattern | **Performance** at scale for large content | `hash_mode`, `content_ref` on Merkle leaves |

All four features are optional and backward compatible. A v0.7.0 event is valid in a v0.8.0 world.

---

## Design Principles

1. **AI governance, not compliance.** AIGP proves agents were governed. Regulatory compliance is an outcome of governance, not the governance itself. Sampling governance proofs is logically incoherent -- a governance proof either exists or it doesn't.

2. **Merkle batching over sampling.** For high-event-volume scenarios (reflection loops, tight tool-call cycles), the correct mitigation is batching N individual events into one `GOVERNANCE_PROOF` event with N Merkle leaves -- not sampling at the collector. Every leaf hash remains independently verifiable.

3. **Trust first, then optimize.** Features 1-3 close trust gaps (forgery, ordering, visibility). Feature 4 closes a performance gap. Ship them together so teams get everything they need to go from "we have governance events" to "we have trustworthy, performant governance proof at scale."

4. **Border pattern for partial adoption.** Don't require every agent to support AIGP. Instead, make the boundary between governed and ungoverned space visible and auditable. This is how TLS works in practice -- you can talk to HTTP endpoints, but the connection is marked insecure.
