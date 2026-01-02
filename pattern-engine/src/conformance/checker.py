"""
Conformance Checking Engine for SAP Process Mining.

Compares actual event logs against expected process models to measure
conformance and identify deviations. Implements industry-standard
conformance checking algorithms.

Key metrics computed:
- Fitness: How well the log can be replayed on the model (0.0 - 1.0)
- Precision: How much behavior allowed by model is in log (0.0 - 1.0)
- Conformance Rate: Percentage of fully conformant cases (0.0 - 100.0%)

References:
- van der Aalst, W.M.P. (2016). Process Mining: Data Science in Action.
  Springer. Chapter 8: Conformance Checking.
- Rozinat, A., & van der Aalst, W.M.P. (2008). Conformance checking of
  processes based on monitoring real behavior. Information Systems, 33(1).
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from .deviations import (
    Deviation,
    DeviationDetector,
    DeviationSummary,
    DeviationType,
    Severity,
    SeverityScorer,
)
from .models import ProcessModel, ProcessState

logger = logging.getLogger(__name__)


@dataclass
class CaseConformanceResult:
    """
    Conformance checking result for a single case (process instance).

    Attributes:
        case_id: Identifier for the process instance
        is_conformant: True if no critical/major deviations
        is_fully_conformant: True if no deviations at all
        fitness_score: How well the trace fits the model (0.0 - 1.0)
        deviations: List of detected deviations
        executed_activities: Activities that were executed
        expected_activities: Activities that should have been executed
        trace_length: Number of events in the trace
        conformance_percentage: Fitness score as percentage (0.0 - 100.0)
    """
    case_id: str
    is_conformant: bool
    is_fully_conformant: bool
    fitness_score: float
    deviations: List[Deviation]
    executed_activities: List[str]
    expected_activities: List[str]
    trace_length: int
    conformance_percentage: float = 0.0

    def __post_init__(self):
        self.conformance_percentage = self.fitness_score * 100.0

    @property
    def critical_deviations(self) -> List[Deviation]:
        """Get critical severity deviations."""
        return [d for d in self.deviations if d.severity == Severity.CRITICAL]

    @property
    def major_deviations(self) -> List[Deviation]:
        """Get major severity deviations."""
        return [d for d in self.deviations if d.severity == Severity.MAJOR]

    @property
    def minor_deviations(self) -> List[Deviation]:
        """Get minor severity deviations."""
        return [d for d in self.deviations if d.severity == Severity.MINOR]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "case_id": self.case_id,
            "is_conformant": self.is_conformant,
            "is_fully_conformant": self.is_fully_conformant,
            "fitness_score": self.fitness_score,
            "conformance_percentage": self.conformance_percentage,
            "deviation_count": len(self.deviations),
            "critical_count": len(self.critical_deviations),
            "major_count": len(self.major_deviations),
            "minor_count": len(self.minor_deviations),
            "deviations": [d.to_dict() for d in self.deviations],
            "executed_activities": self.executed_activities,
            "expected_activities": self.expected_activities,
            "trace_length": self.trace_length,
        }


@dataclass
class ConformanceResult:
    """
    Aggregated conformance checking results across all cases.

    Attributes:
        model_name: Name of the process model used
        total_cases: Total number of cases analyzed
        conformant_cases: Number of cases with acceptable conformance
        fully_conformant_cases: Number of cases with perfect conformance
        conformance_rate: Percentage of conformant cases (0.0 - 100.0)
        full_conformance_rate: Percentage of fully conformant cases
        average_fitness: Mean fitness score across all cases
        min_fitness: Minimum fitness score observed
        max_fitness: Maximum fitness score observed
        total_deviations: Total deviations across all cases
        deviation_summary: Summary statistics for deviations
        case_results: Individual results for each case
        analysis_timestamp: When the analysis was performed
    """
    model_name: str
    total_cases: int
    conformant_cases: int
    fully_conformant_cases: int
    conformance_rate: float
    full_conformance_rate: float
    average_fitness: float
    min_fitness: float
    max_fitness: float
    total_deviations: int
    deviation_summary: DeviationSummary
    case_results: List[CaseConformanceResult]
    analysis_timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "model_name": self.model_name,
            "total_cases": self.total_cases,
            "conformant_cases": self.conformant_cases,
            "fully_conformant_cases": self.fully_conformant_cases,
            "conformance_rate": self.conformance_rate,
            "full_conformance_rate": self.full_conformance_rate,
            "average_fitness": self.average_fitness,
            "min_fitness": self.min_fitness,
            "max_fitness": self.max_fitness,
            "total_deviations": self.total_deviations,
            "deviation_summary": self.deviation_summary.to_dict(),
            "analysis_timestamp": self.analysis_timestamp.isoformat(),
            "case_results": [r.to_dict() for r in self.case_results],
        }

    def get_non_conformant_cases(self) -> List[CaseConformanceResult]:
        """Get cases that are not conformant."""
        return [r for r in self.case_results if not r.is_conformant]

    def get_cases_by_fitness(
        self,
        min_fitness: float = 0.0,
        max_fitness: float = 1.0
    ) -> List[CaseConformanceResult]:
        """Get cases within a fitness range."""
        return [
            r for r in self.case_results
            if min_fitness <= r.fitness_score <= max_fitness
        ]


class ConformanceChecker:
    """
    Main conformance checking engine.

    Compares actual event logs against expected process models,
    computing fitness scores and detecting deviations.

    The checker implements token-based replay with deviation detection:
    1. For each case (trace), replay events against the model
    2. Track which activities were executed and in what order
    3. Detect deviations from expected behavior
    4. Calculate fitness based on alignment quality

    Fitness calculation:
    - Perfect trace: 1.0
    - Each deviation reduces fitness based on severity
    - Critical deviation: -0.3
    - Major deviation: -0.15
    - Minor deviation: -0.05

    Example:
        from conformance import ConformanceChecker
        from conformance.templates.order_to_cash import get_o2c_model

        model = get_o2c_model()
        checker = ConformanceChecker(model)

        # Check a single trace
        trace = [
            {"activity": "OrderCreated", "timestamp": "2024-01-01T10:00:00"},
            {"activity": "DeliveryCreated", "timestamp": "2024-01-02T10:00:00"},
            {"activity": "GoodsIssued", "timestamp": "2024-01-03T10:00:00"},
            {"activity": "InvoiceCreated", "timestamp": "2024-01-04T10:00:00"},
        ]
        result = checker.check_trace(trace, case_id="CASE001")

        # Check multiple cases
        event_log = [
            {"case_id": "001", "events": [...]},
            {"case_id": "002", "events": [...]},
        ]
        results = checker.check_log(event_log)
    """

    # Fitness penalty weights by severity
    SEVERITY_PENALTIES = {
        Severity.CRITICAL: 0.30,
        Severity.MAJOR: 0.15,
        Severity.MINOR: 0.05,
        Severity.INFO: 0.01,
    }

    def __init__(
        self,
        model: ProcessModel,
        severity_scorer: Optional[SeverityScorer] = None,
        strict_mode: bool = False
    ):
        """
        Initialize the conformance checker.

        Args:
            model: The process model to check against
            severity_scorer: Custom severity scoring (uses default if None)
            strict_mode: If True, any deviation makes case non-conformant
        """
        self._model = model
        self._scorer = severity_scorer or SeverityScorer()
        self._detector = DeviationDetector(model, self._scorer)
        self._strict_mode = strict_mode

    @property
    def model(self) -> ProcessModel:
        """Get the process model."""
        return self._model

    def check_trace(
        self,
        trace: List[Dict[str, Any]],
        case_id: str = ""
    ) -> CaseConformanceResult:
        """
        Check conformance of a single event trace.

        Args:
            trace: List of events with 'activity' and optional 'timestamp'
            case_id: Identifier for the process instance

        Returns:
            CaseConformanceResult with conformance details
        """
        # Detect deviations
        deviations = self._detector.detect_deviations(trace, case_id)

        # Extract executed activities
        executed = self._extract_activities(trace)

        # Get expected activities
        expected = self._model.get_expected_sequence()

        # Calculate fitness score
        fitness = self._calculate_fitness(deviations)

        # Determine conformance status
        if self._strict_mode:
            is_conformant = len(deviations) == 0
        else:
            # Conformant if no critical deviations
            critical_count = sum(
                1 for d in deviations
                if d.severity == Severity.CRITICAL
            )
            is_conformant = critical_count == 0

        is_fully_conformant = len(deviations) == 0

        return CaseConformanceResult(
            case_id=case_id,
            is_conformant=is_conformant,
            is_fully_conformant=is_fully_conformant,
            fitness_score=fitness,
            deviations=deviations,
            executed_activities=executed,
            expected_activities=expected,
            trace_length=len(trace)
        )

    def check_log(
        self,
        event_log: List[Dict[str, Any]],
        case_id_field: str = "case_id",
        events_field: str = "events"
    ) -> ConformanceResult:
        """
        Check conformance of an entire event log.

        The event log should be a list of cases, where each case has
        a case ID and a list of events.

        Args:
            event_log: List of cases with events
            case_id_field: Field name for case ID
            events_field: Field name for events list

        Returns:
            ConformanceResult with aggregated statistics
        """
        case_results = []
        all_deviations = []

        for case in event_log:
            case_id = str(case.get(case_id_field, f"case_{len(case_results)}"))
            events = case.get(events_field, [])

            if not events:
                logger.debug(f"Skipping empty case: {case_id}")
                continue

            result = self.check_trace(events, case_id)
            case_results.append(result)
            all_deviations.extend(result.deviations)

        # Calculate aggregated statistics
        return self._aggregate_results(case_results, all_deviations)

    def check_flat_log(
        self,
        events: List[Dict[str, Any]],
        case_id_field: str = "case_id",
        activity_field: str = "activity",
        timestamp_field: str = "timestamp"
    ) -> ConformanceResult:
        """
        Check conformance of a flat event log.

        A flat log has all events in a single list, with case IDs
        identifying which case each event belongs to.

        Args:
            events: List of all events
            case_id_field: Field name for case ID
            activity_field: Field name for activity
            timestamp_field: Field name for timestamp

        Returns:
            ConformanceResult with aggregated statistics
        """
        # Group events by case
        cases: Dict[str, List[Dict[str, Any]]] = {}

        for event in events:
            case_id = str(event.get(case_id_field, "unknown"))
            if case_id not in cases:
                cases[case_id] = []
            cases[case_id].append({
                "activity": event.get(activity_field),
                "timestamp": event.get(timestamp_field),
                **{k: v for k, v in event.items()
                   if k not in [case_id_field, activity_field, timestamp_field]}
            })

        # Sort events within each case by timestamp
        for case_id, case_events in cases.items():
            case_events.sort(
                key=lambda e: e.get("timestamp") or datetime.min
            )

        # Convert to structured log format
        event_log = [
            {"case_id": case_id, "events": events}
            for case_id, events in cases.items()
        ]

        return self.check_log(event_log)

    def _extract_activities(self, trace: List[Dict[str, Any]]) -> List[str]:
        """Extract activity names from a trace."""
        activities = []
        for event in trace:
            activity = event.get("activity") or event.get("type", "")
            if activity:
                # Map to model activity if possible
                model_activity = self._model.get_activity_for_event(activity)
                if model_activity:
                    activities.append(model_activity.name)
                else:
                    activities.append(activity)
        return activities

    def _calculate_fitness(self, deviations: List[Deviation]) -> float:
        """
        Calculate fitness score based on deviations.

        Fitness starts at 1.0 (perfect) and is reduced by each deviation
        based on its severity. The minimum fitness is 0.0.

        Args:
            deviations: List of detected deviations

        Returns:
            Fitness score between 0.0 and 1.0
        """
        if not deviations:
            return 1.0

        total_penalty = 0.0
        for deviation in deviations:
            penalty = self.SEVERITY_PENALTIES.get(deviation.severity, 0.1)
            total_penalty += penalty

        # Fitness cannot go below 0
        fitness = max(0.0, 1.0 - total_penalty)
        return round(fitness, 4)

    def _aggregate_results(
        self,
        case_results: List[CaseConformanceResult],
        all_deviations: List[Deviation]
    ) -> ConformanceResult:
        """
        Aggregate individual case results into overall statistics.

        Args:
            case_results: List of individual case results
            all_deviations: All deviations from all cases

        Returns:
            Aggregated ConformanceResult
        """
        if not case_results:
            return ConformanceResult(
                model_name=self._model.name,
                total_cases=0,
                conformant_cases=0,
                fully_conformant_cases=0,
                conformance_rate=0.0,
                full_conformance_rate=0.0,
                average_fitness=0.0,
                min_fitness=0.0,
                max_fitness=0.0,
                total_deviations=0,
                deviation_summary=DeviationSummary(),
                case_results=[]
            )

        total_cases = len(case_results)
        conformant_cases = sum(1 for r in case_results if r.is_conformant)
        fully_conformant_cases = sum(1 for r in case_results if r.is_fully_conformant)

        fitness_scores = [r.fitness_score for r in case_results]
        average_fitness = sum(fitness_scores) / len(fitness_scores)

        conformance_rate = (conformant_cases / total_cases) * 100.0
        full_conformance_rate = (fully_conformant_cases / total_cases) * 100.0

        return ConformanceResult(
            model_name=self._model.name,
            total_cases=total_cases,
            conformant_cases=conformant_cases,
            fully_conformant_cases=fully_conformant_cases,
            conformance_rate=round(conformance_rate, 2),
            full_conformance_rate=round(full_conformance_rate, 2),
            average_fitness=round(average_fitness, 4),
            min_fitness=round(min(fitness_scores), 4),
            max_fitness=round(max(fitness_scores), 4),
            total_deviations=len(all_deviations),
            deviation_summary=DeviationSummary.from_deviations(all_deviations),
            case_results=case_results
        )


def check_conformance(
    event_log: List[Dict[str, Any]],
    model: ProcessModel,
    strict_mode: bool = False
) -> ConformanceResult:
    """
    Convenience function to check conformance of an event log.

    Args:
        event_log: List of cases with events
        model: Process model to check against
        strict_mode: If True, any deviation makes case non-conformant

    Returns:
        ConformanceResult with analysis results
    """
    checker = ConformanceChecker(model, strict_mode=strict_mode)
    return checker.check_log(event_log)


def calculate_conformance_rate(
    event_log: List[Dict[str, Any]],
    model: ProcessModel
) -> float:
    """
    Calculate the conformance rate for an event log.

    Returns the percentage of cases that are conformant (no critical
    deviations) as a value between 0.0 and 100.0.

    Args:
        event_log: List of cases with events
        model: Process model to check against

    Returns:
        Conformance rate as percentage (0.0 - 100.0)
    """
    result = check_conformance(event_log, model)
    return result.conformance_rate
