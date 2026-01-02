"""
Feature Extraction for Predictive Process Monitoring.

Extracts features from SAP Order-to-Cash (O2C) process events for use in
predictive models. Features are designed to capture temporal patterns,
process state, and risk indicators that correlate with outcomes like
delays, credit holds, and completion times.

Feature Categories:
- Temporal features: Cycle times, waiting times, time-since-start
- Count features: Number of activities, documents, changes
- Pattern features: Activity sequences, deviation indicators
- State features: Current process stage, completion percentage

References:
- Teinemaa, I., et al. (2019). Outcome-oriented predictive process monitoring.
  ACM TIST, 10(2), 1-57.
- Di Francescomarino, C., et al. (2018). Predictive business process monitoring
  framework with hyperparameter optimization. CAiSE 2018.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)


class FeatureType(Enum):
    """Types of features that can be extracted."""

    TEMPORAL = "temporal"
    COUNT = "count"
    PATTERN = "pattern"
    STATE = "state"
    AGGREGATE = "aggregate"


# Standard O2C activities for feature extraction
O2C_ACTIVITIES = [
    "OrderCreated",
    "OrderChanged",
    "CreditCheck",
    "CreditBlock",
    "CreditRelease",
    "DeliveryCreated",
    "PickingCompleted",
    "GoodsIssued",
    "InvoiceCreated",
    "PaymentReceived",
]

# Activity sequence for progress calculation
O2C_MILESTONE_ORDER = {
    "OrderCreated": 0,
    "CreditCheck": 1,
    "DeliveryCreated": 2,
    "GoodsIssued": 3,
    "InvoiceCreated": 4,
    "PaymentReceived": 5,
}


@dataclass
class FeatureConfig:
    """
    Configuration for feature extraction.

    Attributes:
        include_temporal: Whether to extract temporal features
        include_counts: Whether to extract count features
        include_patterns: Whether to extract pattern features
        include_state: Whether to extract state features
        time_units: Units for time-based features ('hours', 'days', 'minutes')
        max_sequence_length: Maximum activity sequence length to consider
        activity_list: List of activities to track (defaults to O2C_ACTIVITIES)
    """
    include_temporal: bool = True
    include_counts: bool = True
    include_patterns: bool = True
    include_state: bool = True
    time_units: str = "hours"
    max_sequence_length: int = 20
    activity_list: List[str] = field(default_factory=lambda: O2C_ACTIVITIES.copy())

    def get_time_divisor(self) -> float:
        """Get the divisor for converting seconds to configured time units."""
        divisors = {
            "seconds": 1.0,
            "minutes": 60.0,
            "hours": 3600.0,
            "days": 86400.0,
        }
        return divisors.get(self.time_units, 3600.0)


@dataclass
class ExtractedFeatures:
    """
    Container for extracted features from a single case.

    Attributes:
        case_id: Identifier for the process instance
        feature_vector: Numeric feature values as numpy array
        feature_names: Names of features in the vector
        feature_dict: Dictionary mapping feature names to values
        extraction_timestamp: When features were extracted
        metadata: Additional metadata about the extraction
    """
    case_id: str
    feature_vector: np.ndarray
    feature_names: List[str]
    feature_dict: Dict[str, float]
    extraction_timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "case_id": self.case_id,
            "features": self.feature_dict.copy(),
            "extraction_timestamp": self.extraction_timestamp.isoformat(),
            "metadata": self.metadata,
        }

    def get_feature(self, name: str) -> Optional[float]:
        """Get a specific feature value by name."""
        return self.feature_dict.get(name)


class FeatureExtractor:
    """
    Extracts features from SAP O2C process events for predictive modeling.

    Implements feature engineering techniques for process mining, extracting
    features that capture the temporal dynamics, process state, and patterns
    that can predict process outcomes.

    The extractor supports both single-event (prefix) extraction for online
    prediction and full-trace extraction for model training.

    Example:
        from prediction.features import FeatureExtractor, FeatureConfig

        config = FeatureConfig(time_units="hours")
        extractor = FeatureExtractor(config)

        # Extract features from a trace
        trace = [
            {"activity": "OrderCreated", "timestamp": "2024-01-01T10:00:00"},
            {"activity": "DeliveryCreated", "timestamp": "2024-01-02T14:00:00"},
        ]
        features = extractor.extract(trace, case_id="ORDER001")

        # Get feature vector for ML model
        X = features.feature_vector
    """

    def __init__(self, config: Optional[FeatureConfig] = None):
        """
        Initialize the feature extractor.

        Args:
            config: Feature extraction configuration
        """
        self._config = config or FeatureConfig()
        self._feature_names: List[str] = []
        self._build_feature_names()

    def _build_feature_names(self) -> None:
        """Build the list of feature names based on configuration."""
        self._feature_names = []

        if self._config.include_temporal:
            self._feature_names.extend([
                "total_duration",
                "time_since_start",
                "avg_activity_duration",
                "max_activity_duration",
                "min_activity_duration",
                "std_activity_duration",
                "time_to_last_milestone",
            ])

        if self._config.include_counts:
            self._feature_names.extend([
                "event_count",
                "unique_activity_count",
                "order_change_count",
                "credit_block_count",
            ])
            # Add per-activity counts
            for activity in self._config.activity_list:
                self._feature_names.append(f"count_{activity}")

        if self._config.include_patterns:
            self._feature_names.extend([
                "has_credit_block",
                "has_order_changes",
                "rework_count",
                "backward_flow_count",
            ])

        if self._config.include_state:
            self._feature_names.extend([
                "current_stage",
                "completion_percentage",
                "is_blocked",
                "days_in_current_stage",
            ])

    @property
    def feature_names(self) -> List[str]:
        """Get the list of feature names."""
        return self._feature_names.copy()

    @property
    def n_features(self) -> int:
        """Get the number of features."""
        return len(self._feature_names)

    def extract(
        self,
        trace: List[Dict[str, Any]],
        case_id: str = "",
        current_time: Optional[datetime] = None
    ) -> ExtractedFeatures:
        """
        Extract features from an event trace.

        Args:
            trace: List of events with 'activity' and 'timestamp' fields
            case_id: Identifier for the process instance
            current_time: Reference time for time-based calculations
                         (defaults to last event time or now)

        Returns:
            ExtractedFeatures containing the feature vector and metadata
        """
        if not trace:
            return self._empty_features(case_id)

        # Parse timestamps
        events = self._parse_events(trace)
        if not events:
            return self._empty_features(case_id)

        # Determine reference time
        if current_time is None:
            current_time = events[-1]["parsed_timestamp"] or datetime.now()

        feature_dict: Dict[str, float] = {}

        # Extract each feature category
        if self._config.include_temporal:
            feature_dict.update(self._extract_temporal_features(events, current_time))

        if self._config.include_counts:
            feature_dict.update(self._extract_count_features(events))

        if self._config.include_patterns:
            feature_dict.update(self._extract_pattern_features(events))

        if self._config.include_state:
            feature_dict.update(self._extract_state_features(events, current_time))

        # Build feature vector in consistent order
        feature_vector = np.array([
            feature_dict.get(name, 0.0) for name in self._feature_names
        ], dtype=np.float64)

        return ExtractedFeatures(
            case_id=case_id,
            feature_vector=feature_vector,
            feature_names=self._feature_names.copy(),
            feature_dict=feature_dict,
            metadata={
                "event_count": len(events),
                "first_timestamp": events[0]["parsed_timestamp"].isoformat()
                if events[0]["parsed_timestamp"] else None,
                "last_timestamp": events[-1]["parsed_timestamp"].isoformat()
                if events[-1]["parsed_timestamp"] else None,
            }
        )

    def extract_batch(
        self,
        cases: List[Dict[str, Any]],
        case_id_field: str = "case_id",
        events_field: str = "events"
    ) -> Tuple[np.ndarray, List[str], List[ExtractedFeatures]]:
        """
        Extract features from multiple cases.

        Args:
            cases: List of cases with events
            case_id_field: Field name for case ID
            events_field: Field name for events list

        Returns:
            Tuple of (feature_matrix, case_ids, feature_objects)
        """
        all_features: List[ExtractedFeatures] = []
        case_ids: List[str] = []

        for case in cases:
            case_id = str(case.get(case_id_field, f"case_{len(all_features)}"))
            events = case.get(events_field, [])

            features = self.extract(events, case_id)
            all_features.append(features)
            case_ids.append(case_id)

        # Stack feature vectors into matrix
        if all_features:
            feature_matrix = np.vstack([f.feature_vector for f in all_features])
        else:
            feature_matrix = np.zeros((0, self.n_features))

        return feature_matrix, case_ids, all_features

    def _parse_events(
        self,
        trace: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Parse events and add parsed timestamps.

        Args:
            trace: Raw event trace

        Returns:
            Events with 'parsed_timestamp' field added
        """
        events = []
        for event in trace:
            parsed = event.copy()
            parsed["parsed_timestamp"] = self._parse_timestamp(
                event.get("timestamp")
            )
            parsed["activity"] = event.get("activity") or event.get("type", "")
            events.append(parsed)

        # Sort by timestamp if available
        events_with_ts = [e for e in events if e["parsed_timestamp"] is not None]
        if events_with_ts:
            events_with_ts.sort(key=lambda e: e["parsed_timestamp"])
            return events_with_ts

        return events

    def _parse_timestamp(
        self,
        timestamp: Optional[Union[str, datetime]]
    ) -> Optional[datetime]:
        """Parse a timestamp value."""
        if timestamp is None:
            return None
        if isinstance(timestamp, datetime):
            return timestamp
        if isinstance(timestamp, str):
            try:
                return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    def _extract_temporal_features(
        self,
        events: List[Dict[str, Any]],
        current_time: datetime
    ) -> Dict[str, float]:
        """Extract time-based features."""
        features: Dict[str, float] = {}
        divisor = self._config.get_time_divisor()

        # Get timestamps
        timestamps = [
            e["parsed_timestamp"] for e in events
            if e["parsed_timestamp"] is not None
        ]

        if len(timestamps) < 1:
            return {
                "total_duration": 0.0,
                "time_since_start": 0.0,
                "avg_activity_duration": 0.0,
                "max_activity_duration": 0.0,
                "min_activity_duration": 0.0,
                "std_activity_duration": 0.0,
                "time_to_last_milestone": 0.0,
            }

        first_ts = timestamps[0]
        last_ts = timestamps[-1]

        # Total duration (first to last event)
        total_seconds = (last_ts - first_ts).total_seconds()
        features["total_duration"] = total_seconds / divisor

        # Time since start (to current time)
        time_since_start = (current_time - first_ts).total_seconds()
        features["time_since_start"] = time_since_start / divisor

        # Inter-event durations
        if len(timestamps) > 1:
            durations = [
                (timestamps[i] - timestamps[i - 1]).total_seconds()
                for i in range(1, len(timestamps))
            ]
            features["avg_activity_duration"] = np.mean(durations) / divisor
            features["max_activity_duration"] = np.max(durations) / divisor
            features["min_activity_duration"] = np.min(durations) / divisor
            features["std_activity_duration"] = np.std(durations) / divisor
        else:
            features["avg_activity_duration"] = 0.0
            features["max_activity_duration"] = 0.0
            features["min_activity_duration"] = 0.0
            features["std_activity_duration"] = 0.0

        # Time to last milestone
        milestone_time = self._get_last_milestone_time(events)
        if milestone_time:
            features["time_to_last_milestone"] = (
                (milestone_time - first_ts).total_seconds() / divisor
            )
        else:
            features["time_to_last_milestone"] = 0.0

        return features

    def _extract_count_features(
        self,
        events: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Extract count-based features."""
        features: Dict[str, float] = {}

        activities = [e["activity"] for e in events]

        # Basic counts
        features["event_count"] = float(len(events))
        features["unique_activity_count"] = float(len(set(activities)))

        # Specific activity counts
        features["order_change_count"] = float(
            sum(1 for a in activities if a == "OrderChanged")
        )
        features["credit_block_count"] = float(
            sum(1 for a in activities if a == "CreditBlock")
        )

        # Per-activity counts
        activity_counts = {}
        for activity in activities:
            activity_counts[activity] = activity_counts.get(activity, 0) + 1

        for activity in self._config.activity_list:
            features[f"count_{activity}"] = float(activity_counts.get(activity, 0))

        return features

    def _extract_pattern_features(
        self,
        events: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Extract pattern-based features."""
        features: Dict[str, float] = {}

        activities = [e["activity"] for e in events]
        activity_set = set(activities)

        # Binary pattern indicators
        features["has_credit_block"] = float("CreditBlock" in activity_set)
        features["has_order_changes"] = float("OrderChanged" in activity_set)

        # Rework detection (activity executed more than once)
        activity_counts = {}
        for activity in activities:
            activity_counts[activity] = activity_counts.get(activity, 0) + 1
        features["rework_count"] = float(
            sum(1 for count in activity_counts.values() if count > 1)
        )

        # Backward flow detection
        backward_count = 0
        for i in range(1, len(activities)):
            prev_activity = activities[i - 1]
            curr_activity = activities[i]
            prev_order = O2C_MILESTONE_ORDER.get(prev_activity, -1)
            curr_order = O2C_MILESTONE_ORDER.get(curr_activity, -1)
            if prev_order >= 0 and curr_order >= 0 and curr_order < prev_order:
                backward_count += 1
        features["backward_flow_count"] = float(backward_count)

        return features

    def _extract_state_features(
        self,
        events: List[Dict[str, Any]],
        current_time: datetime
    ) -> Dict[str, float]:
        """Extract state-based features."""
        features: Dict[str, float] = {}

        activities = [e["activity"] for e in events]
        activity_set = set(activities)

        # Current stage (highest milestone reached)
        current_stage = 0
        for activity in activities:
            stage = O2C_MILESTONE_ORDER.get(activity, -1)
            if stage > current_stage:
                current_stage = stage
        features["current_stage"] = float(current_stage)

        # Completion percentage
        max_stage = max(O2C_MILESTONE_ORDER.values())
        features["completion_percentage"] = (current_stage / max_stage) * 100.0

        # Is blocked (has credit block without release)
        has_block = "CreditBlock" in activity_set
        has_release = "CreditRelease" in activity_set
        features["is_blocked"] = float(has_block and not has_release)

        # Days in current stage
        last_milestone_time = self._get_last_milestone_time(events)
        if last_milestone_time:
            days_in_stage = (current_time - last_milestone_time).total_seconds() / 86400.0
            features["days_in_current_stage"] = days_in_stage
        else:
            features["days_in_current_stage"] = 0.0

        return features

    def _get_last_milestone_time(
        self,
        events: List[Dict[str, Any]]
    ) -> Optional[datetime]:
        """Get the timestamp of the last milestone activity."""
        last_milestone_time = None
        for event in events:
            if event["activity"] in O2C_MILESTONE_ORDER:
                if event["parsed_timestamp"]:
                    last_milestone_time = event["parsed_timestamp"]
        return last_milestone_time

    def _empty_features(self, case_id: str) -> ExtractedFeatures:
        """Create an empty feature set."""
        return ExtractedFeatures(
            case_id=case_id,
            feature_vector=np.zeros(self.n_features, dtype=np.float64),
            feature_names=self._feature_names.copy(),
            feature_dict={name: 0.0 for name in self._feature_names},
            metadata={"empty": True}
        )


def extract_features(
    trace: List[Dict[str, Any]],
    case_id: str = "",
    config: Optional[FeatureConfig] = None
) -> ExtractedFeatures:
    """
    Convenience function to extract features from a trace.

    Args:
        trace: List of events with 'activity' and 'timestamp' fields
        case_id: Identifier for the process instance
        config: Feature extraction configuration

    Returns:
        ExtractedFeatures containing the feature vector and metadata
    """
    extractor = FeatureExtractor(config)
    return extractor.extract(trace, case_id)


def extract_features_batch(
    cases: List[Dict[str, Any]],
    config: Optional[FeatureConfig] = None
) -> Tuple[np.ndarray, List[str]]:
    """
    Convenience function to extract features from multiple cases.

    Args:
        cases: List of cases with 'case_id' and 'events' fields
        config: Feature extraction configuration

    Returns:
        Tuple of (feature_matrix, case_ids)
    """
    extractor = FeatureExtractor(config)
    matrix, case_ids, _ = extractor.extract_batch(cases)
    return matrix, case_ids
