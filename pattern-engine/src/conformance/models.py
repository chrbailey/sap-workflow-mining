"""
Process Model Definitions for Conformance Checking.

Provides state machine-based process models that define expected execution paths
for SAP business processes. These models follow established process mining theory,
particularly:

- Van der Aalst, W.M.P. (2016). Process Mining: Data Science in Action
- Rozinat, A., & van der Aalst, W.M.P. (2008). Conformance checking of
  processes based on monitoring real behavior

Process models are defined as directed graphs where:
- Nodes represent activities (events/states)
- Edges represent valid transitions between activities
- Each model captures the expected sequence(s) of activities

Key concepts:
- Activity: A discrete unit of work in a process (e.g., "OrderCreated")
- Transition: A valid progression from one activity to another
- State: Current position in the process model
- Path: A sequence of activities representing one execution trace
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple


class ActivityType(Enum):
    """Classification of activities in a process model."""

    START = "start"          # Process initiation activity
    END = "end"              # Process completion activity
    INTERMEDIATE = "intermediate"  # Middle activity
    MILESTONE = "milestone"  # Key checkpoint activity
    OPTIONAL = "optional"    # Activity that may be skipped


@dataclass(frozen=True)
class Activity:
    """
    An activity in a process model.

    Represents a discrete unit of work that can occur during process execution.
    Activities are immutable to ensure model integrity.

    Attributes:
        name: Unique identifier for the activity
        display_name: Human-readable name
        activity_type: Classification of the activity
        sap_event_types: SAP event types that map to this activity
        description: Optional description of the activity
    """
    name: str
    display_name: str
    activity_type: ActivityType
    sap_event_types: FrozenSet[str] = field(default_factory=frozenset)
    description: str = ""

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Activity):
            return self.name == other.name
        return False

    def matches_event(self, event_type: str) -> bool:
        """
        Check if an event type matches this activity.

        Args:
            event_type: The event type to check

        Returns:
            True if the event matches this activity
        """
        if not self.sap_event_types:
            # If no SAP events defined, match by name
            return event_type == self.name
        return event_type in self.sap_event_types


@dataclass(frozen=True)
class Transition:
    """
    A valid transition between two activities.

    Represents an edge in the process model graph. Transitions can be
    mandatory (must occur) or optional (may be skipped).

    Attributes:
        source: The source activity
        target: The target activity
        is_mandatory: Whether this transition must be taken
        condition: Optional condition for the transition
    """
    source: Activity
    target: Activity
    is_mandatory: bool = True
    condition: str = ""

    def __hash__(self) -> int:
        return hash((self.source.name, self.target.name))


@dataclass
class ProcessState:
    """
    Current state during process execution.

    Tracks which activities have been executed and the current position
    in the process model.

    Attributes:
        current_activity: The most recently executed activity
        executed_activities: Set of all executed activity names
        execution_sequence: Ordered list of executed activities
    """
    current_activity: Optional[Activity] = None
    executed_activities: Set[str] = field(default_factory=set)
    execution_sequence: List[str] = field(default_factory=list)

    def execute(self, activity: Activity) -> None:
        """
        Record execution of an activity.

        Args:
            activity: The activity being executed
        """
        self.current_activity = activity
        self.executed_activities.add(activity.name)
        self.execution_sequence.append(activity.name)

    def has_executed(self, activity_name: str) -> bool:
        """
        Check if an activity has been executed.

        Args:
            activity_name: Name of the activity

        Returns:
            True if the activity has been executed
        """
        return activity_name in self.executed_activities

    def get_position(self, activity_name: str) -> int:
        """
        Get the position of an activity in the execution sequence.

        Args:
            activity_name: Name of the activity

        Returns:
            Position index, or -1 if not found
        """
        try:
            return self.execution_sequence.index(activity_name)
        except ValueError:
            return -1


class ProcessModel:
    """
    A process model defining expected execution behavior.

    Implements a state machine representation of a business process.
    The model defines which activities can occur and in what order,
    enabling conformance checking against actual event logs.

    The model supports:
    - Sequential flows (A -> B -> C)
    - Parallel activities (activities that can occur in any order)
    - Optional activities (activities that may be skipped)
    - Mandatory activities (activities that must occur)

    Attributes:
        name: Unique identifier for the process model
        display_name: Human-readable name
        description: Description of the process
        version: Model version string
    """

    def __init__(
        self,
        name: str,
        display_name: str,
        description: str = "",
        version: str = "1.0.0"
    ):
        """
        Initialize a process model.

        Args:
            name: Unique identifier for the process model
            display_name: Human-readable name
            description: Description of the process
            version: Model version string
        """
        self.name = name
        self.display_name = display_name
        self.description = description
        self.version = version

        self._activities: Dict[str, Activity] = {}
        self._transitions: List[Transition] = []
        self._start_activities: Set[str] = set()
        self._end_activities: Set[str] = set()
        self._mandatory_activities: Set[str] = set()

        # Build adjacency lists for efficient traversal
        self._outgoing: Dict[str, Set[str]] = {}
        self._incoming: Dict[str, Set[str]] = {}

    def add_activity(self, activity: Activity) -> None:
        """
        Add an activity to the process model.

        Args:
            activity: The activity to add
        """
        self._activities[activity.name] = activity

        if activity.name not in self._outgoing:
            self._outgoing[activity.name] = set()
        if activity.name not in self._incoming:
            self._incoming[activity.name] = set()

        if activity.activity_type == ActivityType.START:
            self._start_activities.add(activity.name)
        elif activity.activity_type == ActivityType.END:
            self._end_activities.add(activity.name)

        if activity.activity_type != ActivityType.OPTIONAL:
            self._mandatory_activities.add(activity.name)

    def add_transition(self, transition: Transition) -> None:
        """
        Add a transition between activities.

        Args:
            transition: The transition to add

        Raises:
            ValueError: If source or target activity not in model
        """
        if transition.source.name not in self._activities:
            raise ValueError(
                f"Source activity '{transition.source.name}' not in model"
            )
        if transition.target.name not in self._activities:
            raise ValueError(
                f"Target activity '{transition.target.name}' not in model"
            )

        self._transitions.append(transition)
        self._outgoing[transition.source.name].add(transition.target.name)
        self._incoming[transition.target.name].add(transition.source.name)

    def get_activity(self, name: str) -> Optional[Activity]:
        """
        Get an activity by name.

        Args:
            name: Activity name

        Returns:
            The activity, or None if not found
        """
        return self._activities.get(name)

    def get_activity_for_event(self, event_type: str) -> Optional[Activity]:
        """
        Find the activity that matches an event type.

        Args:
            event_type: The event type to match

        Returns:
            The matching activity, or None if not found
        """
        for activity in self._activities.values():
            if activity.matches_event(event_type):
                return activity
        return None

    def get_valid_next_activities(self, activity_name: str) -> Set[str]:
        """
        Get activities that can follow the given activity.

        Args:
            activity_name: Name of the current activity

        Returns:
            Set of valid successor activity names
        """
        return self._outgoing.get(activity_name, set())

    def get_valid_previous_activities(self, activity_name: str) -> Set[str]:
        """
        Get activities that can precede the given activity.

        Args:
            activity_name: Name of the current activity

        Returns:
            Set of valid predecessor activity names
        """
        return self._incoming.get(activity_name, set())

    def is_valid_transition(self, from_activity: str, to_activity: str) -> bool:
        """
        Check if a transition between activities is valid.

        Args:
            from_activity: Source activity name
            to_activity: Target activity name

        Returns:
            True if the transition is valid
        """
        return to_activity in self._outgoing.get(from_activity, set())

    def is_start_activity(self, activity_name: str) -> bool:
        """
        Check if an activity is a valid start activity.

        Args:
            activity_name: Activity name

        Returns:
            True if the activity can start the process
        """
        return activity_name in self._start_activities

    def is_end_activity(self, activity_name: str) -> bool:
        """
        Check if an activity is a valid end activity.

        Args:
            activity_name: Activity name

        Returns:
            True if the activity can end the process
        """
        return activity_name in self._end_activities

    def is_mandatory(self, activity_name: str) -> bool:
        """
        Check if an activity is mandatory.

        Args:
            activity_name: Activity name

        Returns:
            True if the activity must be executed
        """
        return activity_name in self._mandatory_activities

    @property
    def activities(self) -> Dict[str, Activity]:
        """Get all activities in the model."""
        return self._activities.copy()

    @property
    def transitions(self) -> List[Transition]:
        """Get all transitions in the model."""
        return self._transitions.copy()

    @property
    def start_activities(self) -> Set[str]:
        """Get start activity names."""
        return self._start_activities.copy()

    @property
    def end_activities(self) -> Set[str]:
        """Get end activity names."""
        return self._end_activities.copy()

    @property
    def mandatory_activities(self) -> Set[str]:
        """Get mandatory activity names."""
        return self._mandatory_activities.copy()

    def get_expected_sequence(self) -> List[str]:
        """
        Get the expected sequence of mandatory activities.

        Returns a topologically sorted list of mandatory activities
        representing the expected execution order.

        Returns:
            List of activity names in expected order
        """
        # Perform topological sort on mandatory activities
        visited = set()
        result = []

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)

            for predecessor in self._incoming.get(name, set()):
                if predecessor in self._mandatory_activities:
                    visit(predecessor)

            if name in self._mandatory_activities:
                result.append(name)

        for end in self._end_activities:
            visit(end)

        return result

    def get_dependency_order(self) -> Dict[str, int]:
        """
        Get the dependency order for all activities.

        Returns a mapping from activity name to its order position,
        where activities that must come earlier have lower values.

        Returns:
            Dictionary mapping activity names to order positions
        """
        sequence = self.get_expected_sequence()
        return {name: idx for idx, name in enumerate(sequence)}

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the process model to a dictionary representation.

        Returns:
            Dictionary representation of the model
        """
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "version": self.version,
            "activities": [
                {
                    "name": a.name,
                    "display_name": a.display_name,
                    "type": a.activity_type.value,
                    "sap_event_types": list(a.sap_event_types),
                    "description": a.description,
                }
                for a in self._activities.values()
            ],
            "transitions": [
                {
                    "source": t.source.name,
                    "target": t.target.name,
                    "is_mandatory": t.is_mandatory,
                    "condition": t.condition,
                }
                for t in self._transitions
            ],
            "start_activities": list(self._start_activities),
            "end_activities": list(self._end_activities),
            "mandatory_activities": list(self._mandatory_activities),
        }


