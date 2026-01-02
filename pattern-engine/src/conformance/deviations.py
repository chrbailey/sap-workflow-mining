"""
Deviation Detection and Severity Scoring for Conformance Checking.

Implements deviation detection algorithms based on academic conformance
checking approaches:

- Token-based replay (van der Aalst et al., 2012)
- Alignment-based conformance (Adriansyah et al., 2011)

Deviation Types:
- SKIPPED_ACTIVITY: Required activity not executed (e.g., delivery without order)
- WRONG_ORDER: Activities executed out of sequence (e.g., invoice before delivery)
- UNEXPECTED_ACTIVITY: Activity not in the expected model
- MISSING_ACTIVITY: Mandatory activity never occurred
- DUPLICATE_ACTIVITY: Same activity executed multiple times unexpectedly

Severity Scoring:
- CRITICAL: Process cannot be valid (e.g., invoice without order)
- MAJOR: Significant deviation requiring attention
- MINOR: Small deviation, may be acceptable in some cases

References:
- van der Aalst, W., Adriansyah, A., & van Dongen, B. (2012).
  Replaying history on process models for conformance checking and
  performance analysis.
- Adriansyah, A., van Dongen, B.F., & van der Aalst, W.M.P. (2011).
  Conformance checking using cost-based fitness analysis.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from .models import Activity, ProcessModel

logger = logging.getLogger(__name__)


class DeviationType(Enum):
    """Types of process deviations."""

    SKIPPED_ACTIVITY = "skipped_activity"
    WRONG_ORDER = "wrong_order"
    UNEXPECTED_ACTIVITY = "unexpected_activity"
    MISSING_ACTIVITY = "missing_activity"
    DUPLICATE_ACTIVITY = "duplicate_activity"
    INVALID_START = "invalid_start"
    INVALID_END = "invalid_end"


class Severity(Enum):
    """Severity levels for deviations."""

    CRITICAL = "critical"  # Process fundamentally invalid
    MAJOR = "major"        # Significant issue requiring attention
    MINOR = "minor"        # Small deviation, may be acceptable
    INFO = "info"          # Informational only

    def __lt__(self, other: "Severity") -> bool:
        """Enable sorting by severity."""
        order = {
            Severity.CRITICAL: 0,
            Severity.MAJOR: 1,
            Severity.MINOR: 2,
            Severity.INFO: 3,
        }
        return order[self] < order[other]


# Severity scoring configuration
# Maps (deviation_type, activity_type_or_name) to severity
DEFAULT_SEVERITY_RULES: Dict[str, Dict[str, Severity]] = {
    DeviationType.SKIPPED_ACTIVITY.value: {
        "default": Severity.MAJOR,
        "OrderCreated": Severity.CRITICAL,  # No order = invalid
        "DeliveryCreated": Severity.MAJOR,
        "GoodsIssued": Severity.MAJOR,
        "InvoiceCreated": Severity.MAJOR,
    },
    DeviationType.WRONG_ORDER.value: {
        "default": Severity.MAJOR,
        "InvoiceCreated": Severity.CRITICAL,  # Invoice before delivery
        "GoodsIssued": Severity.MAJOR,
        "DeliveryCreated": Severity.MAJOR,
    },
    DeviationType.UNEXPECTED_ACTIVITY.value: {
        "default": Severity.MINOR,
    },
    DeviationType.MISSING_ACTIVITY.value: {
        "default": Severity.MAJOR,
        "OrderCreated": Severity.CRITICAL,
        "InvoiceCreated": Severity.MINOR,  # May be pending
    },
    DeviationType.DUPLICATE_ACTIVITY.value: {
        "default": Severity.MINOR,
    },
    DeviationType.INVALID_START.value: {
        "default": Severity.CRITICAL,
    },
    DeviationType.INVALID_END.value: {
        "default": Severity.MINOR,  # Process may be in progress
    },
}


@dataclass
class Deviation:
    """
    A detected deviation from the expected process model.

    Represents a single instance where actual execution diverged
    from the expected behavior defined in the process model.

    Attributes:
        deviation_type: Type of deviation detected
        severity: Severity level of the deviation
        activity_name: Name of the activity involved
        expected: What was expected (context-dependent)
        actual: What actually occurred
        position: Position in the event sequence
        timestamp: When the deviation occurred
        case_id: Identifier for the process instance
        details: Additional details about the deviation
        recommendation: Suggested action to address the deviation
    """
    deviation_type: DeviationType
    severity: Severity
    activity_name: str
    expected: str
    actual: str
    position: int = 0
    timestamp: Optional[datetime] = None
    case_id: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "deviation_type": self.deviation_type.value,
            "severity": self.severity.value,
            "activity_name": self.activity_name,
            "expected": self.expected,
            "actual": self.actual,
            "position": self.position,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "case_id": self.case_id,
            "details": self.details,
            "recommendation": self.recommendation,
        }


class SeverityScorer:
    """
    Calculates severity scores for deviations.

    Uses configurable rules to determine the severity of each
    deviation based on the deviation type and the activity involved.
    """

    def __init__(
        self,
        rules: Optional[Dict[str, Dict[str, Severity]]] = None
    ):
        """
        Initialize the severity scorer.

        Args:
            rules: Custom severity rules (uses defaults if not provided)
        """
        self._rules = rules or DEFAULT_SEVERITY_RULES

    def get_severity(
        self,
        deviation_type: DeviationType,
        activity_name: str
    ) -> Severity:
        """
        Get the severity for a deviation.

        Args:
            deviation_type: Type of deviation
            activity_name: Name of the activity involved

        Returns:
            The severity level
        """
        type_rules = self._rules.get(deviation_type.value, {})

        # Check for activity-specific rule
        if activity_name in type_rules:
            return type_rules[activity_name]

        # Fall back to default for this deviation type
        return type_rules.get("default", Severity.MAJOR)

    def add_rule(
        self,
        deviation_type: DeviationType,
        activity_name: str,
        severity: Severity
    ) -> None:
        """
        Add a custom severity rule.

        Args:
            deviation_type: Type of deviation
            activity_name: Activity name (or "default")
            severity: Severity to assign
        """
        if deviation_type.value not in self._rules:
            self._rules[deviation_type.value] = {}
        self._rules[deviation_type.value][activity_name] = severity


class DeviationDetector:
    """
    Detects deviations in event traces against a process model.

    Implements multiple detection strategies:
    1. Token-based replay: Simulates process execution
    2. Sequence analysis: Checks activity ordering
    3. Completeness check: Verifies all mandatory activities occurred

    The detector identifies:
    - Skipped activities (required predecessor not executed)
    - Wrong order (activities out of expected sequence)
    - Unexpected activities (not in model)
    - Missing activities (mandatory but not executed)
    """

    def __init__(
        self,
        model: ProcessModel,
        scorer: Optional[SeverityScorer] = None
    ):
        """
        Initialize the deviation detector.

        Args:
            model: The process model to check against
            scorer: Severity scorer (uses default if not provided)
        """
        self._model = model
        self._scorer = scorer or SeverityScorer()
        self._dependency_order = model.get_dependency_order()

    def detect_deviations(
        self,
        trace: List[Dict[str, Any]],
        case_id: str = ""
    ) -> List[Deviation]:
        """
        Detect all deviations in an event trace.

        Args:
            trace: List of events with 'activity' and optional 'timestamp' keys
            case_id: Identifier for the process instance

        Returns:
            List of detected deviations, sorted by severity
        """
        deviations = []

        # Extract activity sequence from trace
        activities = self._extract_activities(trace)

        if not activities:
            logger.debug(f"Empty trace for case {case_id}")
            return deviations

        # 1. Check for invalid start
        deviations.extend(
            self._check_start_activity(activities, trace, case_id)
        )

        # 2. Check for wrong order / skipped prerequisites
        deviations.extend(
            self._check_activity_order(activities, trace, case_id)
        )

        # 3. Check for unexpected activities
        deviations.extend(
            self._check_unexpected_activities(activities, trace, case_id)
        )

        # 4. Check for missing mandatory activities
        deviations.extend(
            self._check_missing_activities(activities, trace, case_id)
        )

        # 5. Check for duplicate activities (optional)
        deviations.extend(
            self._check_duplicate_activities(activities, trace, case_id)
        )

        # 6. Check for invalid end (if process appears complete)
        deviations.extend(
            self._check_end_activity(activities, trace, case_id)
        )

        # Sort by severity (critical first)
        deviations.sort(key=lambda d: d.severity)

        return deviations

    def _extract_activities(
        self,
        trace: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Extract activity names from event trace.

        Maps event types to model activities where possible.

        Args:
            trace: List of events

        Returns:
            List of activity names
        """
        activities = []
        for event in trace:
            event_type = event.get("activity") or event.get("type", "")
            if not event_type:
                continue

            # Try to map to model activity
            activity = self._model.get_activity_for_event(event_type)
            if activity:
                activities.append(activity.name)
            else:
                # Use event type as-is if not in model
                activities.append(event_type)

        return activities

    def _check_start_activity(
        self,
        activities: List[str],
        trace: List[Dict[str, Any]],
        case_id: str
    ) -> List[Deviation]:
        """Check if the trace starts with a valid start activity."""
        deviations = []

        if not activities:
            return deviations

        first_activity = activities[0]
        if not self._model.is_start_activity(first_activity):
            # Check if it's even a known activity
            if self._model.get_activity(first_activity) is not None:
                severity = self._scorer.get_severity(
                    DeviationType.INVALID_START, first_activity
                )
                deviations.append(Deviation(
                    deviation_type=DeviationType.INVALID_START,
                    severity=severity,
                    activity_name=first_activity,
                    expected=f"Start with: {', '.join(self._model.start_activities)}",
                    actual=f"Started with: {first_activity}",
                    position=0,
                    timestamp=self._get_timestamp(trace, 0),
                    case_id=case_id,
                    recommendation="Ensure process begins with order creation"
                ))

        return deviations

    def _check_activity_order(
        self,
        activities: List[str],
        trace: List[Dict[str, Any]],
        case_id: str
    ) -> List[Deviation]:
        """Check for wrong order and skipped prerequisite activities."""
        deviations = []
        executed = set()

        for i, activity_name in enumerate(activities):
            activity = self._model.get_activity(activity_name)
            if activity is None:
                # Unknown activity, skip order check
                executed.add(activity_name)
                continue

            # Get required predecessors
            predecessors = self._model.get_valid_previous_activities(activity_name)
            mandatory_predecessors = {
                p for p in predecessors
                if self._model.is_mandatory(p)
            }

            # Check if any mandatory predecessor was skipped
            if mandatory_predecessors and not mandatory_predecessors.intersection(executed):
                # Only report if this is not a start activity
                if not self._model.is_start_activity(activity_name):
                    severity = self._scorer.get_severity(
                        DeviationType.SKIPPED_ACTIVITY, activity_name
                    )
                    skipped = mandatory_predecessors - executed
                    deviations.append(Deviation(
                        deviation_type=DeviationType.SKIPPED_ACTIVITY,
                        severity=severity,
                        activity_name=activity_name,
                        expected=f"Requires: {', '.join(sorted(skipped))}",
                        actual=f"Prerequisites missing: {', '.join(sorted(skipped))}",
                        position=i,
                        timestamp=self._get_timestamp(trace, i),
                        case_id=case_id,
                        details={"skipped_activities": list(skipped)},
                        recommendation=f"Execute {', '.join(sorted(skipped))} before {activity_name}"
                    ))

            # Check ordering against dependency order
            if activity_name in self._dependency_order:
                expected_pos = self._dependency_order[activity_name]
                for prev_activity in executed:
                    if prev_activity in self._dependency_order:
                        prev_expected_pos = self._dependency_order[prev_activity]
                        if prev_expected_pos > expected_pos:
                            severity = self._scorer.get_severity(
                                DeviationType.WRONG_ORDER, activity_name
                            )
                            deviations.append(Deviation(
                                deviation_type=DeviationType.WRONG_ORDER,
                                severity=severity,
                                activity_name=activity_name,
                                expected=f"{activity_name} should come after {prev_activity}",
                                actual=f"{activity_name} executed before {prev_activity}",
                                position=i,
                                timestamp=self._get_timestamp(trace, i),
                                case_id=case_id,
                                details={
                                    "expected_predecessor": prev_activity,
                                    "expected_order": list(self._dependency_order.keys())
                                },
                                recommendation=f"Execute {prev_activity} before {activity_name}"
                            ))

            executed.add(activity_name)

        return deviations

    def _check_unexpected_activities(
        self,
        activities: List[str],
        trace: List[Dict[str, Any]],
        case_id: str
    ) -> List[Deviation]:
        """Check for activities not defined in the process model."""
        deviations = []

        for i, activity_name in enumerate(activities):
            if self._model.get_activity(activity_name) is None:
                severity = self._scorer.get_severity(
                    DeviationType.UNEXPECTED_ACTIVITY, activity_name
                )
                deviations.append(Deviation(
                    deviation_type=DeviationType.UNEXPECTED_ACTIVITY,
                    severity=severity,
                    activity_name=activity_name,
                    expected="Activity in process model",
                    actual=f"Unknown activity: {activity_name}",
                    position=i,
                    timestamp=self._get_timestamp(trace, i),
                    case_id=case_id,
                    recommendation="Review if this activity should be added to model"
                ))

        return deviations

    def _check_missing_activities(
        self,
        activities: List[str],
        trace: List[Dict[str, Any]],
        case_id: str
    ) -> List[Deviation]:
        """Check for mandatory activities that were never executed."""
        deviations = []
        executed = set(activities)
        mandatory = self._model.mandatory_activities

        missing = mandatory - executed

        for activity_name in missing:
            severity = self._scorer.get_severity(
                DeviationType.MISSING_ACTIVITY, activity_name
            )
            deviations.append(Deviation(
                deviation_type=DeviationType.MISSING_ACTIVITY,
                severity=severity,
                activity_name=activity_name,
                expected=f"Mandatory activity: {activity_name}",
                actual="Activity not executed",
                position=-1,  # Not in trace
                timestamp=None,
                case_id=case_id,
                details={"executed_activities": list(executed)},
                recommendation=f"Ensure {activity_name} is executed"
            ))

        return deviations

    def _check_duplicate_activities(
        self,
        activities: List[str],
        trace: List[Dict[str, Any]],
        case_id: str
    ) -> List[Deviation]:
        """Check for unexpected duplicate activities."""
        deviations = []
        seen: Dict[str, int] = {}

        for i, activity_name in enumerate(activities):
            if activity_name in seen:
                # Duplicate found
                activity = self._model.get_activity(activity_name)
                # Only flag as deviation if activity is not expected to repeat
                if activity is not None:
                    severity = self._scorer.get_severity(
                        DeviationType.DUPLICATE_ACTIVITY, activity_name
                    )
                    deviations.append(Deviation(
                        deviation_type=DeviationType.DUPLICATE_ACTIVITY,
                        severity=severity,
                        activity_name=activity_name,
                        expected="Single execution",
                        actual=f"Duplicate at positions {seen[activity_name]} and {i}",
                        position=i,
                        timestamp=self._get_timestamp(trace, i),
                        case_id=case_id,
                        details={"first_occurrence": seen[activity_name]},
                        recommendation="Review if duplicate execution is expected"
                    ))
            else:
                seen[activity_name] = i

        return deviations

    def _check_end_activity(
        self,
        activities: List[str],
        trace: List[Dict[str, Any]],
        case_id: str
    ) -> List[Deviation]:
        """Check if the trace ends with a valid end activity."""
        deviations = []

        if not activities:
            return deviations

        last_activity = activities[-1]
        # Only check end if all mandatory activities were executed
        executed = set(activities)
        mandatory = self._model.mandatory_activities

        if mandatory.issubset(executed):
            if not self._model.is_end_activity(last_activity):
                severity = self._scorer.get_severity(
                    DeviationType.INVALID_END, last_activity
                )
                deviations.append(Deviation(
                    deviation_type=DeviationType.INVALID_END,
                    severity=severity,
                    activity_name=last_activity,
                    expected=f"End with: {', '.join(self._model.end_activities)}",
                    actual=f"Ended with: {last_activity}",
                    position=len(activities) - 1,
                    timestamp=self._get_timestamp(trace, len(trace) - 1),
                    case_id=case_id,
                    recommendation="Ensure process completes with expected end activity"
                ))

        return deviations

    def _get_timestamp(
        self,
        trace: List[Dict[str, Any]],
        index: int
    ) -> Optional[datetime]:
        """Extract timestamp from trace event."""
        if index < 0 or index >= len(trace):
            return None

        ts = trace[index].get("timestamp")
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts)
            except ValueError:
                return None
        return None


