"""
AIGP + OpenTelemetry End-to-End Example
========================================

Demonstrates the full dual-emit architecture:
1. OTel tracer with AIGP Resource attributes (agent identity)
2. Policy injection with governance hash → AIGP event + OTel span event
3. Multi-policy injection with array-valued attributes
4. Prompt usage governance
5. Policy violation detection
6. Agent-to-agent call with Baggage propagation
7. tracestate vendor key for lightweight governance signaling
8. Merkle tree governance proof for multi-resource verification
9. OpenLineage triple-emit with context resource

Run:
    pip install opentelemetry-api opentelemetry-sdk
    python examples/end_to_end.py
"""

import json
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource

from aigp_otel import AIGPInstrumentor
from aigp_otel.baggage import AIGPBaggage
from aigp_otel.tracestate import AIGPTraceState


def compliance_store_callback(aigp_event: dict) -> None:
    """
    Simulates sending AIGP events to a compliance store (Kafka, ClickHouse, etc.).
    In production, replace this with your actual event pipeline.
    """
    print(f"\n--- AIGP Event -> Compliance Store ---")
    print(f"  event_type:    {aigp_event['event_type']}")
    print(f"  trace_id:      {aigp_event['trace_id']}")
    print(f"  span_id:       {aigp_event['span_id']}")
    print(f"  governance_hash: {aigp_event['governance_hash'][:16]}...")
    print(f"  policy_name:   {aigp_event.get('policy_name', 'N/A')}")
    print(f"  classification: {aigp_event.get('data_classification', 'N/A')}")
    print(f"--------------------------------------")


