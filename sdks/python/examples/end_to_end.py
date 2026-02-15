"""
AIGP End-to-End Example — Triple-Emit Architecture
====================================================

This example demonstrates the complete AIGP (AI Governance Protocol) integration
with OpenTelemetry and OpenLineage. It shows how a single AI agent invocation
produces three complementary records:

    AI Agent Invocation
        |
        +--> AIGP Event (JSON) --> AI Governance Store
        |    Full Merkle tree, all leaf hashes, cryptographic proof
        |
        +--> OTel Span Event --> Observability Backend
        |    governance_hash, leaf_count, trace context, latency
        |
        +--> OpenLineage RunEvent --> Lineage Backend
             Governance summary + resources as InputDatasets

Same data. Three destinations. Three purposes.

Three Layers, One trace_id
--------------------------

    | Layer            | Standard    | What It Shows                                      |
    |------------------|-------------|----------------------------------------------------|
    | AI Governance    | AIGP        | Cryptographic proof, enforcement, audit trail       |
    | Observability    | OTel        | Agent latency, errors, trace topology               |
    | Lineage          | OpenLineage | What data flowed where, governed by what             |

Five Governed Resource Types
----------------------------

AIGP governs five resource types, each with domain-separated hashing:

    | Type      | Prefix    | Semantics           | Who Defines It |
    |-----------|-----------|---------------------|----------------|
    | policy    | policy.   | Governance rules    | AIGP           |
    | prompt    | prompt.   | System prompts      | AIGP           |
    | tool      | tool.     | Tool definitions    | AIGP           |
    | context   | context.  | Pre-exec context    | Agent-defined  |
    | lineage   | lineage.  | Data lineage        | AIGP-defined   |

    "context" — General-purpose, agent-defined. AIGP does not prescribe what goes
    inside. Each AI agent or framework determines its semantics (env config,
    runtime params, session state, etc.). AIGP hashes it; the agent owns the meaning.

    "lineage" — AIGP-defined, specific meaning. Data lineage snapshots: upstream
    dataset provenance, DAG state, OpenLineage graph context. Used for bidirectional
    sync between AIGP governance proof and OpenLineage data lineage.

Scenarios
---------

This example walks through 9 scenarios, each building on the previous:

    1. OTel tracer initialization with AIGP Resource attributes (agent identity)
    2. Single policy injection — SHA-256 hash, dual-emit (AIGP event + OTel span)
    3. Multi-policy injection — array-valued OTel attributes
    4. Prompt usage governance — governed prompt with classification
    5. Policy violation detection — denial with severity and escalation
    6. Agent-to-agent (A2A) call — W3C Baggage propagation of governance context
    7. tracestate vendor key — lightweight governance signaling via W3C tracestate
    8. Merkle tree governance proof — multi-resource cryptographic verification
    9. OpenLineage triple-emit — full three-layer integration with all 5 resource types

Run
---

    pip install opentelemetry-api opentelemetry-sdk
    cd sdks/python
    PYTHONPATH=. python examples/end_to_end.py

Architecture Notes
------------------

- The AIGPInstrumentor is the main entry point. It wraps OTel span operations
  and emits AIGP events via the event_callback.

- Every AIGP event includes a governance_hash (SHA-256 of the governed content).
  For single resources, this is a flat hash. For multiple resources, it's a
  Merkle root computed from domain-separated leaf hashes.

- Domain separation ensures that identical content in different resource types
  produces different hashes:
      SHA-256("policy:policy.trading-limits:" + content) !=
      SHA-256("prompt:policy.trading-limits:" + content)

- The Merkle tree uses odd-promotion (not duplication) for odd leaf counts,
  keeping the proof compact and unambiguous.

- OpenLineage integration is zero-dependency: the builder produces plain Python
  dicts compatible with the OpenLineage spec. No openlineage-python needed.

- trace_id is the universal correlation key across all three systems.
  In OTel it's the span trace_id, in OpenLineage it's the runId, in AIGP
  it's the trace_id field. One query joins all three views.
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
    Simulates sending AIGP events to a compliance store.

    In production, replace this with your actual event pipeline:
    - Message bus for real-time streaming to compliance dashboards
    - OLAP store for long-term audit storage
    - Object store for immutable governance evidence (the AIGP SKOC pipeline)

    Every AIGP event contains:
    - event_type: What happened (INJECT_SUCCESS, PROMPT_USED, POLICY_VIOLATION, etc.)
    - trace_id / span_id: W3C trace context for correlation with OTel and OpenLineage
    - governance_hash: SHA-256 or Merkle root — the cryptographic proof
    - data_classification: public / internal / confidential / restricted
    - metadata: Regulatory hooks, resource lists, OTel attributes
    """
    print(f"\n--- AIGP Event -> Compliance Store ---")
    print(f"  event_type:      {aigp_event['event_type']}")
    print(f"  trace_id:        {aigp_event['trace_id']}")
    print(f"  span_id:         {aigp_event['span_id']}")
    print(f"  governance_hash: {aigp_event['governance_hash'][:16]}...")
    print(f"  policy_name:     {aigp_event.get('policy_name', 'N/A')}")
    print(f"  classification:  {aigp_event.get('data_classification', 'N/A')}")
    print(f"--------------------------------------")


