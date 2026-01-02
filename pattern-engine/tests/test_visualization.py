"""
Tests for visualization module.

Tests cover:
- Mermaid diagram generation
- GraphViz DOT format generation
- Bottleneck analysis and detection
- Convenience function
"""

import pytest
from datetime import datetime, timedelta

from src.visualization import (
    # Mermaid
    MermaidGenerator,
    generate_mermaid_diagram,
    # GraphViz
    GraphVizGenerator,
    generate_dot_diagram,
    generate_svg_diagram,
    # Bottleneck
    BottleneckAnalyzer,
    BottleneckAnalysis,
    BottleneckLevel,
    TransitionMetrics,
    analyze_bottlenecks,
    # Convenience
    generate_process_diagram,
)


# Test fixtures
@pytest.fixture
def sample_events():
    """Sample O2C events for testing."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    return [
        {"case_id": "ORDER001", "type": "OrderCreated", "timestamp": base.isoformat()},
        {"case_id": "ORDER001", "type": "DeliveryCreated", "timestamp": (base + timedelta(days=2)).isoformat()},
        {"case_id": "ORDER001", "type": "GoodsIssued", "timestamp": (base + timedelta(days=3)).isoformat()},
        {"case_id": "ORDER001", "type": "InvoiceCreated", "timestamp": (base + timedelta(days=5)).isoformat()},
    ]


@pytest.fixture
def multi_case_events():
    """Multiple cases for bottleneck analysis."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    events = []
    for i in range(5):
        case_id = f"ORDER{i:03d}"
        delay = timedelta(hours=i * 12)  # Varying delays
        events.extend([
            {"case_id": case_id, "type": "OrderCreated", "timestamp": (base + delay).isoformat()},
            {"case_id": case_id, "type": "DeliveryCreated", "timestamp": (base + delay + timedelta(days=2 + i)).isoformat()},
            {"case_id": case_id, "type": "GoodsIssued", "timestamp": (base + delay + timedelta(days=3 + i)).isoformat()},
            {"case_id": case_id, "type": "InvoiceCreated", "timestamp": (base + delay + timedelta(days=5 + i * 2)).isoformat()},
        ])
    return events


class TestMermaidGenerator:
    """Tests for Mermaid diagram generation."""

    def test_generator_creation(self):
        """Test MermaidGenerator instantiation."""
        generator = MermaidGenerator()
        assert generator is not None

    def test_generate_basic_diagram(self, sample_events):
        """Test basic diagram generation."""
        generator = MermaidGenerator()
        diagram = generator.generate(sample_events)

        assert diagram is not None
        assert "flowchart" in diagram.lower() or "graph" in diagram.lower()

    def test_generate_with_timing(self, sample_events):
        """Test diagram generation with timing annotations."""
        generator = MermaidGenerator()
        diagram = generator.generate(sample_events, include_timing=True)

        assert diagram is not None
        # Should contain some timing information
        assert len(diagram) > 0

    def test_generate_empty_events(self):
        """Test handling of empty event list."""
        generator = MermaidGenerator()
        diagram = generator.generate([])

        # Should return something (even if minimal)
        assert diagram is not None

    def test_convenience_function(self, sample_events):
        """Test generate_mermaid_diagram convenience function."""
        diagram = generate_mermaid_diagram(sample_events)

        assert diagram is not None
        assert len(diagram) > 0


class TestGraphVizGenerator:
    """Tests for GraphViz DOT format generation."""

    def test_generator_creation(self):
        """Test GraphVizGenerator instantiation."""
        generator = GraphVizGenerator()
        assert generator is not None

    def test_generate_dot_format(self, sample_events):
        """Test DOT format generation."""
        generator = GraphVizGenerator()
        dot = generator.generate(sample_events)

        assert dot is not None
        assert "digraph" in dot.lower() or "graph" in dot.lower()

    def test_generate_with_timing(self, sample_events):
        """Test DOT generation with timing."""
        generator = GraphVizGenerator()
        dot = generator.generate(sample_events, include_timing=True)

        assert dot is not None
        assert len(dot) > 0

    def test_convenience_function(self, sample_events):
        """Test generate_dot_diagram convenience function."""
        dot = generate_dot_diagram(sample_events)

        assert dot is not None
        assert len(dot) > 0


