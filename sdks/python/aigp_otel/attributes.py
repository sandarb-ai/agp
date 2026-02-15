"""
AIGP Semantic Attributes for OpenTelemetry
==========================================

Defines the `aigp.*` namespace attributes as constants, organized by
their OTel signal type (Resource vs Span vs Span Event).

These follow OTel naming conventions:
- Lowercase, dot-separated namespace hierarchy
- Domain-first approach: aigp.{component}.{property}
"""


class AIGPAttributes:
    """Constants for AIGP semantic attributes in the aigp.* namespace."""

    # -------------------------------------------------------
    # Resource Attributes (constant per agent process)
    # -------------------------------------------------------
    AGENT_ID = "aigp.agent.id"
    AGENT_NAME = "aigp.agent.name"
    ORG_ID = "aigp.org.id"
    ORG_NAME = "aigp.org.name"

    # -------------------------------------------------------
    # Span Attributes: Core Governance
    # -------------------------------------------------------
    EVENT_ID = "aigp.event.id"
    EVENT_TYPE = "aigp.event.type"
    EVENT_CATEGORY = "aigp.event.category"
    GOVERNANCE_HASH = "aigp.governance.hash"
    GOVERNANCE_HASH_TYPE = "aigp.governance.hash_type"
    DATA_CLASSIFICATION = "aigp.data.classification"
    ENFORCEMENT_RESULT = "aigp.enforcement.result"

    # -------------------------------------------------------
    # Span Attributes: Policy (singular — one policy per span)
    # -------------------------------------------------------
    POLICY_NAME = "aigp.policy.name"
    POLICY_VERSION = "aigp.policy.version"
    POLICY_ID = "aigp.policy.id"

    # -------------------------------------------------------
    # Span Attributes: Prompt (singular — one prompt per span)
    # -------------------------------------------------------
    PROMPT_NAME = "aigp.prompt.name"
    PROMPT_VERSION = "aigp.prompt.version"
    PROMPT_ID = "aigp.prompt.id"

    # -------------------------------------------------------
    # Span Attributes: Multi-Policy / Multi-Prompt / Multi-Tool
    # Array-valued attributes for operations involving multiple
    # governed resources simultaneously.
    # -------------------------------------------------------
    POLICIES_NAMES = "aigp.policies.names"
    POLICIES_VERSIONS = "aigp.policies.versions"
    PROMPTS_NAMES = "aigp.prompts.names"
    PROMPTS_VERSIONS = "aigp.prompts.versions"
    TOOLS_NAMES = "aigp.tools.names"
    CONTEXTS_NAMES = "aigp.contexts.names"
    LINEAGES_NAMES = "aigp.lineages.names"

    # -------------------------------------------------------
    # Span Attributes: Merkle Tree Governance
    # -------------------------------------------------------
    MERKLE_LEAF_COUNT = "aigp.governance.merkle.leaf_count"

    # -------------------------------------------------------
    # Span Attributes: Denial and Violation
    # -------------------------------------------------------
    SEVERITY = "aigp.severity"
    VIOLATION_TYPE = "aigp.violation.type"
    DENIAL_REASON = "aigp.denial.reason"

    # -------------------------------------------------------
    # Span Event Names
    # -------------------------------------------------------
    EVENT_INJECT_SUCCESS = "aigp.inject.success"
    EVENT_INJECT_DENIED = "aigp.inject.denied"
    EVENT_PROMPT_USED = "aigp.prompt.used"
    EVENT_PROMPT_DENIED = "aigp.prompt.denied"
    EVENT_POLICY_VIOLATION = "aigp.policy.violation"
    EVENT_GOVERNANCE_PROOF = "aigp.governance.proof"
    EVENT_A2A_CALL = "aigp.a2a.call"

    # -------------------------------------------------------
    # Enforcement result values
    # -------------------------------------------------------
    ENFORCEMENT_ALLOWED = "allowed"
    ENFORCEMENT_DENIED = "denied"

    # -------------------------------------------------------
    # Data classification values
    # -------------------------------------------------------
    CLASSIFICATION_PUBLIC = "public"
    CLASSIFICATION_INTERNAL = "internal"
    CLASSIFICATION_CONFIDENTIAL = "confidential"
    CLASSIFICATION_RESTRICTED = "restricted"

    # -------------------------------------------------------
    # Classification abbreviations for tracestate
    # -------------------------------------------------------
    CLASSIFICATION_ABBREV = {
        "public": "pub",
        "internal": "int",
        "confidential": "con",
        "restricted": "res",
    }