def main():
    # =====================================================================
    # Scenario 1: Initialize OTel with AIGP Resource Attributes
    # =====================================================================
    #
    # The AIGPInstrumentor is initialized once per agent. It provides:
    #   - get_resource_attributes(): AIGP identity attributes for the OTel Resource
    #   - inject_success(), prompt_used(), etc.: Governance event emitters
    #   - event_callback: Where AIGP events are sent (message bus, DB, object store, etc.)
    #
    # AIGP Resource attributes (aigp.agent.id, aigp.org.id, etc.) travel with
    # EVERY OTel span automatically — no per-span injection needed. This means
    # any OTel-compatible observability backend can filter and group
    # spans by agent identity without any custom instrumentation.
    #
    instrumentor = AIGPInstrumentor(
        agent_id="agent.trading-bot-v2",       # AGRN-format agent identifier
        agent_name="Trading Bot",               # Human-readable display name
        org_id="org.finco",                     # Organization that owns this agent
        org_name="FinCo",                       # Organization display name
        event_callback=compliance_store_callback,  # Where AIGP events go
    )

    # Merge AIGP resource attributes with standard OTel service attributes.
    # The resulting Resource object is attached to the TracerProvider, so every
    # span created by this tracer carries both OTel service identity AND AIGP
    # agent identity.
    #
    # AIGP adds these resource attributes:
    #   aigp.agent.id    = "agent.trading-bot-v2"
    #   aigp.agent.name  = "Trading Bot"
    #   aigp.org.id      = "org.finco"
    #   aigp.org.name    = "FinCo"
    #
    resource = Resource.create({
        **instrumentor.get_resource_attributes(),
        "service.name": "trading-bot-v2",
        "service.version": "2.4.1",
        "deployment.environment": "production",
    })

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)

    tracer = trace.get_tracer("aigp.example", "0.5.0")

    # =====================================================================
    # Scenario 2: Single Policy Injection
    # =====================================================================
    #
    # The most basic governance operation: a policy is injected into an agent's
    # context window. AIGP records:
    #
    #   1. AIGP event (JSON) → compliance store
    #      - governance_hash = SHA-256(policy_content)
    #      - Full audit trail: who, what, when, which policy, what version
    #
    #   2. OTel span event → observability backend
    #      - "aigp.governance" event attached to the current span
    #      - Attributes: aigp.governance.hash, aigp.policies.names, etc.
    #
    # This is the "dual-emit" pattern. The same governance action produces
    # both an immutable audit record AND operational observability data.
    #
    print("\n=== Scenario 2: Single Policy Injection ===")

    with tracer.start_as_current_span("invoke_agent.trading_bot") as span:
        # OTel GenAI semantic conventions — these are standard OTel attributes
        # for AI/ML operations (see: OTel GenAI semantic conventions).
        span.set_attribute("gen_ai.operation.name", "invoke_agent")
        span.set_attribute("gen_ai.system", "custom")

        # inject_success() does three things atomically:
        #   1. Computes SHA-256 hash of the policy content
        #   2. Emits an AIGP event via event_callback (→ compliance store)
        #   3. Attaches an OTel span event with governance attributes
        policy_content = "You are a trading assistant. Maximum single position: $10M. Daily loss limit: $500K."
        event = instrumentor.inject_success(
            policy_name="policy.trading-limits",   # AGRN-format policy name
            policy_version=4,                       # Version at time of injection
            content=policy_content,                 # The actual policy text (hashed)
            data_classification="confidential",     # Data classification level
            template_rendered=True,                 # Was the policy template-rendered?
            request_method="GET",                   # HTTP method used to fetch policy
            request_path="/api/policies/trading-limits/content",
            metadata={"regulatory_hooks": ["FINRA", "SEC"]},  # Compliance metadata
        )

    # =====================================================================
    # Scenario 3: Multi-Policy Injection
    # =====================================================================
    #
    # In regulated environments, an agent is often governed by MULTIPLE
    # policies simultaneously. For example, a trading bot might need both
    # position limits AND risk controls injected at the same time.
    #
    # AIGP records this as a single event with array-valued OTel attributes:
    #   aigp.policies.names = ["policy.trading-limits", "policy.risk-controls"]
    #
    # This is important for observability: you can query your backend for
    # "all spans where policy.risk-controls was active" and get precise results.
    #
    print("\n=== Scenario 3: Multi-Policy Injection ===")

    with tracer.start_as_current_span("invoke_agent.trading_bot.multi") as span:
        span.set_attribute("gen_ai.operation.name", "invoke_agent")

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

    # =====================================================================
    # Scenario 4: Prompt Usage Governance
    # =====================================================================
    #
    # Prompts are governed resources, just like policies. When a system prompt
    # is used in an LLM call, AIGP records which prompt, which version, and
    # computes the governance hash.
    #
    # This creates an audit trail for prompt management:
    #   - Which prompt was active when the model produced output X?
    #   - Has the prompt changed since the last compliance review?
    #   - Which agents are using prompt version 3 vs version 4?
    #
    print("\n=== Scenario 4: Prompt Usage ===")

    with tracer.start_as_current_span("chat.inference") as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.request.model", "gpt-4")

        prompt_content = "You are a helpful trading assistant. Follow all risk controls."
        event = instrumentor.prompt_used(
            prompt_name="prompt.trading-assistant-v3",
            prompt_version=3,
            content=prompt_content,
            data_classification="internal",   # Lower classification than policy
        )

    # =====================================================================
    # Scenario 5: Policy Violation Detection
    # =====================================================================
    #
    # When an agent violates a policy (e.g., accesses restricted data outside
    # an approved window), AIGP records the violation with:
    #   - violation_type: Category of violation (DATA_CLASSIFICATION_BREACH, etc.)
    #   - severity: critical / high / medium / low
    #   - denial_reason: Human-readable explanation
    #
    # The OTel span is marked with an error status, making violations visible
    # in observability dashboards and alerting systems.
    #
    # The AIGP event goes to the compliance store with full context for
    # regulatory reporting and incident investigation.
    #
    print("\n=== Scenario 5: Policy Violation ===")

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

    # =====================================================================
    # Scenario 6: Agent-to-Agent (A2A) Call with Baggage Propagation
    # =====================================================================
    #
    # When one agent calls another (A2A), governance context must propagate.
    # AIGP uses W3C Baggage (RFC 8941) to carry governance metadata across
    # service boundaries:
    #
    #   Calling Agent                    Receiving Agent
    #   ┌─────────────┐                 ┌─────────────┐
    #   │ trading-bot  │ ── HTTP ──────> │ shipping-calc│
    #   │              │   + Baggage:    │              │
    #   │              │   aigp.policy=  │ Extracts     │
    #   │              │   order-fulfill │ baggage,     │
    #   │              │   aigp.class=   │ knows it's   │
    #   │              │   internal      │ governed     │
    #   └─────────────┘                 └─────────────┘
    #
    # The receiving agent knows: which policy governs this interaction,
    # what data classification applies, and which org initiated the call.
    # This enables cross-agent governance without tight coupling.
    #
    print("\n=== Scenario 6: A2A Call with Baggage ===")

    with tracer.start_as_current_span("execute_tool.shipping_calc") as span:
        # Inject governance context into W3C Baggage
        ctx = AIGPBaggage.inject(
            policy_name="policy.order-fulfillment",
            data_classification="internal",
            org_id="org.finco",
        )

        # Record the A2A call in the AIGP audit trail
        event = instrumentor.a2a_call(
            request_method="A2A",
            request_path="/.well-known/agent.json",  # Google A2A discovery endpoint
            data_classification="internal",
            metadata={
                "target_agent": "agent.shipping-calculator",
                "a2a_method": "tasks/send",
            },
        )

        # Simulate the receiving agent extracting governance baggage
        extracted = AIGPBaggage.extract(ctx)
        print(f"\n  Receiving agent extracted baggage: {extracted}")

    # =====================================================================
    # Scenario 7: tracestate Vendor Key
    # =====================================================================
    #
    # W3C tracestate allows multiple vendors to attach metadata to a trace.
    # AIGP injects a vendor key ("aigp=...") alongside existing entries
    # (e.g., other vendor entries like "dd=s:1", "rojo=t61rcWkgMzE").
    #
    # This provides lightweight governance signaling without Baggage overhead:
    #   tracestate: aigp=dc~confidential;pn~policy.trading-limits;pv~4,dd=s:1,rojo=t61rcWkgMzE
    #
    # Any system that understands tracestate can see AIGP governance context
    # at a glance, without parsing AIGP events or querying the audit trail.
    #
    # Together with traceparent (trace_id + span_id + trace_flags), this gives
    # full W3C Trace Context compatibility.
    #
    print("\n=== Scenario 7: tracestate Vendor Key ===")

    tracestate = AIGPTraceState.inject_into_tracestate(
        existing_tracestate="dd=s:1,rojo=t61rcWkgMzE",
        data_classification="confidential",
        policy_name="policy.trading-limits",
        policy_version=4,
    )
    print(f"  tracestate: {tracestate}")

    # The receiving side extracts AIGP context from tracestate
    extracted = AIGPTraceState.extract_from_tracestate(tracestate)
    print(f"  Extracted AIGP context: {extracted}")

    # Reconstruct W3C traceparent from the AIGP event fields
    # Format: version-trace_id-span_id-trace_flags
    print(f"\n  Reconstructed traceparent:")
    print(f"    00-{event['trace_id']}-{event['span_id']}-{event['trace_flags']}")

    # =====================================================================
    # Scenario 8: Merkle Tree Governance Proof
    # =====================================================================
    #
    # When an agent is governed by MULTIPLE resources (policies + prompts +
    # tools), a flat SHA-256 hash of concatenated content is fragile and
    # doesn't support selective verification.
    #
    # AIGP uses a Merkle tree instead:
    #
    #                    governance_hash (Merkle root)
    #                   /                             \
    #              H(0,1)                           H(2) ← odd-promoted
    #             /      \                            |
    #     leaf[0]         leaf[1]                  leaf[2]
    #     policy.         prompt.                  tool.
    #     trading-limits  trading-assistant-v3     position-calculator
    #
    # Each leaf hash is domain-separated:
    #   leaf[0] = SHA-256("policy:policy.trading-limits:" + content)
    #   leaf[1] = SHA-256("prompt:prompt.trading-assistant-v3:" + content)
    #   leaf[2] = SHA-256("tool:tool.position-calculator:" + content)
    #
    # Domain separation ensures that identical content in different resource
    # types produces different hashes — preventing type confusion attacks.
    #
    # Odd-promotion (not duplication) is used for odd leaf counts: the unpaired
    # leaf is promoted to the next level without hashing with itself. This keeps
    # the tree compact and unambiguous (no duplicate leaves).
    #
    # The Merkle root becomes the governance_hash in both AIGP events and
    # OTel span events. Individual leaf hashes enable selective verification:
    # "prove that policy.trading-limits was part of this governance session"
    # without revealing the prompt or tool content.
    #
    print("\n=== Scenario 8: Merkle Tree Governance Proof ===")

    with tracer.start_as_current_span("invoke_agent.customer_support") as span:
        span.set_attribute("gen_ai.operation.name", "invoke_agent")

        # Three resources: 1 policy + 1 prompt + 1 tool
        # Each gets a domain-separated leaf hash; Merkle root = governance_hash
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

        # Display the Merkle tree structure
        print(f"\n  hash_type:       {event['hash_type']}")
        print(f"  governance_hash: {event['governance_hash'][:16]}... (Merkle root)")
        if "governance_merkle_tree" in event:
            tree = event["governance_merkle_tree"]
            print(f"  leaf_count:      {tree['leaf_count']}")
            for leaf in tree["leaves"]:
                print(f"    {leaf['resource_type']:8s} {leaf['resource_name']:40s} {leaf['hash'][:16]}...")

    # =====================================================================
    # Scenario 9: OpenLineage Triple-Emit with Context + Lineage
    # =====================================================================
    #
    # This is the crown jewel: the full three-layer integration.
    #
    # A single agent invocation produces THREE records, all correlated by
    # the same trace_id:
    #
    #   1. AIGP event → AI Governance Store
    #      Full Merkle tree, all leaf hashes, complete cryptographic proof
    #
    #   2. OTel span → Observability Backend
    #      governance_hash, leaf_count, agent identity, latency, errors
    #
    #   3. OpenLineage RunEvent → Lineage Backend
    #      Governance summary as run facet + resources as InputDatasets
    #
    # OpenLineage integration is BIDIRECTIONAL:
    #
    #   AIGP → OpenLineage:
    #     Governance proof rides on OpenLineage RunEvents as custom facets.
    #     Lineage backends see what governed each data pipeline job.
    #
    #   OpenLineage → AIGP:
    #     Pre-execution lineage snapshots are hashed as "lineage" Merkle leaves.
    #     If upstream data changes after the snapshot, the governance hash
    #     won't match — the proof covers data provenance, not just code.
    #
    # The five resource types in this scenario:
    #
    #   "policy"  — Governance rules (AIGP-defined, normative)
    #              Example: "Maximum debt-to-income ratio: 43%"
    #
    #   "prompt"  — System prompts (AIGP-defined, normative)
    #              Example: "You are a credit scoring assistant..."
    #
    #   "context" — Agent-defined, general-purpose pre-execution context.
    #              AIGP does NOT prescribe what goes inside. Each AI agent
    #              or framework determines its own semantics: env config,
    #              runtime params, session state, feature flags, etc.
    #              AIGP hashes the content; the agent owns the meaning.
    #              Example: {"env": "production", "region": "us-east-1"}
    #
    #   "lineage" — AIGP-defined, specific meaning. Data lineage snapshots
    #              capturing upstream dataset provenance, DAG state, or
    #              OpenLineage graph context. Used for bidirectional sync
    #              between AIGP governance proof and OpenLineage data lineage.
    #              Example: {"datasets": ["orders", "customers"], "source": "..."}
    #
    # Note: "tool" is the fifth resource type (not used in this scenario).
    #
    print("\n=== Scenario 9: OpenLineage Triple-Emit with Context + Lineage ===")

    from aigp_otel.openlineage import build_openlineage_run_event
    from aigp_otel.events import compute_merkle_governance_hash

    # ---- Pre-execution: Snapshot upstream data lineage ----
    #
    # Before the agent runs, query the OpenLineage lineage graph for upstream
    # data provenance. Serialize the result as JSON and hash it as a "lineage"
    # Merkle leaf. If the upstream data changes after this snapshot, the
    # governance hash won't match — providing tamper evidence for data lineage.
    #
    lineage_snapshot = json.dumps({
        "datasets": ["orders", "customers", "credit-scores"],
        "snapshot_time": "2026-02-15T14:00:00Z",
        "source": "openlineage.finco.data-warehouse",
    })

    # ---- Pre-execution: Capture environment config as context ----
    #
    # "context" is agent-defined — AIGP doesn't prescribe what goes inside.
    # This agent captures runtime environment config. Another agent might
    # capture session state, feature flags, or model parameters. AIGP hashes
    # whatever the agent provides; the agent owns the semantics.
    #
    env_config = json.dumps({
        "env": "production",
        "region": "us-east-1",
        "model": "gpt-4",
    })

    # ---- Build the Merkle tree from all governed resources ----
    #
    # Four resources, four leaf hashes, one Merkle root:
    #
    #                    governance_hash (root)
    #                   /                     \
    #              H(0,1)                   H(2,3)
    #             /      \                 /      \
    #     leaf[0]        leaf[1]    leaf[2]       leaf[3]
    #     policy.        prompt.    context.      lineage.
    #     fair-lending   scoring-v3 env-config    upstream-orders
    #
    # Leaf hash construction (domain-separated):
    #   leaf[0] = SHA-256("policy:policy.fair-lending:" + content)
    #   leaf[1] = SHA-256("prompt:prompt.scoring-v3:" + content)
    #   leaf[2] = SHA-256("context:context.env-config:" + env_config_json)
    #   leaf[3] = SHA-256("lineage:lineage.upstream-orders:" + lineage_json)
    #
    resources = [
        ("policy", "policy.fair-lending", "Maximum debt-to-income ratio: 43%..."),
        ("prompt", "prompt.scoring-v3", "You are a credit scoring assistant..."),
        ("context", "context.env-config", env_config),
        ("lineage", "lineage.upstream-orders", lineage_snapshot),
    ]

    root_hash, merkle_tree = compute_merkle_governance_hash(resources)

    # ---- Create the AIGP event (Layer 1: AI Governance) ----
    #
    # This is the canonical governance record. It contains the full Merkle tree,
    # all leaf hashes, and all metadata needed for regulatory compliance.
    #
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

    # ---- Build OpenLineage RunEvent (Layer 3: Lineage) ----
    #
    # The OpenLineage builder transforms an AIGP event into an OpenLineage-
    # compatible RunEvent with two custom facets:
    #
    #   run.facets.aigp_governance (AIGPGovernanceRunFacet):
    #     - governanceHash, hashType, leafCount, agentId, traceId
    #     - Summary: "this run was governed, here's the proof"
    #
    #   inputs[].inputFacets.aigp_resource (AIGPResourceInputFacet):
    #     - resourceType, resourceName, leafHash
    #     - Detail: "each governed resource as an InputDataset"
    #
    # OpenLineage-compatible lineage backends render governed resources
    # as standard datasets in the lineage graph. The aigp_resource facet
    # provides AIGP-specific metadata for governance-aware UIs.
    #
    # Zero dependency: build_openlineage_run_event() produces plain Python dicts.
    # No openlineage-python library required.
    #
    ol_event = build_openlineage_run_event(
        aigp_event,
        job_namespace="finco.scoring",          # OpenLineage job namespace
        job_name="credit-scorer-v2.invoke",     # OpenLineage job name
    )

    # ---- Display the OpenLineage RunEvent ----
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

    # ---- Correlation: trace_id as the universal key ----
    #
    # The same trace_id appears in all three records:
    #
    #   | System              | Location                                |
    #   |---------------------|-----------------------------------------|
    #   | AIGP event          | trace_id field                          |
    #   | OTel span           | trace_id in span context                |
    #   | OpenLineage RunEvent| run.facets.aigp_governance.traceId      |
    #
    # One query joins all three views:
    #   SELECT * FROM aigp_events WHERE trace_id = 'abc123...';       -- governance
    #   -- Query observability backend by trace_id                     -- observability
    #   -- Query lineage backend by run facet traceId                 -- lineage
    #

    # =====================================================================
    # Done
    # =====================================================================
    print("\n=== All scenarios complete ===")
    print("AIGP events went to: compliance_store_callback (simulated AI governance store)")
    print("OTel spans went to:  ConsoleSpanExporter (simulated observability backend)")
    print("OpenLineage events:  built for any OpenLineage-compatible lineage backend")
    print("\nThree layers, one trace_id:")
    print("  AI Governance (AIGP)   — cryptographic proof, enforcement, audit trail")
    print("  Observability (OTel)   — agent latency, errors, trace topology")
    print("  Lineage (OpenLineage)  — what data flowed where, governed by what")
    print("\nFive governed resource types:")
    print("  policy   — governance rules          (AIGP-defined)")
    print("  prompt   — system prompts             (AIGP-defined)")
    print("  tool     — tool definitions           (AIGP-defined)")
    print("  context  — pre-execution context      (agent-defined, meaning owned by agent)")
    print("  lineage  — data lineage snapshots     (AIGP-defined, for OpenLineage sync)")

    provider.shutdown()


if __name__ == "__main__":
    main()