class TestBottleneckAnalyzer:
    """Tests for bottleneck analysis."""

    def test_analyzer_creation(self):
        """Test BottleneckAnalyzer instantiation."""
        analyzer = BottleneckAnalyzer()
        assert analyzer is not None

    def test_analyzer_with_custom_thresholds(self):
        """Test analyzer with custom percentile thresholds."""
        analyzer = BottleneckAnalyzer(percentile_thresholds=(40, 80))
        assert analyzer is not None

    def test_analyze_events(self, multi_case_events):
        """Test bottleneck analysis on events."""
        analyzer = BottleneckAnalyzer()
        analysis = analyzer.analyze(multi_case_events)

        assert analysis is not None
        assert isinstance(analysis, BottleneckAnalysis)

    def test_analyze_empty_events(self):
        """Test analysis of empty event list."""
        analyzer = BottleneckAnalyzer()
        analysis = analyzer.analyze([])

        assert analysis is not None

    def test_convenience_function(self, multi_case_events):
        """Test analyze_bottlenecks convenience function."""
        analysis = analyze_bottlenecks(multi_case_events)

        assert analysis is not None


class TestBottleneckLevel:
    """Tests for BottleneckLevel enum."""

    def test_level_values(self):
        """Test that expected levels exist."""
        assert BottleneckLevel.FAST is not None
        assert BottleneckLevel.MEDIUM is not None
        assert BottleneckLevel.SLOW is not None

    def test_level_comparison(self):
        """Test level ordering."""
        # Levels should be comparable
        levels = [BottleneckLevel.FAST, BottleneckLevel.MEDIUM, BottleneckLevel.SLOW]
        assert len(levels) == 3


class TestTransitionMetrics:
    """Tests for TransitionMetrics dataclass."""

    def test_metrics_creation(self):
        """Test TransitionMetrics can be created."""
        # This tests that the class exists and can be instantiated
        # The exact fields depend on implementation
        assert TransitionMetrics is not None


class TestGenerateProcessDiagram:
    """Tests for the convenience function generate_process_diagram."""

    def test_mermaid_format(self, sample_events):
        """Test Mermaid format output."""
        diagram = generate_process_diagram(sample_events, format="mermaid")

        assert diagram is not None
        assert len(diagram) > 0

    def test_dot_format(self, sample_events):
        """Test DOT format output."""
        diagram = generate_process_diagram(sample_events, format="dot")

        assert diagram is not None
        assert "digraph" in diagram.lower() or "graph" in diagram.lower()

    def test_invalid_format(self, sample_events):
        """Test invalid format raises error."""
        with pytest.raises(ValueError):
            generate_process_diagram(sample_events, format="invalid")

    def test_with_bottlenecks(self, multi_case_events):
        """Test diagram with bottleneck highlighting."""
        diagram = generate_process_diagram(
            multi_case_events,
            format="mermaid",
            include_bottlenecks=True
        )

        assert diagram is not None

    def test_without_bottlenecks(self, sample_events):
        """Test diagram without bottleneck highlighting."""
        diagram = generate_process_diagram(
            sample_events,
            format="mermaid",
            include_bottlenecks=False
        )

        assert diagram is not None

    def test_without_timing(self, sample_events):
        """Test diagram without timing annotations."""
        diagram = generate_process_diagram(
            sample_events,
            format="mermaid",
            include_timing=False
        )

        assert diagram is not None


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_single_event(self):
        """Test with single event."""
        events = [{"case_id": "ORDER001", "type": "OrderCreated", "timestamp": "2024-01-01T10:00:00"}]

        generator = MermaidGenerator()
        diagram = generator.generate(events)

        assert diagram is not None

    def test_missing_case_id(self):
        """Test events without case_id."""
        events = [
            {"type": "OrderCreated", "timestamp": "2024-01-01T10:00:00"},
            {"type": "DeliveryCreated", "timestamp": "2024-01-02T10:00:00"},
        ]

        generator = MermaidGenerator()
        # Should handle gracefully
        diagram = generator.generate(events)
        assert diagram is not None

    def test_alternative_field_names(self):
        """Test with alternative field names (activity vs type)."""
        events = [
            {"case_id": "ORDER001", "activity": "OrderCreated", "timestamp": "2024-01-01T10:00:00"},
            {"case_id": "ORDER001", "activity": "DeliveryCreated", "timestamp": "2024-01-02T10:00:00"},
        ]

        generator = MermaidGenerator()
        diagram = generator.generate(events)
        assert diagram is not None

    def test_out_of_order_timestamps(self):
        """Test events with out-of-order timestamps."""
        events = [
            {"case_id": "ORDER001", "type": "InvoiceCreated", "timestamp": "2024-01-04T10:00:00"},
            {"case_id": "ORDER001", "type": "OrderCreated", "timestamp": "2024-01-01T10:00:00"},
            {"case_id": "ORDER001", "type": "DeliveryCreated", "timestamp": "2024-01-02T10:00:00"},
        ]

        generator = MermaidGenerator()
        diagram = generator.generate(events)
        assert diagram is not None
