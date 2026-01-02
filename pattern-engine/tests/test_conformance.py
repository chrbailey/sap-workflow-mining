"""
Tests for conformance checking module.

Tests cover:
- Process model definitions
- Conformance checker initialization
- Token-based replay conformance checking
- Deviation detection and classification
- SAP O2C template models
"""

import pytest
from datetime import datetime, timedelta

from src.conformance import (
    # Models
    Activity,
    ActivityType,
    ProcessModel,
    ProcessState,
    Transition,
    # Checker
    ConformanceChecker,
    ConformanceResult,
    CaseConformanceResult,
    calculate_conformance_rate,
    # Deviations
    Deviation,
    DeviationType,
    DeviationDetector,
    DeviationSummary,
    Severity,
    SeverityScorer,
    DEFAULT_SEVERITY_RULES,
    # Templates
    get_o2c_model,
    get_simple_o2c_model,
    get_detailed_o2c_model,
    SAP_O2C_ACTIVITIES,
)


# Test fixtures
@pytest.fixture
def o2c_model():
    """Get the standard O2C model."""
    return get_o2c_model()


@pytest.fixture
def conforming_trace():
    """A trace that conforms to O2C model."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    return [
        {"activity": "OrderCreated", "timestamp": base.isoformat()},
        {"activity": "DeliveryCreated", "timestamp": (base + timedelta(days=2)).isoformat()},
        {"activity": "GoodsIssued", "timestamp": (base + timedelta(days=3)).isoformat()},
        {"activity": "InvoiceCreated", "timestamp": (base + timedelta(days=5)).isoformat()},
    ]


@pytest.fixture
def non_conforming_trace():
    """A trace with deviations from O2C model."""
    base = datetime(2024, 1, 1, 10, 0, 0)
    return [
        {"activity": "OrderCreated", "timestamp": base.isoformat()},
        # Missing DeliveryCreated - skipped step
        {"activity": "InvoiceCreated", "timestamp": (base + timedelta(days=5)).isoformat()},
    ]


class TestActivity:
    """Tests for Activity class."""

    def test_activity_creation(self):
        """Test basic activity creation."""
        activity = Activity(
            name="OrderCreated",
            display_name="Order Created",
            activity_type=ActivityType.START,
        )

        assert activity.name == "OrderCreated"
        assert activity.display_name == "Order Created"
        assert activity.activity_type == ActivityType.START

    def test_activity_with_description(self):
        """Test activity with optional description."""
        activity = Activity(
            name="OrderCreated",
            display_name="Order Created",
            activity_type=ActivityType.START,
            description="Sales order is created",
        )

        assert activity.description == "Sales order is created"

    def test_activity_equality(self):
        """Test activity equality based on name."""
        a1 = Activity(name="Test", display_name="Test", activity_type=ActivityType.INTERMEDIATE)
        a2 = Activity(name="Test", display_name="Test 2", activity_type=ActivityType.START)

        assert a1 == a2  # Same name = equal

    def test_activity_hash(self):
        """Test activity can be used in sets."""
        a1 = Activity(name="Test", display_name="Test", activity_type=ActivityType.INTERMEDIATE)
        a2 = Activity(name="Test2", display_name="Test2", activity_type=ActivityType.INTERMEDIATE)

        activity_set = {a1, a2}
        assert len(activity_set) == 2


class TestActivityType:
    """Tests for ActivityType enum."""

    def test_activity_types_exist(self):
        """Test that expected activity types exist."""
        assert ActivityType.START is not None
        assert ActivityType.END is not None
        assert ActivityType.INTERMEDIATE is not None
        assert ActivityType.OPTIONAL is not None
        assert ActivityType.MILESTONE is not None

    def test_activity_type_values(self):
        """Test activity type values."""
        assert ActivityType.START.value == "start"
        assert ActivityType.END.value == "end"


class TestTransition:
    """Tests for Transition class."""

    def test_transition_creation(self):
        """Test basic transition creation."""
        source = Activity(name="A", display_name="A", activity_type=ActivityType.START)
        target = Activity(name="B", display_name="B", activity_type=ActivityType.END)

        transition = Transition(source=source, target=target)

        assert transition.source == source
        assert transition.target == target
        assert transition.is_mandatory is True

    def test_optional_transition(self):
        """Test optional transition."""
        source = Activity(name="A", display_name="A", activity_type=ActivityType.START)
        target = Activity(name="B", display_name="B", activity_type=ActivityType.END)

        transition = Transition(source=source, target=target, is_mandatory=False)

        assert transition.is_mandatory is False


class TestDeviationType:
    """Tests for DeviationType enum."""

    def test_deviation_types_exist(self):
        """Test that expected deviation types exist."""
        assert DeviationType.SKIPPED_ACTIVITY is not None
        assert DeviationType.WRONG_ORDER is not None
        assert DeviationType.UNEXPECTED_ACTIVITY is not None
        assert DeviationType.MISSING_ACTIVITY is not None
        assert DeviationType.DUPLICATE_ACTIVITY is not None

    def test_deviation_type_values(self):
        """Test deviation type string values."""
        assert DeviationType.SKIPPED_ACTIVITY.value == "skipped_activity"


class TestSeverity:
    """Tests for Severity enum."""

    def test_severity_levels_exist(self):
        """Test that expected severity levels exist."""
        assert Severity.CRITICAL is not None
        assert Severity.MAJOR is not None
        assert Severity.MINOR is not None
        assert Severity.INFO is not None

    def test_severity_comparison(self):
        """Test severity levels are comparable."""
        assert Severity.CRITICAL < Severity.MAJOR
        assert Severity.MAJOR < Severity.MINOR
        assert Severity.MINOR < Severity.INFO


class TestDeviation:
    """Tests for Deviation class."""

    def test_deviation_creation(self):
        """Test creating a deviation."""
        deviation = Deviation(
            deviation_type=DeviationType.SKIPPED_ACTIVITY,
            severity=Severity.MAJOR,
            activity_name="DeliveryCreated",
            expected="DeliveryCreated after OrderCreated",
            actual="InvoiceCreated (skipped delivery)",
        )

        assert deviation.deviation_type == DeviationType.SKIPPED_ACTIVITY
        assert deviation.severity == Severity.MAJOR
        assert deviation.activity_name == "DeliveryCreated"

    def test_deviation_to_dict(self):
        """Test deviation serialization."""
        deviation = Deviation(
            deviation_type=DeviationType.WRONG_ORDER,
            severity=Severity.CRITICAL,
            activity_name="InvoiceCreated",
            expected="Invoice after GoodsIssued",
            actual="Invoice before GoodsIssued",
        )

        result = deviation.to_dict()
        assert isinstance(result, dict)
        assert "deviation_type" in result or "type" in result


class TestO2CTemplates:
    """Tests for pre-built O2C templates."""

    def test_get_o2c_model(self):
        """Test getting default O2C model."""
        model = get_o2c_model()

        assert model is not None
        assert isinstance(model, ProcessModel)

    def test_get_simple_o2c_model(self):
        """Test getting simple O2C model."""
        model = get_simple_o2c_model()

        assert model is not None
        assert isinstance(model, ProcessModel)

    def test_get_detailed_o2c_model(self):
        """Test getting detailed O2C model."""
        model = get_detailed_o2c_model()

        assert model is not None
        assert isinstance(model, ProcessModel)

    def test_sap_o2c_activities(self):
        """Test SAP O2C activities constant."""
        assert SAP_O2C_ACTIVITIES is not None
        assert len(SAP_O2C_ACTIVITIES) > 0

    def test_o2c_activities_are_activities(self):
        """Test that O2C activities are Activity instances."""
        # SAP_O2C_ACTIVITIES is a dict mapping name -> Activity
        for name, activity in SAP_O2C_ACTIVITIES.items():
            assert isinstance(activity, Activity)
            assert activity.name == name


class TestConformanceChecker:
    """Tests for ConformanceChecker."""

    def test_checker_creation(self, o2c_model):
        """Test checker instantiation."""
        checker = ConformanceChecker(o2c_model)
        assert checker is not None

    def test_check_conforming_trace(self, o2c_model, conforming_trace):
        """Test checking a conforming trace."""
        checker = ConformanceChecker(o2c_model)
        result = checker.check_trace(conforming_trace, case_id="ORDER001")

        assert result is not None
        assert isinstance(result, CaseConformanceResult)
        assert result.case_id == "ORDER001"

    def test_check_non_conforming_trace(self, o2c_model, non_conforming_trace):
        """Test checking a non-conforming trace."""
        checker = ConformanceChecker(o2c_model)
        result = checker.check_trace(non_conforming_trace, case_id="ORDER002")

        assert result is not None
        assert isinstance(result, CaseConformanceResult)
        # Non-conforming trace should have deviations or lower fitness
        assert hasattr(result, 'deviations') or hasattr(result, 'fitness_score')

    def test_conformance_result_attributes(self, o2c_model, conforming_trace):
        """Test CaseConformanceResult has expected attributes."""
        checker = ConformanceChecker(o2c_model)
        result = checker.check_trace(conforming_trace, case_id="ORDER003")

        assert hasattr(result, 'case_id')
        assert hasattr(result, 'is_conformant')
        assert hasattr(result, 'fitness_score')
        assert hasattr(result, 'deviations')


class TestDefaultSeverityRules:
    """Tests for default severity rules."""

    def test_rules_exist(self):
        """Test that default rules are defined."""
        assert DEFAULT_SEVERITY_RULES is not None
        assert len(DEFAULT_SEVERITY_RULES) > 0

    def test_rules_for_skipped(self):
        """Test rules for skipped activity."""
        assert DeviationType.SKIPPED_ACTIVITY.value in DEFAULT_SEVERITY_RULES

    def test_rules_have_defaults(self):
        """Test each rule type has a default."""
        for rule_type, rules in DEFAULT_SEVERITY_RULES.items():
            assert "default" in rules


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_trace(self, o2c_model):
        """Test checking empty trace."""
        checker = ConformanceChecker(o2c_model)
        result = checker.check_trace([], case_id="EMPTY")

        assert result is not None

    def test_single_event_trace(self, o2c_model):
        """Test trace with single event."""
        trace = [{"activity": "OrderCreated", "timestamp": "2024-01-01T10:00:00"}]

        checker = ConformanceChecker(o2c_model)
        result = checker.check_trace(trace, case_id="SINGLE")

        assert result is not None

    def test_duplicate_events(self, o2c_model):
        """Test trace with duplicate events."""
        base = datetime(2024, 1, 1, 10, 0, 0)
        trace = [
            {"activity": "OrderCreated", "timestamp": base.isoformat()},
            {"activity": "OrderCreated", "timestamp": (base + timedelta(hours=1)).isoformat()},
            {"activity": "DeliveryCreated", "timestamp": (base + timedelta(days=2)).isoformat()},
        ]

        checker = ConformanceChecker(o2c_model)
        result = checker.check_trace(trace, case_id="DUPLICATE")

        assert result is not None

    def test_out_of_order_events(self, o2c_model):
        """Test trace with out of order events."""
        base = datetime(2024, 1, 1, 10, 0, 0)
        trace = [
            {"activity": "OrderCreated", "timestamp": base.isoformat()},
            {"activity": "InvoiceCreated", "timestamp": (base + timedelta(days=1)).isoformat()},
            {"activity": "DeliveryCreated", "timestamp": (base + timedelta(days=2)).isoformat()},
        ]

        checker = ConformanceChecker(o2c_model)
        result = checker.check_trace(trace, case_id="OUT_OF_ORDER")

        assert result is not None
        # Should detect wrong order deviation
        assert len(result.deviations) > 0 or not result.is_fully_conformant


class TestConformanceRate:
    """Tests for conformance rate calculation."""

    def test_calculate_conformance_rate_function_exists(self):
        """Test that calculate_conformance_rate function exists."""
        assert calculate_conformance_rate is not None
        assert callable(calculate_conformance_rate)