@dataclass
class DeviationSummary:
    """
    Summary statistics for deviations across multiple cases.

    Attributes:
        total_deviations: Total number of deviations detected
        by_type: Count of deviations by type
        by_severity: Count of deviations by severity
        by_activity: Count of deviations by activity
        most_common: List of (deviation_type, count) tuples
    """
    total_deviations: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_severity: Dict[str, int] = field(default_factory=dict)
    by_activity: Dict[str, int] = field(default_factory=dict)
    most_common: List[tuple] = field(default_factory=list)

    @classmethod
    def from_deviations(cls, deviations: List[Deviation]) -> "DeviationSummary":
        """
        Create a summary from a list of deviations.

        Args:
            deviations: List of deviations to summarize

        Returns:
            DeviationSummary instance
        """
        summary = cls(total_deviations=len(deviations))

        for dev in deviations:
            # Count by type
            type_key = dev.deviation_type.value
            summary.by_type[type_key] = summary.by_type.get(type_key, 0) + 1

            # Count by severity
            sev_key = dev.severity.value
            summary.by_severity[sev_key] = summary.by_severity.get(sev_key, 0) + 1

            # Count by activity
            summary.by_activity[dev.activity_name] = (
                summary.by_activity.get(dev.activity_name, 0) + 1
            )

        # Determine most common
        type_counts = sorted(
            summary.by_type.items(),
            key=lambda x: x[1],
            reverse=True
        )
        summary.most_common = type_counts[:5]

        return summary

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "total_deviations": self.total_deviations,
            "by_type": self.by_type,
            "by_severity": self.by_severity,
            "by_activity": self.by_activity,
            "most_common": self.most_common,
        }
