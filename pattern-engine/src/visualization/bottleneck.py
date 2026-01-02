"""
Bottleneck Analysis and Color-Coded Highlighting for SAP Process Flows.

Analyzes process transition times to identify bottlenecks based on
cycle time percentiles, providing color-coded performance indicators:
- Green (fast): Below median transition time
- Yellow (medium): Between median and 85th percentile
- Red (slow): Above 85th percentile (bottleneck)

This module supports the SAP Order-to-Cash workflow visualization
by identifying where process delays occur.
"""

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class BottleneckLevel(Enum):
    """Performance level for process transitions."""
    FAST = "fast"       # Green - below median
    MEDIUM = "medium"   # Yellow - between median and 85th percentile
    SLOW = "slow"       # Red - above 85th percentile (bottleneck)


@dataclass
class TransitionMetrics:
    """
    Metrics for a specific transition between two event types.

    Contains timing statistics and bottleneck classification.
    """
    from_event: str
    to_event: str
    count: int
    durations_hours: List[float] = field(default_factory=list)

    # Computed statistics
    mean_hours: float = 0.0
    median_hours: float = 0.0
    std_hours: float = 0.0
    min_hours: float = 0.0
    max_hours: float = 0.0
    p50_hours: float = 0.0
    p85_hours: float = 0.0
    p95_hours: float = 0.0

    # Bottleneck classification
    level: Optional[BottleneckLevel] = None

    def compute_statistics(self) -> None:
        """Compute statistics from durations."""
        if not self.durations_hours:
            return

        sorted_durations = sorted(self.durations_hours)
        n = len(sorted_durations)

        self.mean_hours = sum(sorted_durations) / n
        self.min_hours = sorted_durations[0]
        self.max_hours = sorted_durations[-1]

        # Median (p50)
        if n % 2 == 0:
            self.median_hours = (sorted_durations[n // 2 - 1] + sorted_durations[n // 2]) / 2
        else:
            self.median_hours = sorted_durations[n // 2]

        self.p50_hours = self.median_hours

        # Standard deviation
        if n > 1:
            variance = sum((x - self.mean_hours) ** 2 for x in sorted_durations) / (n - 1)
            self.std_hours = math.sqrt(variance)

        # Percentiles
        self.p85_hours = self._percentile(sorted_durations, 85)
        self.p95_hours = self._percentile(sorted_durations, 95)

    def _percentile(self, sorted_data: List[float], p: int) -> float:
        """Calculate percentile from sorted data."""
        if not sorted_data:
            return 0.0

        n = len(sorted_data)
        k = (n - 1) * p / 100
        f = math.floor(k)
        c = math.ceil(k)

        if f == c:
            return sorted_data[int(k)]

        return sorted_data[int(f)] * (c - k) + sorted_data[int(c)] * (k - f)

    @property
    def mean_days(self) -> float:
        """Mean duration in days."""
        return self.mean_hours / 24.0

    @property
    def median_days(self) -> float:
        """Median duration in days."""
        return self.median_hours / 24.0

    def format_duration(self, hours: float) -> str:
        """Format duration for display."""
        if hours < 1:
            return f"{hours * 60:.0f}m"
        elif hours < 24:
            return f"{hours:.1f}h"
        else:
            days = hours / 24
            if days < 7:
                return f"{days:.1f}d"
            else:
                weeks = days / 7
                return f"{weeks:.1f}w"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "from_event": self.from_event,
            "to_event": self.to_event,
            "count": self.count,
            "mean_hours": self.mean_hours,
            "median_hours": self.median_hours,
            "std_hours": self.std_hours,
            "min_hours": self.min_hours,
            "max_hours": self.max_hours,
            "p50_hours": self.p50_hours,
            "p85_hours": self.p85_hours,
            "p95_hours": self.p95_hours,
            "level": self.level.value if self.level else None,
        }


@dataclass
class BottleneckAnalysis:
    """
    Complete bottleneck analysis results for a process.

    Contains per-transition metrics and overall process statistics.
    """
    transitions: Dict[Tuple[str, str], TransitionMetrics] = field(default_factory=dict)
    transition_levels: Dict[Tuple[str, str], BottleneckLevel] = field(default_factory=dict)

    # Overall process statistics
    total_cases: int = 0
    total_events: int = 0

    # Global percentile thresholds (across all transitions)
    global_p50_hours: float = 0.0
    global_p85_hours: float = 0.0

    # Thresholds used
    medium_percentile: int = 50
    slow_percentile: int = 85

    def get_bottlenecks(self) -> List[TransitionMetrics]:
        """Get all transitions classified as bottlenecks (slow)."""
        return [
            metrics for metrics in self.transitions.values()
            if metrics.level == BottleneckLevel.SLOW
        ]

    def get_summary(self) -> Dict[str, Any]:
        """Get analysis summary."""
        fast_count = sum(1 for m in self.transitions.values() if m.level == BottleneckLevel.FAST)
        medium_count = sum(1 for m in self.transitions.values() if m.level == BottleneckLevel.MEDIUM)
        slow_count = sum(1 for m in self.transitions.values() if m.level == BottleneckLevel.SLOW)

        bottlenecks = self.get_bottlenecks()
        worst_bottleneck = max(bottlenecks, key=lambda m: m.mean_hours) if bottlenecks else None

        return {
            "total_cases": self.total_cases,
            "total_events": self.total_events,
            "total_transitions": len(self.transitions),
            "fast_count": fast_count,
            "medium_count": medium_count,
            "slow_count": slow_count,
            "global_p50_hours": self.global_p50_hours,
            "global_p85_hours": self.global_p85_hours,
            "worst_bottleneck": {
                "transition": f"{worst_bottleneck.from_event} -> {worst_bottleneck.to_event}",
                "mean_duration": worst_bottleneck.format_duration(worst_bottleneck.mean_hours),
            } if worst_bottleneck else None,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "transitions": {
                f"{k[0]}->{k[1]}": v.to_dict()
                for k, v in self.transitions.items()
            },
            "summary": self.get_summary(),
            "thresholds": {
                "medium_percentile": self.medium_percentile,
                "slow_percentile": self.slow_percentile,
                "global_p50_hours": self.global_p50_hours,
                "global_p85_hours": self.global_p85_hours,
            },
        }


class BottleneckAnalyzer:
    """
    Analyzes process transitions to identify bottlenecks.

    Uses percentile-based classification:
    - Fast (green): Duration below the medium_percentile (default: 50th)
    - Medium (yellow): Duration between medium and slow percentile
    - Slow/Bottleneck (red): Duration above slow_percentile (default: 85th)
    """

    def __init__(
        self,
        percentile_thresholds: Tuple[int, int] = (50, 85),
        use_global_thresholds: bool = True,
        min_samples: int = 3,
    ):
        """
        Initialize the bottleneck analyzer.

        Args:
            percentile_thresholds: (medium_percentile, slow_percentile) for classification
            use_global_thresholds: If True, use global thresholds across all transitions;
                                   if False, use per-transition thresholds
            min_samples: Minimum samples required to classify a transition
        """
        self.medium_percentile = percentile_thresholds[0]
        self.slow_percentile = percentile_thresholds[1]
        self.use_global_thresholds = use_global_thresholds
        self.min_samples = min_samples

    def analyze(self, events: List[Dict[str, Any]]) -> BottleneckAnalysis:
        """
        Analyze events to identify bottlenecks.

        Args:
            events: List of event dictionaries with 'type', 'timestamp', 'case_id'

        Returns:
            BottleneckAnalysis with per-transition metrics and classifications
        """
        analysis = BottleneckAnalysis(
            medium_percentile=self.medium_percentile,
            slow_percentile=self.slow_percentile,
        )

        # Group events by case
        cases: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for event in events:
            case_id = event.get("case_id") or event.get("order_id") or event.get("document_number")
            if case_id:
                cases[case_id].append(event)

        analysis.total_cases = len(cases)
        analysis.total_events = len(events)

        if not cases:
            logger.warning("No cases found in events")
            return analysis

        # Sort events within each case by timestamp
        for case_id in cases:
            cases[case_id].sort(key=lambda e: self._parse_timestamp(e.get("timestamp")))

        # Extract all transition durations
        transition_durations: Dict[Tuple[str, str], List[float]] = defaultdict(list)

        for case_id, case_events in cases.items():
            for i in range(len(case_events) - 1):
                from_event = case_events[i]
                to_event = case_events[i + 1]

                from_type = from_event.get("type") or from_event.get("event_type")
                to_type = to_event.get("type") or to_event.get("event_type")

                if not from_type or not to_type:
                    continue

                from_ts = self._parse_timestamp(from_event.get("timestamp") or from_event.get("time"))
                to_ts = self._parse_timestamp(to_event.get("timestamp") or to_event.get("time"))

                if from_ts and to_ts:
                    duration_hours = (to_ts - from_ts).total_seconds() / 3600
                    if duration_hours >= 0:  # Ignore negative durations
                        transition_durations[(from_type, to_type)].append(duration_hours)

        if not transition_durations:
            logger.warning("No valid transitions found")
            return analysis

        # Compute statistics for each transition
        for (from_type, to_type), durations in transition_durations.items():
            metrics = TransitionMetrics(
                from_event=from_type,
                to_event=to_type,
                count=len(durations),
                durations_hours=durations,
            )
            metrics.compute_statistics()
            analysis.transitions[(from_type, to_type)] = metrics

        # Compute global thresholds
        all_durations = []
        for metrics in analysis.transitions.values():
            all_durations.extend(metrics.durations_hours)

        if all_durations:
            sorted_all = sorted(all_durations)
            analysis.global_p50_hours = self._percentile(sorted_all, self.medium_percentile)
            analysis.global_p85_hours = self._percentile(sorted_all, self.slow_percentile)

        # Classify each transition
        for key, metrics in analysis.transitions.items():
            if metrics.count < self.min_samples:
                # Not enough samples for classification
                metrics.level = BottleneckLevel.MEDIUM
                analysis.transition_levels[key] = BottleneckLevel.MEDIUM
                continue

            if self.use_global_thresholds:
                # Use global percentiles
                p50 = analysis.global_p50_hours
                p85 = analysis.global_p85_hours
            else:
                # Use per-transition percentiles
                p50 = metrics.p50_hours
                p85 = metrics.p85_hours

            # Classify based on mean duration
            if metrics.mean_hours <= p50:
                metrics.level = BottleneckLevel.FAST
            elif metrics.mean_hours <= p85:
                metrics.level = BottleneckLevel.MEDIUM
            else:
                metrics.level = BottleneckLevel.SLOW

            analysis.transition_levels[key] = metrics.level

        return analysis

    def _percentile(self, sorted_data: List[float], p: int) -> float:
        """Calculate percentile from sorted data."""
        if not sorted_data:
            return 0.0

        n = len(sorted_data)
        k = (n - 1) * p / 100
        f = math.floor(k)
        c = math.ceil(k)

        if f == c:
            return sorted_data[int(k)]

        return sorted_data[int(f)] * (c - k) + sorted_data[int(c)] * (k - f)

    def _parse_timestamp(self, value: Any) -> Optional[datetime]:
        """Parse a timestamp value into datetime."""
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            formats = [
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(value.split("+")[0].split("Z")[0], fmt)
                except ValueError:
                    continue

        return None


def analyze_bottlenecks(
    events: List[Dict[str, Any]],
    percentile_thresholds: Tuple[int, int] = (50, 85),
    use_global_thresholds: bool = True,
) -> BottleneckAnalysis:
    """
    Convenience function to analyze bottlenecks in event data.

    Args:
        events: List of event dictionaries with 'type', 'timestamp', 'case_id'
        percentile_thresholds: (medium_percentile, slow_percentile) for classification
        use_global_thresholds: If True, use global thresholds across all transitions

    Returns:
        BottleneckAnalysis with per-transition metrics and classifications
    """
    analyzer = BottleneckAnalyzer(
        percentile_thresholds=percentile_thresholds,
        use_global_thresholds=use_global_thresholds,
    )
    return analyzer.analyze(events)


def get_color_for_level(level: BottleneckLevel) -> str:
    """
    Get the hex color code for a bottleneck level.

    Args:
        level: BottleneckLevel enum value

    Returns:
        Hex color code string
    """
    colors = {
        BottleneckLevel.FAST: "#22c55e",     # Green
        BottleneckLevel.MEDIUM: "#eab308",   # Yellow
        BottleneckLevel.SLOW: "#ef4444",     # Red
    }
    return colors.get(level, "#64748b")  # Default gray


def get_level_description(level: BottleneckLevel) -> str:
    """
    Get a human-readable description for a bottleneck level.

    Args:
        level: BottleneckLevel enum value

    Returns:
        Description string
    """
    descriptions = {
        BottleneckLevel.FAST: "Fast - below median cycle time",
        BottleneckLevel.MEDIUM: "Medium - between median and 85th percentile",
        BottleneckLevel.SLOW: "Slow (Bottleneck) - above 85th percentile",
    }
    return descriptions.get(level, "Unknown")