class ProcessModelBuilder:
    """
    Builder for constructing process models.

    Provides a fluent interface for building process models,
    making it easier to define complex process structures.

    Example:
        model = (ProcessModelBuilder("o2c", "Order to Cash")
            .add_activity("OrderCreated", "Order Created", ActivityType.START)
            .add_activity("DeliveryCreated", "Delivery Created")
            .add_activity("GoodsIssued", "Goods Issued")
            .add_activity("InvoiceCreated", "Invoice Created", ActivityType.END)
            .add_sequence(["OrderCreated", "DeliveryCreated",
                          "GoodsIssued", "InvoiceCreated"])
            .build())
    """

    def __init__(
        self,
        name: str,
        display_name: str,
        description: str = "",
        version: str = "1.0.0"
    ):
        """
        Initialize the builder.

        Args:
            name: Process model name
            display_name: Human-readable name
            description: Description of the process
            version: Model version string
        """
        self._model = ProcessModel(name, display_name, description, version)
        self._activities: Dict[str, Activity] = {}

    def add_activity(
        self,
        name: str,
        display_name: str,
        activity_type: ActivityType = ActivityType.INTERMEDIATE,
        sap_event_types: Optional[List[str]] = None,
        description: str = ""
    ) -> "ProcessModelBuilder":
        """
        Add an activity to the model.

        Args:
            name: Activity name
            display_name: Human-readable name
            activity_type: Type of activity
            sap_event_types: SAP event types that map to this activity
            description: Activity description

        Returns:
            Self for method chaining
        """
        activity = Activity(
            name=name,
            display_name=display_name,
            activity_type=activity_type,
            sap_event_types=frozenset(sap_event_types or []),
            description=description
        )
        self._activities[name] = activity
        self._model.add_activity(activity)
        return self

    def add_transition(
        self,
        source_name: str,
        target_name: str,
        is_mandatory: bool = True,
        condition: str = ""
    ) -> "ProcessModelBuilder":
        """
        Add a transition between activities.

        Args:
            source_name: Source activity name
            target_name: Target activity name
            is_mandatory: Whether the transition is mandatory
            condition: Optional condition string

        Returns:
            Self for method chaining
        """
        source = self._activities.get(source_name)
        target = self._activities.get(target_name)

        if source is None:
            raise ValueError(f"Source activity '{source_name}' not defined")
        if target is None:
            raise ValueError(f"Target activity '{target_name}' not defined")

        transition = Transition(
            source=source,
            target=target,
            is_mandatory=is_mandatory,
            condition=condition
        )
        self._model.add_transition(transition)
        return self

    def add_sequence(
        self,
        activity_names: List[str],
        is_mandatory: bool = True
    ) -> "ProcessModelBuilder":
        """
        Add a sequence of transitions.

        Creates transitions connecting activities in order:
        A -> B -> C

        Args:
            activity_names: List of activity names in order
            is_mandatory: Whether transitions are mandatory

        Returns:
            Self for method chaining
        """
        for i in range(len(activity_names) - 1):
            self.add_transition(
                activity_names[i],
                activity_names[i + 1],
                is_mandatory
            )
        return self

    def add_parallel_activities(
        self,
        predecessor: str,
        parallel_activities: List[str],
        successor: str
    ) -> "ProcessModelBuilder":
        """
        Add parallel activities that can occur in any order.

        Creates a structure where all parallel activities can follow
        the predecessor and all can precede the successor.

        Args:
            predecessor: Activity before the parallel block
            parallel_activities: Activities that can occur in parallel
            successor: Activity after the parallel block

        Returns:
            Self for method chaining
        """
        for activity in parallel_activities:
            self.add_transition(predecessor, activity)
            self.add_transition(activity, successor)

        # Allow transitions between parallel activities
        for i, act1 in enumerate(parallel_activities):
            for act2 in parallel_activities[i + 1:]:
                self.add_transition(act1, act2, is_mandatory=False)
                self.add_transition(act2, act1, is_mandatory=False)

        return self

    def build(self) -> ProcessModel:
        """
        Build and return the process model.

        Returns:
            The constructed ProcessModel
        """
        return self._model