def main():
    # ===========================================================
    # Step 1: Initialize OTel with AIGP Resource attributes
    # ===========================================================
    instrumentor = AIGPInstrumentor(
        agent_id="agent.trading-bot-v2",
        agent_name="Trading Bot",
        org_id="org.finco",
        org_name="FinCo",
        event_callback=compliance_store_callback,
    )

    # AIGP resource attributes travel with every span automatically
    resource = Resource.create({
        **instrumentor.get_resource_attributes(),
        "service.name": "trading-bot-v2",
        "service.version": "2.4.1",
        "deployment.environment": "production",
    })

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)

    tracer = trace.get_tracer("aigp.example", "0.4.0")

    # ===========================================================
    # Step 2: Single policy injection with OTel correlation
    # ===========================================================
    print("\n=== Scenario 1: Single Policy Injection ===")

    with tracer.start_as_current_span("invoke_agent.trading_bot") as span:
        # Set gen_ai.* attributes (OTel GenAI conventions)
        span.set_attribute("gen_ai.operation.name", "invoke_agent")
        span.set_attribute("gen_ai.system", "custom")

        # Inject governed policy — dual-emit happens automatically
        policy_content = "You are a trading assistant. Maximum single position: $10M. Daily loss limit: $500K."
        event = instrumentor.inject_success(
            policy_name="policy.trading-limits",
            policy_version=4,
            content=policy_content,
            data_classification="confidential",
            template_rendered=True,
            request_method="GET",
            request_path="/api/policies/trading-limits/content",
            metadata={"regulatory_hooks": ["FINRA", "SEC"]},
        )

    # ===========================================================
    # Step 3: Multi-policy injection (array-valued attributes)
    # ===========================================================
    print("\n=== Scenario 2: Multi-Policy Injection ===")

    with tracer.start_as_current_span("invoke_agent.trading_bot.multi") as span:
        span.set_attribute("gen_ai.operation.name", "invoke_agent")

        # Agent is governed by TWO policies simultaneously
        combined_content = "Trading limits: $10M max. Risk controls: VaR < 2%."
        event = instrumentor.multi_policy_inject(
            policies=[
                {"name": "policy.trading-limits", "version": 4},
                {"name": "policy.risk-controls", "version": 2},
            ],
            content=combined_content,
            data_classification="confidential",
            metadata={"regulatory_hooks": ["FINRA", "SEC", "CFTC"]},
        )

    # ===========================================================
    # Step 4: Prompt usage governance
    # ===========================================================
    print("\n=== Scenario 3: Prompt Usage ===")

    with tracer.start_as_current_span("chat.inference") as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.request.model", "gpt-4")

        prompt_content = "You are a helpful trading assistant. Follow all risk controls."
        event = instrumentor.prompt_used(
            prompt_name="prompt.trading-assistant-v3",
            prompt_version=3,
            content=prompt_content,
            data_classification="internal",
        )

    # ===========================================================
    # Step 5: Policy violation detection
    # ===========================================================
    print("\n=== Scenario 4: Policy Violation ===")

    with tracer.start_as_current_span("policy_check") as span:
        event = instrumentor.policy_violation(
            violation_type="DATA_CLASSIFICATION_BREACH",
            severity="critical",
            denial_reason="Restricted data (pre-release earnings) accessed outside approved window",
            data_classification="restricted",
            policy_name="policy.pre-release-earnings",
            policy_version=2,
            content="Q4 earnings: $2.3B revenue...",
            metadata={
                "regulatory_hooks": ["SEC", "FINRA"],
                "escalated_to": "compliance-team@finco.com",
                "auto_blocked": True,
            },
        )

    # ===========================================================
    # Step 6: Agent-to-agent call with Baggage propagation
    # ===========================================================
    print("\n=== Scenario 5: A2A Call with Baggage ===")

    with tracer.start_as_current_span("execute_tool.shipping_calc") as span:
        # Inject governance context into Baggage before calling another agent
        ctx = AIGPBaggage.inject(
            policy_name="policy.order-fulfillment",
            data_classification="internal",
            org_id="org.finco",
        )

        # The A2A call event
        event = instrumentor.a2a_call(
            request_method="A2A",
            request_path="/.well-known/agent.json",
            data_classification="internal",
            metadata={
                "target_agent": "agent.shipping-calculator",
                "a2a_method": "tasks/send",
            },
        )

        # Simulate receiving agent extracting baggage
        extracted = AIGPBaggage.extract(ctx)
        print(f"\n  Receiving agent extracted baggage: {extracted}")

    # ===========================================================
    # Step 7: tracestate vendor key
    # ===========================================================
    print("\n=== Scenario 6: tracestate Vendor Key ===")

    # Inject AIGP into tracestate alongside existing vendor entries
    tracestate = AIGPTraceState.inject_into_tracestate(
        existing_tracestate="dd=s:1,rojo=t61rcWkgMzE",
        data_classification="confidential",
        policy_name="policy.trading-limits",
        policy_version=4,
    )
    print(f"  tracestate: {tracestate}")

    # Extract on receiving side
    extracted = AIGPTraceState.extract_from_tracestate(tracestate)
    print(f"  Extracted AIGP context: {extracted}")

    # Reconstruct W3C traceparent from AIGP event
    print(f"\n  Reconstructed traceparent:")
    print(f"    00-{event['trace_id']}-{event['span_id']}-{event['trace_flags']}")

    # ===========================================================
    # Step 8: Merkle tree governance proof (multi-resource)
    # ===========================================================
    print("\n=== Scenario 7: Merkle Tree Governance Proof ===")

    with tracer.start_as_current_span("invoke_agent.customer_support") as span:
        span.set_attribute("gen_ai.operation.name", "invoke_agent")

        # Agent governed by 3 resources: 1 policy + 1 prompt + 1 tool
        # Each gets its own leaf hash; Merkle root becomes governance_hash
        event = instrumentor.multi_resource_governance_proof(
            resources=[
                ("policy", "policy.trading-limits",
                 "Maximum single position: $10M. Daily loss limit: $500K."),
                ("prompt", "prompt.trading-assistant-v3",
                 "You are a helpful trading assistant. Follow all risk controls."),
                ("tool", "tool.position-calculator",
                 '{"name": "position-calculator", "scope": "read"}'),
            ],
            data_classification="confidential",
            metadata={"regulatory_hooks": ["FINRA", "SEC"]},
        )

        print(f"\n  hash_type:       {event['hash_type']}")
        print(f"  governance_hash: {event['governance_hash'][:16]}... (Merkle root)")
        if "governance_merkle_tree" in event:
            tree = event["governance_merkle_tree"]
            print(f"  leaf_count:      {tree['leaf_count']}")
            for leaf in tree["leaves"]:
                print(f"    {leaf['resource_type']:8s} {leaf['resource_name']:40s} {leaf['hash'][:16]}...")

    # ===========================================================
    # Scenario 9: OpenLineage Triple-Emit with Context + Lineage Resources
    # ===========================================================
    print("\n--- Scenario 9: OpenLineage Triple-Emit with Context + Lineage ---")

    from aigp_otel.openlineage import build_openlineage_run_event
    from aigp_otel.events import compute_merkle_governance_hash

    # Pre-execution: snapshot upstream data lineage as a lineage resource
    lineage_snapshot = json.dumps({
        "datasets": ["orders", "customers", "credit-scores"],
        "snapshot_time": "2026-02-15T14:00:00Z",
        "source": "openlineage.finco.data-warehouse",
    })

    # Pre-execution: capture environment config as a context resource
    env_config = json.dumps({
        "env": "production",
        "region": "us-east-1",
        "model": "gpt-4",
    })

    resources = [
        ("policy", "policy.fair-lending", "Maximum debt-to-income ratio: 43%..."),
        ("prompt", "prompt.scoring-v3", "You are a credit scoring assistant..."),
        ("context", "context.env-config", env_config),
        ("lineage", "lineage.upstream-orders", lineage_snapshot),
    ]

    root_hash, merkle_tree = compute_merkle_governance_hash(resources)

    # Create the AIGP event
    from aigp_otel.events import create_aigp_event
    aigp_event = create_aigp_event(
        event_type="GOVERNANCE_PROOF",
        event_category="governance-proof",
        agent_id="agent.credit-scorer-v2",
        trace_id="abc123def456abc123def456abc12345",
        governance_hash=root_hash,
        hash_type="merkle-sha256" if merkle_tree else "sha256",
        governance_merkle_tree=merkle_tree,
        data_classification="confidential",
    )

    # Build OpenLineage RunEvent with AIGP facets
    ol_event = build_openlineage_run_event(
        aigp_event,
        job_namespace="finco.scoring",
        job_name="credit-scorer-v2.invoke",
    )

    print(f"\n  OpenLineage RunEvent:")
    print(f"    eventType: {ol_event['eventType']}")
    print(f"    runId:     {ol_event['run']['runId']}")
    print(f"    job:       {ol_event['job']['namespace']}/{ol_event['job']['name']}")
    governance = ol_event["run"]["facets"]["aigp_governance"]
    print(f"    governance hash: {governance['governanceHash'][:16]}... (Merkle root)")
    print(f"    leaf count:      {governance['leafCount']}")
    print(f"    enforcement:     {governance.get('enforcementResult', 'N/A')}")
    print(f"    inputs ({len(ol_event['inputs'])}):")
    for inp in ol_event["inputs"]:
        rf = inp["inputFacets"]["aigp_resource"]
        print(f"      {rf['resourceType']:8s} {rf['resourceName']}")

    # ===========================================================
    # Done
    # ===========================================================
    print("\n=== All scenarios complete ===")
    print("AIGP events went to: compliance_store_callback (simulated Kafka)")
    print("OTel spans went to: ConsoleSpanExporter (simulated observability backend)")
    print("OpenLineage events built for: Marquez/DataHub (simulated lineage backend)")
    print("\nSame data. Three destinations. Three purposes.")

    provider.shutdown()


if __name__ == "__main__":
    main()
