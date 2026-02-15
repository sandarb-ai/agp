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

    return event
