"""
Tests for AIGP v0.7.0 New Event Types
======================================

Tests all 14 new instrumentor convenience methods added in v0.7.0:
- Memory: MEMORY_READ, MEMORY_WRITTEN
- Tool: TOOL_INVOKED, TOOL_DENIED
- Context: CONTEXT_CAPTURED
- Lineage: LINEAGE_SNAPSHOT
- Inference: INFERENCE_STARTED, INFERENCE_COMPLETED, INFERENCE_BLOCKED
- Human: HUMAN_OVERRIDE, HUMAN_APPROVAL
- Classification: CLASSIFICATION_CHANGED
- Model: MODEL_LOADED, MODEL_SWITCHED
"""

import hashlib
import re

import pytest

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry import trace

from aigp_otel.instrumentor import AIGPInstrumentor
from aigp_otel.events import compute_governance_hash


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture(autouse=True)
def setup_tracer():
    """Set up a real OTel TracerProvider for tests."""
    resource = Resource.create({"service.name": "aigp-test"})
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)
    yield
    # Cleanup
    provider.shutdown()


@pytest.fixture
def instrumentor():
    """Create an AIGPInstrumentor for testing."""
    return AIGPInstrumentor(
        agent_id="agent.test-bot",
        agent_name="Test Bot",
        org_id="org.test",
    )


# ===================================================================
# Memory Events
# ===================================================================

