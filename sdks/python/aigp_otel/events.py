"""
AIGP Event Creation
===================

Functions for creating AIGP-compliant governance events with
OpenTelemetry correlation fields (span_id, parent_span_id, trace_flags).
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Optional


def compute_governance_hash(
    content: str, algorithm: str = "sha256"
) -> str:
    """
    Compute the governance hash per AIGP spec Section 8.

    - Input: UTF-8 encoded byte representation (no normalization).
    - Output: Lowercase hexadecimal string.
    - SHA-256 produces exactly 64 characters.

    Args:
        content: The governed content to hash.
        algorithm: Hash algorithm ("sha256", "sha384", "sha512").

    Returns:
        Lowercase hexadecimal hash string.
    """
    if algorithm == "sha256":
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    elif algorithm == "sha384":
        return hashlib.sha384(content.encode("utf-8")).hexdigest()
    elif algorithm == "sha512":
        return hashlib.sha512(content.encode("utf-8")).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def compute_leaf_hash(
    resource_type: str,
    resource_name: str,
    content: str,
) -> str:
    """
    Compute a Merkle leaf hash for a single governed resource.

    Leaf = SHA-256(resource_type + ":" + resource_name + ":" + content)

    The domain separator (resource_type:resource_name:) prevents
    cross-resource collisions: a policy and a prompt with identical
    content produce different leaf hashes.

    Args:
        resource_type: One of "policy", "prompt", "tool", "context", "lineage".
        resource_name: AGRN-format name (e.g., "policy.trading-limits").
        content: The governed content string.

    Returns:
        Lowercase hexadecimal hash string (64 chars, SHA-256).
    """
    if resource_type not in ("policy", "prompt", "tool", "context", "lineage"):
        raise ValueError(
            f"Invalid resource_type: {resource_type}. "
            "Must be 'policy', 'prompt', 'tool', 'context', or 'lineage'."
        )
    prefixed = f"{resource_type}:{resource_name}:{content}"
    return hashlib.sha256(prefixed.encode("utf-8")).hexdigest()


def _compute_merkle_root(sorted_hashes: list[str]) -> str:
    """
    Compute Merkle root from a list of sorted leaf hashes.

    Algorithm (AIGP Spec Section 8.8.3):
    - Pair hashes left-to-right: parent = SHA-256(left + right)
    - If odd number, last hash is promoted (not duplicated)
    - Repeat until one root remains.

    The promotion rule (vs. Bitcoin-style duplication) avoids the
    second-preimage vulnerability where a tree with N leaves could
    have the same root as a tree with N+1 identical-last leaves.

    Args:
        sorted_hashes: Leaf hashes in lexicographic ascending order.

    Returns:
        The Merkle root hash (64-char lowercase hex).
    """
    if len(sorted_hashes) == 0:
        raise ValueError("Cannot compute Merkle root of empty list")
    if len(sorted_hashes) == 1:
        return sorted_hashes[0]

    level = list(sorted_hashes)
    while len(level) > 1:
        next_level: list[str] = []
        i = 0
        while i < len(level) - 1:
            combined = level[i] + level[i + 1]
            parent = hashlib.sha256(combined.encode("utf-8")).hexdigest()
            next_level.append(parent)
            i += 2
        if i == len(level) - 1:
            # Odd node: promote without duplication
            next_level.append(level[i])
        level = next_level
    return level[0]


def compute_merkle_governance_hash(
    resources: list[tuple[str, str, str]],
) -> tuple[str, dict | None]:
    """
    Compute Merkle tree governance hash for multiple governed resources.

    If only one resource is provided, returns a flat SHA-256 hash
    (backward compatible with v0.3.0 — no Merkle tree structure).

    If multiple resources are provided, computes a Merkle tree where
    each resource gets its own leaf hash, and the root becomes the
    governance_hash.

    Args:
        resources: List of (resource_type, resource_name, content) tuples.
            resource_type: "policy", "prompt", or "tool"
            resource_name: AGRN name (e.g., "policy.trading-limits")
            content: The governed content string

    Returns:
        Tuple of (root_hash, merkle_tree_dict):
        - root_hash: The governance_hash value (64-char hex).
        - merkle_tree_dict: The governance_merkle_tree object, or None
          if only one resource (single resource uses flat hash).
    """
    if not resources:
        raise ValueError("At least one resource is required")

    if len(resources) == 1:
        # Single resource: flat hash over content only (backward compatible)
        _rtype, _rname, content = resources[0]
        flat_hash = compute_governance_hash(content)
        return flat_hash, None

    # Multiple resources: compute Merkle tree
    leaves = []
    for resource_type, resource_name, content in resources:
        leaf_hash = compute_leaf_hash(resource_type, resource_name, content)
        leaves.append({
            "resource_type": resource_type,
            "resource_name": resource_name,
            "hash": leaf_hash,
        })

    # Sort leaves by hash (lexicographic ascending) for deterministic tree
    leaves.sort(key=lambda leaf: leaf["hash"])
    sorted_hashes = [leaf["hash"] for leaf in leaves]

    root = _compute_merkle_root(sorted_hashes)

    merkle_tree = {
        "algorithm": "sha256",
        "leaf_count": len(leaves),
        "leaves": leaves,
    }

    return root, merkle_tree


def create_aigp_event(
    event_type: str,
    event_category: str,
    agent_id: str,
    trace_id: str,
    governance_hash: str = "",
    # OTel correlation fields
    span_id: str = "",
    parent_span_id: str = "",
    trace_flags: str = "",
    # Agent/Org fields
    agent_name: str = "",
    org_id: str = "",
    org_name: str = "",
    # Policy fields
    policy_id: str = "",
    policy_name: str = "",
    policy_version: int = 0,
    # Prompt fields
    prompt_id: str = "",
    prompt_name: str = "",
    prompt_version: int = 0,
    # Governance fields
    hash_type: str = "sha256",
    data_classification: str = "",
    template_rendered: bool = False,
    # Denial fields
    denial_reason: str = "",
    violation_type: str = "",
    severity: str = "",
    # Request fields
    source_ip: str = "",
    request_method: str = "",
    request_path: str = "",
    # Extension
    metadata: Optional[dict[str, Any]] = None,
    # Merkle tree (Section 8.8)
    governance_merkle_tree: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Create an AIGP event conforming to the v0.3.0 schema.

    This function creates the standalone AIGP JSON event (the governance
    record). For the OTel span event (the observability record), use
    AIGPInstrumentor which handles dual-emit.

    Args:
        event_type: AIGP event type (e.g., "INJECT_SUCCESS").
        event_category: Event category (e.g., "inject").
        agent_id: AGRN agent identifier (e.g., "agent.trading-bot-v2").
        trace_id: Distributed trace ID (prefer 32-char hex for OTel).
        governance_hash: SHA-256 hash of governed content.
        span_id: OTel span ID (16-char hex). Optional.
        parent_span_id: OTel parent span ID (16-char hex). Optional.
        trace_flags: W3C trace flags (2-char hex). Optional.
        ... (remaining fields per AIGP spec)

    Returns:
        Dict conforming to AIGP event schema v0.3.0.
    """
    now = datetime.now(timezone.utc)

    event = {
        # Required fields (Section 5.1)
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "event_category": event_category,
        "event_time": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z",
        "agent_id": agent_id,
        "governance_hash": governance_hash,
        "trace_id": trace_id,
        # OTel correlation fields (Section 11.4)
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "trace_flags": trace_flags,
        # Agent/Org fields (Section 5.2)
        "agent_name": agent_name,
        "org_id": org_id,
        "org_name": org_name,
        # Policy fields (Section 5.3)
        "policy_id": policy_id,
        "policy_name": policy_name,
        "policy_version": policy_version,
        # Prompt fields (Section 5.3)
        "prompt_id": prompt_id,
        "prompt_name": prompt_name,
        "prompt_version": prompt_version,
        # Governance fields (Section 5.4)
        "hash_type": hash_type,
        "data_classification": data_classification,
        # Metadata (Section 5.7)
        "template_rendered": template_rendered,
        # Denial fields (Section 5.5)
        "denial_reason": denial_reason,
        "violation_type": violation_type,
        "severity": severity,
        # Request fields (Section 5.6)
        "source_ip": source_ip,
        "request_method": request_method,
        "request_path": request_path,
        # Extension (Section 5.7)
        "metadata": metadata or {},
    }

    # Merkle tree (Section 8.8) — only present when used
    if governance_merkle_tree is not None:
        event["governance_merkle_tree"] = governance_merkle_tree

    return event
