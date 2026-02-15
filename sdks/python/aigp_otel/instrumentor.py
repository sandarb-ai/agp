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
                           (Kafka, HTTP endpoint, etc.).
            openlineage_callback: Optional callback invoked with an
                           AIGPGovernanceRunFacet dict for each governance event.
                           Use this to send governance facets to your lineage
                           backend (Marquez, DataHub, etc.).  Emit at most one
                           OpenLineage RunEvent per governance session/task.
        """
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.org_id = org_id
        self.org_name = org_name
        self.tracer_name = tracer_name
        self.event_callback = event_callback
        self.openlineage_callback = openlineage_callback

        self._tracer = trace.get_tracer(tracer_name, "0.5.0")

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
        if "DENIED" in event_type or "VIOLATION" in event_type:
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

        span.add_event(event_name, attributes=attrs)

    def _dual_emit(
        self,
        event_name: str,
        aigp_event: dict[str, Any],
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """
        Dual-emit: create AIGP event + OTel span event.

        1. Emits OTel span event (observability backend).
        2. Calls event_callback with AIGP event dict (compliance store).
        3. Returns the AIGP event dict.
        """
        if span is None:
            span = trace.get_current_span()

        # Emit OTel span event
        self._emit_span_event(span, event_name, aigp_event)

        # Set span status for denials/violations
        event_type = aigp_event["event_type"]
        if "DENIED" in event_type or "VIOLATION" in event_type:
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
        metadata: Optional[dict[str, Any]] = None,
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
            metadata=metadata,
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
        metadata: Optional[dict[str, Any]] = None,
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
            metadata=metadata,
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
        metadata: Optional[dict[str, Any]] = None,
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
            metadata=metadata,
        )

        return self._dual_emit(AIGPAttributes.EVENT_PROMPT_USED, aigp_event, span)

    def prompt_denied(
        self,
        prompt_name: str,
        denial_reason: str,
        severity: str = "medium",
        prompt_id: str = "",
        violation_type: str = "ACCESS_CONTROL",
        metadata: Optional[dict[str, Any]] = None,
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
            metadata=metadata,
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
        metadata: Optional[dict[str, Any]] = None,
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
            metadata=metadata,
        )

        return self._dual_emit(AIGPAttributes.EVENT_POLICY_VIOLATION, aigp_event, span)

    def a2a_call(
        self,
        request_method: str = "A2A",
        request_path: str = "",
        content: str = "",
        data_classification: str = "",
        metadata: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """Emit an A2A_CALL governance event."""
        span_ctx = self._get_span_context(span)
        governance_hash = compute_governance_hash(content) if content else ""

        aigp_event = create_aigp_event(
            event_type="A2A_CALL",
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
            data_classification=data_classification,
            request_method=request_method,
            request_path=request_path,
            metadata=metadata,
        )

        return self._dual_emit(AIGPAttributes.EVENT_A2A_CALL, aigp_event, span)

    def governance_proof(
        self,
        content: str,
        data_classification: str = "",
        policy_name: str = "",
        policy_version: int = 0,
        prompt_name: str = "",
        prompt_version: int = 0,
        metadata: Optional[dict[str, Any]] = None,
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
            metadata=metadata,
        )

        return self._dual_emit(AIGPAttributes.EVENT_GOVERNANCE_PROOF, aigp_event, span)

    def multi_policy_inject(
        self,
        policies: list[dict[str, Any]],
        content: str,
        data_classification: str = "",
        template_rendered: bool = False,
        metadata: Optional[dict[str, Any]] = None,
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
            singular AIGP fields. All policies are recorded in metadata.
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
            metadata={
                **(metadata or {}),
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
        metadata: Optional[dict[str, Any]] = None,
        span: Optional[Span] = None,
    ) -> dict[str, Any]:
        """
        Emit a GOVERNANCE_PROOF for multiple governed resources using Merkle tree.

        Each resource gets its own leaf hash (domain-separated), and the Merkle
        root becomes the governance_hash. The OTel span event carries
        aigp.governance.merkle.leaf_count for observability dashboards.

        Args:
            resources: List of (resource_type, resource_name, content) tuples.
                resource_type: "policy", "prompt", "tool", "context", or "lineage"
                resource_name: AGRN name (e.g., "policy.trading-limits",
                    "context.env-config", "lineage.upstream-orders")
                content: The governed content string
            data_classification: Data sensitivity level.
            metadata: Additional metadata.
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
            metadata={
                **(metadata or {}),
                "all_resources": [
                    {"type": r[0], "name": r[1]} for r in resources
                ],
            },
            governance_merkle_tree=merkle_tree,
        )

        return self._dual_emit(AIGPAttributes.EVENT_GOVERNANCE_PROOF, aigp_event, span)
