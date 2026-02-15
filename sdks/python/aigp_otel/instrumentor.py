"""
AIGP Instrumentor
=================

The core bridge between AIGP governance events and OpenTelemetry spans.
Handles dual-emit: every governance action produces both an AIGP event
(compliance store) and an OTel span event (observability backend).

Usage:
    from aigp_otel import AIGPInstrumentor

    instrumentor = AIGPInstrumentor(
        agent_id="agent.trading-bot-v2",
        agent_name="Trading Bot",
        org_id="org.finco",
    )

    # Within an active OTel span:
    event = instrumentor.inject_success(
        policy_name="policy.trading-limits",
        policy_version=4,
        content="Max position: $10M...",
        data_classification="confidential",
    )
"""

import logging
from typing import Any, Callable, Optional

from opentelemetry import trace, baggage, context
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import StatusCode, Span

from aigp_otel.attributes import AIGPAttributes
from aigp_otel.events import (
    create_aigp_event,
    compute_governance_hash,
    compute_merkle_governance_hash,
    sign_event,
)
from aigp_otel.baggage import AIGPBaggage
from aigp_otel.tracestate import AIGPTraceState

logger = logging.getLogger(__name__)


class AIGPInstrumentor:
    """
    Bridges AIGP governance events with OpenTelemetry spans.

    Responsibilities:
    1. Sets AIGP Resource attributes (agent identity — constant per process).
    2. Creates AIGP events and simultaneously emits OTel span events.
    3. Manages Baggage propagation for agent-to-agent governance context.
    4. Provides convenience methods for each AIGP event type.
    """

    def __init__(
        self,
        agent_id: str,
        agent_name: str = "",
        org_id: str = "",
        org_name: str = "",
        tracer_name: str = "aigp",
        event_callback: Optional[Callable[[dict[str, Any]], None]] = None,
        openlineage_callback: Optional[Callable[[dict[str, Any]], None]] = None,
    ):
        """
        Initialize the AIGP instrumentor.

        Args:
            agent_id: AGRN agent identifier (e.g., "agent.trading-bot-v2").
            agent_name: Human-readable agent name.
            org_id: AGRN organization identifier (e.g., "org.finco").
            org_name: Human-readable organization name.
            tracer_name: OTel tracer name for AIGP spans.
            event_callback: Optional callback invoked with each AIGP event dict.
                           Use this to send AIGP events to your AI governance store
                           (message bus, HTTP endpoint, etc.).
            openlineage_callback: Optional callback invoked with an
                           AIGPGovernanceRunFacet dict for each governance event.
                           Use this to send governance facets to your lineage
                           backend (any OpenLineage-compatible store).  Emit at most one
                           OpenLineage RunEvent per governance session/task.
        """
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.org_id = org_id
        self.org_name = org_name
        self.tracer_name = tracer_name
        self.event_callback = event_callback
        self.openlineage_callback = openlineage_callback

        self._tracer = trace.get_tracer(tracer_name, "0.8.0")

        # Causal ordering: auto-incrementing sequence per trace
        self._sequence_counters: dict[str, int] = {}

    def _next_sequence(self, trace_id: str) -> int:
        """Increment and return the next sequence number for a given trace_id."""
        current = self._sequence_counters.get(trace_id, 0)
        current += 1
        self._sequence_counters[trace_id] = current
        return current

    def get_resource_attributes(self) -> dict[str, str]:
        """
        Return AIGP resource attributes for OTel Resource initialization.

        These should be set once at process startup:

            resource = Resource.create(instrumentor.get_resource_attributes())
            provider = TracerProvider(resource=resource)
        """
        attrs = {
            AIGPAttributes.AGENT_ID: self.agent_id,
        }
        if self.agent_name:
            attrs[AIGPAttributes.AGENT_NAME] = self.agent_name
        if self.org_id:
            attrs[AIGPAttributes.ORG_ID] = self.org_id
        if self.org_name:
            attrs[AIGPAttributes.ORG_NAME] = self.org_name
        return attrs

    def _get_span_context(self, span: Optional[Span] = None) -> dict[str, str]:
        """Extract OTel span context (trace_id, span_id, trace_flags) from current or given span."""
        if span is None:
            span = trace.get_current_span()

        ctx = span.get_span_context()
        if ctx is None or not ctx.is_valid:
            return {"trace_id": "", "span_id": "", "trace_flags": "", "parent_span_id": ""}

        trace_id = format(ctx.trace_id, "032x")
        span_id = format(ctx.span_id, "016x")
        trace_flags = format(ctx.trace_flags, "02x")

        # Get parent span ID if available
        parent_span_id = ""
        if hasattr(span, "parent") and span.parent is not None:
            parent_span_id = format(span.parent.span_id, "016x")

        return {
            "trace_id": trace_id,
            "span_id": span_id,
            "trace_flags": trace_flags,
            "parent_span_id": parent_span_id,
        }

    def _emit_span_event(
        self,
        span: Span,
        event_name: str,
        aigp_event: dict[str, Any],
    ) -> None:
        """Emit an AIGP governance action as an OTel span event."""
        attrs: dict[str, Any] = {
            AIGPAttributes.EVENT_ID: aigp_event["event_id"],
            AIGPAttributes.EVENT_TYPE: aigp_event["event_type"],
            AIGPAttributes.EVENT_CATEGORY: aigp_event["event_category"],
        }

        # Governance proof
        if aigp_event.get("governance_hash"):
            attrs[AIGPAttributes.GOVERNANCE_HASH] = aigp_event["governance_hash"]
            attrs[AIGPAttributes.GOVERNANCE_HASH_TYPE] = aigp_event.get("hash_type", "sha256")

        # Data classification
        if aigp_event.get("data_classification"):
            attrs[AIGPAttributes.DATA_CLASSIFICATION] = aigp_event["data_classification"]

        # Policy (singular)
        if aigp_event.get("policy_name"):
            attrs[AIGPAttributes.POLICY_NAME] = aigp_event["policy_name"]
        if aigp_event.get("policy_version"):
            attrs[AIGPAttributes.POLICY_VERSION] = aigp_event["policy_version"]

        # Prompt (singular)
        if aigp_event.get("prompt_name"):
            attrs[AIGPAttributes.PROMPT_NAME] = aigp_event["prompt_name"]
        if aigp_event.get("prompt_version"):
            attrs[AIGPAttributes.PROMPT_VERSION] = aigp_event["prompt_version"]

        # Enforcement result (derived)
        event_type = aigp_event["event_type"]
        if "DENIED" in event_type or "VIOLATION" in event_type or "BLOCKED" in event_type:
            attrs[AIGPAttributes.ENFORCEMENT_RESULT] = AIGPAttributes.ENFORCEMENT_DENIED
        else:
            attrs[AIGPAttributes.ENFORCEMENT_RESULT] = AIGPAttributes.ENFORCEMENT_ALLOWED

        # Denial/violation details
        if aigp_event.get("severity"):
            attrs[AIGPAttributes.SEVERITY] = aigp_event["severity"]
        if aigp_event.get("violation_type"):
            attrs[AIGPAttributes.VIOLATION_TYPE] = aigp_event["violation_type"]
        if aigp_event.get("denial_reason"):
            attrs[AIGPAttributes.DENIAL_REASON] = aigp_event["denial_reason"]

        # Merkle tree governance (Section 8.8)
        if aigp_event.get("governance_merkle_tree"):
            attrs[AIGPAttributes.MERKLE_LEAF_COUNT] = aigp_event["governance_merkle_tree"]["leaf_count"]

        # Proof integrity fields (v0.8.0)
        if aigp_event.get("event_signature"):
            attrs[AIGPAttributes.EVENT_SIGNATURE] = aigp_event["event_signature"]
        if aigp_event.get("signature_key_id"):
            attrs[AIGPAttributes.SIGNATURE_KEY_ID] = aigp_event["signature_key_id"]
        if aigp_event.get("sequence_number"):
            attrs[AIGPAttributes.SEQUENCE_NUMBER] = aigp_event["sequence_number"]
        if aigp_event.get("causality_ref"):
            attrs[AIGPAttributes.CAUSALITY_REF] = aigp_event["causality_ref"]

        span.add_event(event_name, attributes=attrs)

    def _dual_emit(
        self,
        event_name: str,
        aigp_event: dict[str, Any],
        span: Optional[Span] = None,
        causality_ref: str = "",
    ) -> dict[str, Any]:
        """
        Dual-emit: create AIGP event + OTel span event.

        1. Auto-sets sequence_number (monotonic per trace_id).
        2. Optionally sets causality_ref for cross-agent ordering.
        3. Emits OTel span event (observability backend).
        4. Calls event_callback with AIGP event dict (compliance store).
        5. Returns the AIGP event dict.
        """
        if span is None:
            span = trace.get_current_span()

        # Auto-set causal ordering fields (v0.8.0)
        trace_id = aigp_event.get("trace_id", "")
        if trace_id:
            aigp_event["sequence_number"] = self._next_sequence(trace_id)
        if causality_ref:
            aigp_event["causality_ref"] = causality_ref

        # Emit OTel span event
        self._emit_span_event(span, event_name, aigp_event)

        # Set span status for denials/violations
        event_type = aigp_event["event_type"]
        if "DENIED" in event_type or "VIOLATION" in event_type or "BLOCKED" in event_type:
            severity = aigp_event.get("severity", "")
            if severity in ("critical", "high"):
                span.set_status(StatusCode.ERROR, f"AIGP: {event_type}")

        # Emit to AI governance store
        if self.event_callback:
            try:
                self.event_callback(aigp_event)
            except Exception as e:
                logger.error(f"AIGP event callback failed: {e}")

        # Emit to lineage backend (optional triple-emit)
        if self.openlineage_callback:
            try:
                from aigp_otel.openlineage import build_governance_run_facet
                ol_facet = build_governance_run_facet(aigp_event)
                self.openlineage_callback(ol_facet)
            except Exception as e:
                logger.error(f"AIGP OpenLineage callback failed: {e}")

        return aigp_event

    # ===========================================================
    # Convenience methods for each AIGP event type
    # ===========================================================

    def inject_success(
        self,
        policy_name: str,
        policy_version: int,
        content: str,
        data_classification: str = "",
        policy_id: str = "",
        template_rendered: bool = False,
        request_method: str = "",
        request_path: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """
        Emit an INJECT_SUCCESS governance event.

        Args:
            policy_name: AGRN policy name (e.g., "policy.trading-limits").
            policy_version: Policy version at time of delivery.
            content: The governed content (used to compute governance_hash).
            data_classification: Data sensitivity level.
            ...

        Returns:
            AIGP event dict.
        """
        span_ctx = self._get_span_context(span)
        governance_hash = compute_governance_hash(content)

        aigp_event = create_aigp_event(
            event_type="INJECT_SUCCESS",
            event_category="inject",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            policy_id=policy_id,
            policy_name=policy_name,
            policy_version=policy_version,
            data_classification=data_classification,
            template_rendered=template_rendered,
            request_method=request_method,
            request_path=request_path,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_INJECT_SUCCESS, aigp_event, span)

    def inject_denied(
        self,
        policy_name: str,
        denial_reason: str,
        severity: str = "medium",
        data_classification: str = "",
        policy_id: str = "",
        violation_type: str = "ACCESS_CONTROL",
        request_method: str = "",
        request_path: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """Emit an INJECT_DENIED governance event."""
        span_ctx = self._get_span_context(span)

        aigp_event = create_aigp_event(
            event_type="INJECT_DENIED",
            event_category="inject",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            policy_id=policy_id,
            policy_name=policy_name,
            data_classification=data_classification,
            denial_reason=denial_reason,
            violation_type=violation_type,
            severity=severity,
            request_method=request_method,
            request_path=request_path,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_INJECT_DENIED, aigp_event, span)

    def prompt_used(
        self,
        prompt_name: str,
        prompt_version: int,
        content: str,
        data_classification: str = "",
        prompt_id: str = "",
        template_rendered: bool = False,
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """Emit a PROMPT_USED governance event."""
        span_ctx = self._get_span_context(span)
        governance_hash = compute_governance_hash(content)

        aigp_event = create_aigp_event(
            event_type="PROMPT_USED",
            event_category="audit",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            prompt_id=prompt_id,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            data_classification=data_classification,
            template_rendered=template_rendered,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_PROMPT_USED, aigp_event, span)

    def prompt_denied(
        self,
        prompt_name: str,
        denial_reason: str,
        severity: str = "medium",
        prompt_id: str = "",
        violation_type: str = "ACCESS_CONTROL",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """Emit a PROMPT_DENIED governance event."""
        span_ctx = self._get_span_context(span)

        aigp_event = create_aigp_event(
            event_type="PROMPT_DENIED",
            event_category="audit",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            prompt_id=prompt_id,
            prompt_name=prompt_name,
            denial_reason=denial_reason,
            violation_type=violation_type,
            severity=severity,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_PROMPT_DENIED, aigp_event, span)

    def policy_violation(
        self,
        violation_type: str,
        severity: str,
        denial_reason: str,
        data_classification: str = "",
        policy_name: str = "",
        policy_version: int = 0,
        content: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """Emit a POLICY_VIOLATION governance event."""
        span_ctx = self._get_span_context(span)
        governance_hash = compute_governance_hash(content) if content else ""

        aigp_event = create_aigp_event(
            event_type="POLICY_VIOLATION",
            event_category="policy",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            policy_name=policy_name,
            policy_version=policy_version,
            data_classification=data_classification,
            denial_reason=denial_reason,
            violation_type=violation_type,
            severity=severity,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_POLICY_VIOLATION, aigp_event, span)

    def a2a_call(
        self,
        request_method: str = "A2A",
        request_path: str = "",
        content: str = "",
        data_classification: str = "",
        causality_ref: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """Emit an A2A_CALL governance event."""
        span_ctx = self._get_span_context(span)
        governance_hash = compute_governance_hash(content) if content else ""

        aigp_event = create_aigp_event(
            event_type="A2A_CALL",
            event_category="a2a",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            data_classification=data_classification,
            request_method=request_method,
            request_path=request_path,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_A2A_CALL, aigp_event, span, causality_ref=causality_ref)

    def governance_proof(
        self,
        content: str,
        data_classification: str = "",
        policy_name: str = "",
        policy_version: int = 0,
        prompt_name: str = "",
        prompt_version: int = 0,
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """Emit a GOVERNANCE_PROOF event (standalone cryptographic attestation)."""
        span_ctx = self._get_span_context(span)
        governance_hash = compute_governance_hash(content)

        aigp_event = create_aigp_event(
            event_type="GOVERNANCE_PROOF",
            event_category="governance-proof",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            policy_name=policy_name,
            policy_version=policy_version,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            data_classification=data_classification,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_GOVERNANCE_PROOF, aigp_event, span)

    def multi_policy_inject(
        self,
        policies: list[dict[str, Any]],
        content: str,
        data_classification: str = "",
        template_rendered: bool = False,
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
        resource_contents: Optional[list[tuple[str, str, str]]] = None,
    ) -> dict[str, Any]:
        """
        Emit an INJECT_SUCCESS for an operation governed by multiple policies.

        Uses array-valued OTel attributes (aigp.policies.names, aigp.policies.versions)
        per Section 3.5 of the semantic conventions.

        When `resource_contents` is provided with multiple resources, computes a
        Merkle tree governance hash (Section 8.8) where each resource gets its own
        leaf hash and the root becomes the governance_hash. The OTel span event
        carries `aigp.governance.merkle.leaf_count` for observability.

        Args:
            policies: List of dicts, each with "name" and "version" keys.
                      e.g., [{"name": "policy.trading-limits", "version": 4},
                             {"name": "policy.risk-controls", "version": 2}]
            content: The governed content (used for flat hash when
                     resource_contents is not provided).
            resource_contents: Optional list of (resource_type, resource_name,
                     content) tuples for Merkle tree hash computation. When
                     provided with >1 resource, produces merkle-sha256 hash.
            ...

        Returns:
            AIGP event dict. The primary policy (first in list) is used for the
            singular AIGP fields. All policies are recorded in annotations.
        """
        if not policies:
            raise ValueError("At least one policy is required")

        span_ctx = self._get_span_context(span)

        # Merkle tree when per-resource content is provided
        if resource_contents and len(resource_contents) > 1:
            governance_hash, merkle_tree = compute_merkle_governance_hash(resource_contents)
            hash_type = "merkle-sha256"
        else:
            governance_hash = compute_governance_hash(content)
            merkle_tree = None
            hash_type = "sha256"

        # Primary policy goes into standard AIGP fields
        primary = policies[0]

        aigp_event = create_aigp_event(
            event_type="INJECT_SUCCESS",
            event_category="inject",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            hash_type=hash_type,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            policy_name=primary["name"],
            policy_version=primary.get("version", 0),
            data_classification=data_classification,
            template_rendered=template_rendered,
            annotations={
                **(annotations or {}),
                "all_policies": [
                    {"name": p["name"], "version": p.get("version", 0)}
                    for p in policies
                ],
            },
            governance_merkle_tree=merkle_tree,
        )

        # Emit OTel span event with array attributes
        if span is None:
            span = trace.get_current_span()

        attrs: dict[str, Any] = {
            AIGPAttributes.EVENT_ID: aigp_event["event_id"],
            AIGPAttributes.EVENT_TYPE: aigp_event["event_type"],
            AIGPAttributes.EVENT_CATEGORY: aigp_event["event_category"],
            AIGPAttributes.GOVERNANCE_HASH: governance_hash,
            AIGPAttributes.GOVERNANCE_HASH_TYPE: hash_type,
            AIGPAttributes.ENFORCEMENT_RESULT: AIGPAttributes.ENFORCEMENT_ALLOWED,
            # Array-valued attributes for multiple policies
            AIGPAttributes.POLICIES_NAMES: [p["name"] for p in policies],
            AIGPAttributes.POLICIES_VERSIONS: [p.get("version", 0) for p in policies],
        }
        if data_classification:
            attrs[AIGPAttributes.DATA_CLASSIFICATION] = data_classification
        if merkle_tree:
            attrs[AIGPAttributes.MERKLE_LEAF_COUNT] = merkle_tree["leaf_count"]

        span.add_event(AIGPAttributes.EVENT_INJECT_SUCCESS, attributes=attrs)

        # Emit to AI governance store
        if self.event_callback:
            try:
                self.event_callback(aigp_event)
            except Exception as e:
                logger.error(f"AIGP event callback failed: {e}")

        # Emit to lineage backend (optional triple-emit)
        if self.openlineage_callback:
            try:
                from aigp_otel.openlineage import build_governance_run_facet
                ol_facet = build_governance_run_facet(aigp_event)
                self.openlineage_callback(ol_facet)
            except Exception as e:
                logger.error(f"AIGP OpenLineage callback failed: {e}")

        return aigp_event

    def multi_resource_governance_proof(
        self,
        resources: list[tuple[str, str, str]],
        data_classification: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """
        Emit a GOVERNANCE_PROOF for multiple governed resources using Merkle tree.

        Each resource gets its own leaf hash (domain-separated), and the Merkle
        root becomes the governance_hash. The OTel span event carries
        aigp.governance.merkle.leaf_count for observability dashboards.

        Args:
            resources: List of (resource_type, resource_name, content) tuples.
                resource_type: "policy", "prompt", "tool", "context", "lineage",
                    "memory", "model", or any custom type
                resource_name: AGRN name (e.g., "policy.trading-limits",
                    "memory.conversation-history", "model.gpt4-trading-v2")
                content: The governed content string
            data_classification: Data sensitivity level.
            annotations: Informational context (not hashed).
            span: Optional OTel span.

        Returns:
            AIGP event dict with governance_merkle_tree.
        """
        if not resources:
            raise ValueError("At least one resource is required")

        span_ctx = self._get_span_context(span)
        governance_hash, merkle_tree = compute_merkle_governance_hash(resources)
        hash_type = "merkle-sha256" if merkle_tree else "sha256"

        # Extract primary resource for singular fields
        primary_type, primary_name, _ = resources[0]
        policy_name = primary_name if primary_type == "policy" else ""
        prompt_name = primary_name if primary_type == "prompt" else ""

        aigp_event = create_aigp_event(
            event_type="GOVERNANCE_PROOF",
            event_category="governance-proof",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            hash_type=hash_type,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            policy_name=policy_name,
            prompt_name=prompt_name,
            data_classification=data_classification,
            annotations={
                **(annotations or {}),
                "all_resources": [
                    {"type": r[0], "name": r[1]} for r in resources
                ],
            },
            governance_merkle_tree=merkle_tree,
        )

        return self._dual_emit(AIGPAttributes.EVENT_GOVERNANCE_PROOF, aigp_event, span)

    # ===========================================================
    # v0.7.0 — Memory Events
    # ===========================================================

    def memory_read(
        self,
        memory_name: str,
        query: str,
        content: str,
        data_classification: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """
        Emit a MEMORY_READ governance event.

        Records that an agent retrieved content from memory (conversation history,
        RAG retrieval, vector store query, session state read).

        Args:
            memory_name: AGRN memory name (e.g., "memory.conversation-history").
            query: The retrieval query (hashed as query_hash).
            content: The retrieved content (hashed as governance_hash).
            data_classification: Data sensitivity level.
            annotations: Informational context.
            span: Optional OTel span.

        Returns:
            AIGP event dict with query_hash and governance_hash.
        """
        span_ctx = self._get_span_context(span)
        governance_hash = compute_governance_hash(content)
        query_hash = compute_governance_hash(query)

        aigp_event = create_aigp_event(
            event_type="MEMORY_READ",
            event_category="memory",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            data_classification=data_classification,
            query_hash=query_hash,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_MEMORY_READ, aigp_event, span)

    def memory_written(
        self,
        memory_name: str,
        content: str,
        previous_content: Optional[str] = None,
        data_classification: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """
        Emit a MEMORY_WRITTEN governance event.

        Records that an agent updated memory (vector store write, conversation
        history save, session state mutation).

        Args:
            memory_name: AGRN memory name (e.g., "memory.agent-state").
            content: The new memory content (hashed as governance_hash).
            previous_content: Optional previous memory content (hashed as previous_hash).
            data_classification: Data sensitivity level.
            annotations: Informational context.
            span: Optional OTel span.

        Returns:
            AIGP event dict with governance_hash and optional previous_hash.
        """
        span_ctx = self._get_span_context(span)
        governance_hash = compute_governance_hash(content)
        previous_hash = compute_governance_hash(previous_content) if previous_content else ""

        aigp_event = create_aigp_event(
            event_type="MEMORY_WRITTEN",
            event_category="memory",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            data_classification=data_classification,
            previous_hash=previous_hash,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_MEMORY_WRITTEN, aigp_event, span)

    # ===========================================================
    # v0.7.0 — Tool Events
    # ===========================================================

    def tool_invoked(
        self,
        tool_name: str,
        tool_version: int = 0,
        content: str = "",
        data_classification: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """Emit a TOOL_INVOKED governance event."""
        span_ctx = self._get_span_context(span)
        governance_hash = compute_governance_hash(content) if content else ""

        aigp_event = create_aigp_event(
            event_type="TOOL_INVOKED",
            event_category="tool",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            data_classification=data_classification,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_TOOL_INVOKED, aigp_event, span)

    def tool_denied(
        self,
        tool_name: str,
        denial_reason: str,
        severity: str = "medium",
        violation_type: str = "ACCESS_CONTROL",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """Emit a TOOL_DENIED governance event."""
        span_ctx = self._get_span_context(span)

        aigp_event = create_aigp_event(
            event_type="TOOL_DENIED",
            event_category="tool",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            denial_reason=denial_reason,
            violation_type=violation_type,
            severity=severity,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_TOOL_DENIED, aigp_event, span)

    # ===========================================================
    # v0.7.0 — Context Events
    # ===========================================================

    def context_captured(
        self,
        context_name: str,
        content: str,
        data_classification: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """Emit a CONTEXT_CAPTURED governance event."""
        span_ctx = self._get_span_context(span)
        governance_hash = compute_governance_hash(content)

        aigp_event = create_aigp_event(
            event_type="CONTEXT_CAPTURED",
            event_category="context",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            data_classification=data_classification,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_CONTEXT_CAPTURED, aigp_event, span)

    # ===========================================================
    # v0.7.0 — Lineage Events
    # ===========================================================

    def lineage_snapshot(
        self,
        lineage_name: str,
        content: str,
        data_classification: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """Emit a LINEAGE_SNAPSHOT governance event."""
        span_ctx = self._get_span_context(span)
        governance_hash = compute_governance_hash(content)

        aigp_event = create_aigp_event(
            event_type="LINEAGE_SNAPSHOT",
            event_category="lineage",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            data_classification=data_classification,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_LINEAGE_SNAPSHOT, aigp_event, span)

    # ===========================================================
    # v0.7.0 — Inference Events
    # ===========================================================

    def inference_started(
        self,
        content: str,
        data_classification: str = "",
        causality_ref: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """Emit an INFERENCE_STARTED governance event."""
        span_ctx = self._get_span_context(span)
        governance_hash = compute_governance_hash(content)

        aigp_event = create_aigp_event(
            event_type="INFERENCE_STARTED",
            event_category="inference",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            data_classification=data_classification,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_INFERENCE_STARTED, aigp_event, span, causality_ref=causality_ref)

    def inference_completed(
        self,
        content: str,
        data_classification: str = "",
        causality_ref: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """Emit an INFERENCE_COMPLETED governance event."""
        span_ctx = self._get_span_context(span)
        governance_hash = compute_governance_hash(content)

        aigp_event = create_aigp_event(
            event_type="INFERENCE_COMPLETED",
            event_category="inference",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            data_classification=data_classification,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_INFERENCE_COMPLETED, aigp_event, span, causality_ref=causality_ref)

    def inference_blocked(
        self,
        denial_reason: str,
        severity: str = "high",
        violation_type: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """Emit an INFERENCE_BLOCKED governance event."""
        span_ctx = self._get_span_context(span)

        aigp_event = create_aigp_event(
            event_type="INFERENCE_BLOCKED",
            event_category="inference",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            denial_reason=denial_reason,
            violation_type=violation_type,
            severity=severity,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_INFERENCE_BLOCKED, aigp_event, span)

    # ===========================================================
    # v0.7.0 — Human-in-the-Loop Events
    # ===========================================================

    def human_override(
        self,
        denial_reason: str,
        data_classification: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """Emit a HUMAN_OVERRIDE governance event (GDPR Art. 22)."""
        span_ctx = self._get_span_context(span)

        aigp_event = create_aigp_event(
            event_type="HUMAN_OVERRIDE",
            event_category="human",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            data_classification=data_classification,
            denial_reason=denial_reason,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_HUMAN_OVERRIDE, aigp_event, span)

    def human_approval(
        self,
        content: str,
        data_classification: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """Emit a HUMAN_APPROVAL governance event."""
        span_ctx = self._get_span_context(span)
        governance_hash = compute_governance_hash(content)

        aigp_event = create_aigp_event(
            event_type="HUMAN_APPROVAL",
            event_category="human",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            data_classification=data_classification,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_HUMAN_APPROVAL, aigp_event, span)

    # ===========================================================
    # v0.7.0 — Classification Events
    # ===========================================================

    def classification_changed(
        self,
        new_classification: str,
        previous_classification: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """Emit a CLASSIFICATION_CHANGED governance event."""
        span_ctx = self._get_span_context(span)

        merged_annotations = dict(annotations or {})
        if previous_classification:
            merged_annotations["previous_classification"] = previous_classification

        aigp_event = create_aigp_event(
            event_type="CLASSIFICATION_CHANGED",
            event_category="classification",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            data_classification=new_classification,
            annotations=merged_annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_CLASSIFICATION_CHANGED, aigp_event, span)

    # ===========================================================
    # v0.7.0 — Model Events
    # ===========================================================

    def model_loaded(
        self,
        model_name: str,
        content: str,
        data_classification: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """
        Emit a MODEL_LOADED governance event.

        Records that an agent loaded or initialized a model for inference.

        Args:
            model_name: AGRN model name (e.g., "model.gpt4-trading-v2").
            content: Model identity content (model card, config, weights hash).
            data_classification: Data sensitivity level.
            annotations: Informational context (model metadata).
            span: Optional OTel span.

        Returns:
            AIGP event dict.
        """
        span_ctx = self._get_span_context(span)
        governance_hash = compute_governance_hash(content)

        aigp_event = create_aigp_event(
            event_type="MODEL_LOADED",
            event_category="model",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            data_classification=data_classification,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_MODEL_LOADED, aigp_event, span)

    def model_switched(
        self,
        model_name: str,
        content: str,
        previous_content: Optional[str] = None,
        data_classification: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """
        Emit a MODEL_SWITCHED governance event.

        Records that an agent switched from one model to another mid-session.

        Args:
            model_name: AGRN model name of the NEW model.
            content: New model identity content (hashed as governance_hash).
            previous_content: Previous model identity content (hashed as previous_hash).
            data_classification: Data sensitivity level.
            annotations: Should include previous_model and new_model identifiers.
            span: Optional OTel span.

        Returns:
            AIGP event dict with governance_hash and previous_hash.
        """
        span_ctx = self._get_span_context(span)
        governance_hash = compute_governance_hash(content)
        previous_hash = compute_governance_hash(previous_content) if previous_content else ""

        aigp_event = create_aigp_event(
            event_type="MODEL_SWITCHED",
            event_category="model",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            data_classification=data_classification,
            previous_hash=previous_hash,
            annotations=annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_MODEL_SWITCHED, aigp_event, span)

    # ===========================================================
    # v0.8.0 — Boundary Events
    # ===========================================================

    def unverified_boundary(
        self,
        target_agent_id: str,
        content: str = "",
        data_classification: str = "",
        causality_ref: str = "",
        annotations: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """
        Emit an UNVERIFIED_BOUNDARY governance event.

        Records that a governed agent interacted with an ungoverned (or
        unverifiable) external system — a "Dark Node." This event provides
        visibility into trust boundary crossings during partial AIGP adoption.

        Args:
            target_agent_id: Identifier of the ungoverned target agent/system.
            content: Optional content exchanged (hashed as governance_hash).
            data_classification: Data sensitivity level.
            causality_ref: event_id of the preceding event in the causal chain.
            annotations: Informational context. SHOULD include target_agent_id
                and protocol details.
            span: Optional OTel span.

        Returns:
            AIGP event dict.
        """
        span_ctx = self._get_span_context(span)
        governance_hash = compute_governance_hash(content) if content else ""

        merged_annotations = dict(annotations or {})
        merged_annotations["target_agent_id"] = target_agent_id

        aigp_event = create_aigp_event(
            event_type="UNVERIFIED_BOUNDARY",
            event_category="boundary",
            agent_id=self.agent_id,
            trace_id=span_ctx["trace_id"],
            governance_hash=governance_hash,
            span_id=span_ctx["span_id"],
            parent_span_id=span_ctx["parent_span_id"],
            trace_flags=span_ctx["trace_flags"],
            agent_name=self.agent_name,
            org_id=self.org_id,
            org_name=self.org_name,
            data_classification=data_classification,
            annotations=merged_annotations,
        )

        return self._dual_emit(AIGPAttributes.EVENT_UNVERIFIED_BOUNDARY, aigp_event, span, causality_ref=causality_ref)
