"""
AIGP-OpenTelemetry Bridge
=========================

A Python library that bridges AI Governance Proof (AIGP) events with
OpenTelemetry spans, enabling dual-emit governance observability.

AIGP is the governance-proof semantic payload.
OpenTelemetry is the transport and correlation layer.

Usage:
    from aigp_otel import AIGPInstrumentor, create_aigp_event

    # Initialize once at startup
    instrumentor = AIGPInstrumentor(
        agent_id="agent.trading-bot-v2",
        agent_name="Trading Bot",
        org_id="org.finco",
    )

    # Create and emit governance events (dual-emit: AIGP + OTel)
    event = instrumentor.inject_success(
        policy_name="policy.trading-limits",
        policy_version=4,
        content="Max position: $10M...",
        data_classification="confidential",
    )
"""

from aigp_otel.instrumentor import AIGPInstrumentor
from aigp_otel.events import (
    create_aigp_event,
    compute_governance_hash,
    compute_leaf_hash,
    compute_merkle_governance_hash,
)
from aigp_otel.attributes import AIGPAttributes
from aigp_otel.baggage import AIGPBaggage
from aigp_otel.tracestate import AIGPTraceState
from aigp_otel.openlineage import (
    build_governance_run_facet,
    build_resource_input_facets,
    build_openlineage_run_event,
)

__version__ = "0.5.0"
__all__ = [
    "AIGPInstrumentor",
    "create_aigp_event",
    "compute_governance_hash",
    "compute_leaf_hash",
    "compute_merkle_governance_hash",
    "AIGPAttributes",
    "AIGPBaggage",
    "AIGPTraceState",
    "build_governance_run_facet",
    "build_resource_input_facets",
    "build_openlineage_run_event",
]