class TestMemoryRead:
    """Tests for MEMORY_READ governance event."""

    def test_event_type_and_category(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.memory_read(
                memory_name="memory.conversation-history",
                query="What is the trading limit?",
                content='{"messages": [{"role": "user", "content": "Hello"}]}',
                span=span,
            )
        assert event["event_type"] == "MEMORY_READ"
        assert event["event_category"] == "memory"

    def test_governance_hash_computed(self, instrumentor):
        content = '{"messages": [{"role": "user", "content": "Hello"}]}'
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.memory_read(
                memory_name="memory.history",
                query="recent messages",
                content=content,
                span=span,
            )
        expected_hash = compute_governance_hash(content)
        assert event["governance_hash"] == expected_hash

    def test_query_hash_computed(self, instrumentor):
        query = "What is the trading limit?"
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.memory_read(
                memory_name="memory.history",
                query=query,
                content="some content",
                span=span,
            )
        expected_query_hash = compute_governance_hash(query)
        assert event["query_hash"] == expected_query_hash

    def test_query_hash_differs_from_governance_hash(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.memory_read(
                memory_name="memory.history",
                query="query text",
                content="content text",
                span=span,
            )
        assert event["query_hash"] != event["governance_hash"]

    def test_data_classification(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.memory_read(
                memory_name="memory.history",
                query="q",
                content="c",
                data_classification="confidential",
                span=span,
            )
        assert event["data_classification"] == "confidential"


class TestMemoryWritten:
    """Tests for MEMORY_WRITTEN governance event."""

    def test_event_type_and_category(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.memory_written(
                memory_name="memory.agent-state",
                content='{"state": "updated"}',
                span=span,
            )
        assert event["event_type"] == "MEMORY_WRITTEN"
        assert event["event_category"] == "memory"

    def test_governance_hash_of_new_content(self, instrumentor):
        content = '{"state": "new"}'
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.memory_written(
                memory_name="memory.state",
                content=content,
                span=span,
            )
        assert event["governance_hash"] == compute_governance_hash(content)

    def test_previous_hash_when_previous_content_provided(self, instrumentor):
        old_content = '{"state": "old"}'
        new_content = '{"state": "new"}'
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.memory_written(
                memory_name="memory.state",
                content=new_content,
                previous_content=old_content,
                span=span,
            )
        assert event["previous_hash"] == compute_governance_hash(old_content)
        assert event["governance_hash"] == compute_governance_hash(new_content)

    def test_previous_hash_empty_when_no_previous(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.memory_written(
                memory_name="memory.state",
                content="new content",
                span=span,
            )
        assert event["previous_hash"] == ""


# ===================================================================
# Tool Events
# ===================================================================

class TestToolInvoked:
    """Tests for TOOL_INVOKED governance event."""

    def test_event_type_and_category(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.tool_invoked(
                tool_name="tool.order-lookup",
                content='{"order_id": "12345"}',
                span=span,
            )
        assert event["event_type"] == "TOOL_INVOKED"
        assert event["event_category"] == "tool"

    def test_governance_hash_computed(self, instrumentor):
        content = '{"order_id": "12345"}'
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.tool_invoked(
                tool_name="tool.order-lookup",
                content=content,
                span=span,
            )
        assert event["governance_hash"] == compute_governance_hash(content)

    def test_empty_content_no_hash(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.tool_invoked(
                tool_name="tool.order-lookup",
                span=span,
            )
        assert event["governance_hash"] == ""


class TestToolDenied:
    """Tests for TOOL_DENIED governance event."""

    def test_event_type_and_category(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.tool_denied(
                tool_name="tool.delete-account",
                denial_reason="Insufficient permissions",
                span=span,
            )
        assert event["event_type"] == "TOOL_DENIED"
        assert event["event_category"] == "tool"

    def test_denial_fields(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.tool_denied(
                tool_name="tool.delete-account",
                denial_reason="Insufficient permissions",
                severity="high",
                violation_type="ACCESS_CONTROL",
                span=span,
            )
        assert event["denial_reason"] == "Insufficient permissions"
        assert event["severity"] == "high"
        assert event["violation_type"] == "ACCESS_CONTROL"


# ===================================================================
# Context Events
# ===================================================================

class TestContextCaptured:
    """Tests for CONTEXT_CAPTURED governance event."""

    def test_event_type_and_category(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.context_captured(
                context_name="context.env-config",
                content='{"env": "production", "region": "us-east-1"}',
                span=span,
            )
        assert event["event_type"] == "CONTEXT_CAPTURED"
        assert event["event_category"] == "context"

    def test_governance_hash_computed(self, instrumentor):
        content = '{"env": "production"}'
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.context_captured(
                context_name="context.env",
                content=content,
                span=span,
            )
        assert event["governance_hash"] == compute_governance_hash(content)


# ===================================================================
# Lineage Events
# ===================================================================

class TestLineageSnapshot:
    """Tests for LINEAGE_SNAPSHOT governance event."""

    def test_event_type_and_category(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.lineage_snapshot(
                lineage_name="lineage.upstream-orders",
                content='{"datasets": ["orders", "customers"]}',
                span=span,
            )
        assert event["event_type"] == "LINEAGE_SNAPSHOT"
        assert event["event_category"] == "lineage"

    def test_governance_hash_computed(self, instrumentor):
        content = '{"datasets": ["orders"]}'
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.lineage_snapshot(
                lineage_name="lineage.upstream",
                content=content,
                span=span,
            )
        assert event["governance_hash"] == compute_governance_hash(content)


# ===================================================================
# Inference Events
# ===================================================================

class TestInferenceStarted:
    """Tests for INFERENCE_STARTED governance event."""

    def test_event_type_and_category(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.inference_started(
                content="User prompt: What stocks should I buy?",
                span=span,
            )
        assert event["event_type"] == "INFERENCE_STARTED"
        assert event["event_category"] == "inference"

    def test_governance_hash_of_input(self, instrumentor):
        content = "User prompt: What stocks should I buy?"
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.inference_started(content=content, span=span)
        assert event["governance_hash"] == compute_governance_hash(content)


class TestInferenceCompleted:
    """Tests for INFERENCE_COMPLETED governance event."""

    def test_event_type_and_category(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.inference_completed(
                content="Based on analysis, I recommend diversifying...",
                span=span,
            )
        assert event["event_type"] == "INFERENCE_COMPLETED"
        assert event["event_category"] == "inference"

    def test_governance_hash_of_output(self, instrumentor):
        content = "Recommendation: diversify portfolio"
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.inference_completed(content=content, span=span)
        assert event["governance_hash"] == compute_governance_hash(content)


class TestInferenceBlocked:
    """Tests for INFERENCE_BLOCKED governance event."""

    def test_event_type_and_category(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.inference_blocked(
                denial_reason="Content safety violation detected",
                span=span,
            )
        assert event["event_type"] == "INFERENCE_BLOCKED"
        assert event["event_category"] == "inference"

    def test_denial_fields(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.inference_blocked(
                denial_reason="Safety filter triggered",
                severity="critical",
                violation_type="CONTENT_SAFETY",
                span=span,
            )
        assert event["denial_reason"] == "Safety filter triggered"
        assert event["severity"] == "critical"
        assert event["violation_type"] == "CONTENT_SAFETY"

    def test_no_governance_hash(self, instrumentor):
        """INFERENCE_BLOCKED should not have a governance_hash (content was blocked)."""
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.inference_blocked(
                denial_reason="blocked",
                span=span,
            )
        assert event["governance_hash"] == ""


# ===================================================================
# Human-in-the-Loop Events
# ===================================================================

class TestHumanOverride:
    """Tests for HUMAN_OVERRIDE governance event."""

    def test_event_type_and_category(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.human_override(
                denial_reason="Human reviewer rejected agent recommendation",
                span=span,
            )
        assert event["event_type"] == "HUMAN_OVERRIDE"
        assert event["event_category"] == "human"

    def test_denial_reason(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.human_override(
                denial_reason="Trade exceeds manual review threshold",
                span=span,
            )
        assert event["denial_reason"] == "Trade exceeds manual review threshold"


class TestHumanApproval:
    """Tests for HUMAN_APPROVAL governance event."""

    def test_event_type_and_category(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.human_approval(
                content="Trade approved: BUY 1000 AAPL @ $180",
                span=span,
            )
        assert event["event_type"] == "HUMAN_APPROVAL"
        assert event["event_category"] == "human"

    def test_governance_hash_of_approved_content(self, instrumentor):
        content = "Trade approved: BUY 1000 AAPL @ $180"
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.human_approval(content=content, span=span)
        assert event["governance_hash"] == compute_governance_hash(content)


# ===================================================================
# Classification Events
# ===================================================================

class TestClassificationChanged:
    """Tests for CLASSIFICATION_CHANGED governance event."""

    def test_event_type_and_category(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.classification_changed(
                new_classification="restricted",
                previous_classification="confidential",
                span=span,
            )
        assert event["event_type"] == "CLASSIFICATION_CHANGED"
        assert event["event_category"] == "classification"

    def test_data_classification_set(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.classification_changed(
                new_classification="restricted",
                span=span,
            )
        assert event["data_classification"] == "restricted"

    def test_previous_classification_in_annotations(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.classification_changed(
                new_classification="restricted",
                previous_classification="confidential",
                span=span,
            )
        assert event["annotations"]["previous_classification"] == "confidential"

    def test_no_previous_classification(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.classification_changed(
                new_classification="internal",
                span=span,
            )
        assert "previous_classification" not in event["annotations"]


# ===================================================================
# Model Events
# ===================================================================

class TestModelLoaded:
    """Tests for MODEL_LOADED governance event."""

    def test_event_type_and_category(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.model_loaded(
                model_name="model.gpt4-trading-v2",
                content='{"model": "gpt-4", "version": "2024-01"}',
                span=span,
            )
        assert event["event_type"] == "MODEL_LOADED"
        assert event["event_category"] == "model"

    def test_governance_hash_computed(self, instrumentor):
        content = '{"model": "gpt-4", "version": "2024-01"}'
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.model_loaded(
                model_name="model.gpt4",
                content=content,
                span=span,
            )
        assert event["governance_hash"] == compute_governance_hash(content)


class TestModelSwitched:
    """Tests for MODEL_SWITCHED governance event."""

    def test_event_type_and_category(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.model_switched(
                model_name="model.gpt4-turbo",
                content='{"model": "gpt-4-turbo"}',
                span=span,
            )
        assert event["event_type"] == "MODEL_SWITCHED"
        assert event["event_category"] == "model"

    def test_governance_hash_of_new_model(self, instrumentor):
        content = '{"model": "gpt-4-turbo"}'
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.model_switched(
                model_name="model.gpt4-turbo",
                content=content,
                span=span,
            )
        assert event["governance_hash"] == compute_governance_hash(content)

    def test_previous_hash_when_previous_content_provided(self, instrumentor):
        old_content = '{"model": "gpt-4"}'
        new_content = '{"model": "gpt-4-turbo"}'
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.model_switched(
                model_name="model.gpt4-turbo",
                content=new_content,
                previous_content=old_content,
                span=span,
            )
        assert event["previous_hash"] == compute_governance_hash(old_content)
        assert event["governance_hash"] == compute_governance_hash(new_content)

    def test_previous_hash_empty_when_no_previous(self, instrumentor):
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            event = instrumentor.model_switched(
                model_name="model.gpt4-turbo",
                content='{"model": "gpt-4-turbo"}',
                span=span,
            )
        assert event["previous_hash"] == ""


# ===================================================================
# Cross-cutting tests
# ===================================================================

class TestNewEventCommon:
    """Cross-cutting tests for all new v0.7.0 event types."""

    def test_all_events_have_agent_id(self, instrumentor):
        """All new events must carry the configured agent_id."""
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            events = [
                instrumentor.memory_read("memory.test", "q", "c", span=span),
                instrumentor.memory_written("memory.test", "c", span=span),
                instrumentor.tool_invoked("tool.test", content="c", span=span),
                instrumentor.tool_denied("tool.test", "denied", span=span),
                instrumentor.context_captured("context.test", "c", span=span),
                instrumentor.lineage_snapshot("lineage.test", "c", span=span),
                instrumentor.inference_started("c", span=span),
                instrumentor.inference_completed("c", span=span),
                instrumentor.inference_blocked("blocked", span=span),
                instrumentor.human_override("reason", span=span),
                instrumentor.human_approval("c", span=span),
                instrumentor.classification_changed("internal", span=span),
                instrumentor.model_loaded("model.test", "c", span=span),
                instrumentor.model_switched("model.test", "c", span=span),
            ]
        for event in events:
            assert event["agent_id"] == "agent.test-bot"

    def test_all_events_have_valid_event_id(self, instrumentor):
        """All new events must have a valid UUID event_id."""
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        )
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            events = [
                instrumentor.memory_read("memory.test", "q", "c", span=span),
                instrumentor.tool_invoked("tool.test", content="c", span=span),
                instrumentor.inference_started("c", span=span),
                instrumentor.human_approval("c", span=span),
                instrumentor.model_loaded("model.test", "c", span=span),
            ]
        for event in events:
            assert uuid_pattern.match(event["event_id"]), f"Invalid event_id: {event['event_id']}"

    def test_all_events_have_spec_version(self, instrumentor):
        """All new events must have spec_version 0.7.0."""
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            events = [
                instrumentor.memory_read("memory.test", "q", "c", span=span),
                instrumentor.memory_written("memory.test", "c", span=span),
                instrumentor.model_loaded("model.test", "c", span=span),
                instrumentor.model_switched("model.test", "c", span=span),
            ]
        for event in events:
            assert event["spec_version"] == "0.7.0"

    def test_event_callback_called(self):
        """Event callback is called for new event types."""
        captured = []
        instr = AIGPInstrumentor(
            agent_id="agent.test",
            event_callback=captured.append,
        )
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            instr.memory_read("memory.test", "q", "c", span=span)
            instr.model_loaded("model.test", "c", span=span)
        assert len(captured) == 2
        assert captured[0]["event_type"] == "MEMORY_READ"
        assert captured[1]["event_type"] == "MODEL_LOADED"
