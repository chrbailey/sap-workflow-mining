"""
Mermaid Flowchart Diagram Generation for SAP Process Flows.

Generates Mermaid-compatible markdown for process flow visualization,
supporting SAP Order-to-Cash workflows with timing annotations and
bottleneck highlighting.

Mermaid is a Markdown-based diagramming tool that renders in GitHub,
GitLab, and many documentation platforms.

Output example:
    ```mermaid
    flowchart LR
        OrderCreated[Order Created] --> |2.5 days| DeliveryCreated[Delivery Created]
        DeliveryCreated --> |1.2 days| GoodsIssued[Goods Issued]
        GoodsIssued --> |0.8 days| InvoiceCreated[Invoice Created]
    ```
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .bottleneck import BottleneckAnalysis, BottleneckLevel

logger = logging.getLogger(__name__)


# SAP O2C standard event flow order
SAP_O2C_EVENT_ORDER = [
    "OrderCreated",
    "OrderChanged",
    "OrderReleased",
    "DeliveryCreated",
    "GoodsIssued",
    "InvoiceCreated",
    "InvoicePosted",
]

# Human-readable labels for event types
EVENT_LABELS = {
    "OrderCreated": "Order Created",
    "OrderChanged": "Order Changed",
    "OrderReleased": "Order Released",
    "DeliveryCreated": "Delivery Created",
    "GoodsIssued": "Goods Issued",
    "InvoiceCreated": "Invoice Created",
    "InvoicePosted": "Invoice Posted",
}


@dataclass
class TransitionInfo:
    """Information about a transition between two event types."""
    from_event: str
    to_event: str
    durations: List[float] = field(default_factory=list)
    count: int = 0

    @property
    def avg_duration_hours(self) -> float:
        """Average duration in hours."""
        if not self.durations:
            return 0.0
        return sum(self.durations) / len(self.durations)

    @property
    def avg_duration_days(self) -> float:
        """Average duration in days."""
        return self.avg_duration_hours / 24.0

    def format_duration(self) -> str:
        """Format duration for display."""
        hours = self.avg_duration_hours
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


class MermaidGenerator:
    """
    Generates Mermaid flowchart diagrams from event sequences.

    Supports:
    - Automatic discovery of event transitions
    - Timing annotations on edges
    - Color-coded bottleneck highlighting
    - SAP O2C flow optimization
    """

    # Mermaid color styles for bottleneck levels
    BOTTLENECK_STYLES = {
        "fast": "stroke:#22c55e,stroke-width:2px",      # Green
        "medium": "stroke:#eab308,stroke-width:3px",    # Yellow
        "slow": "stroke:#ef4444,stroke-width:4px",      # Red
    }

    def __init__(
        self,
        direction: str = "LR",
        theme: str = "default",
    ):
        """
        Initialize the Mermaid generator.

        Args:
            direction: Flow direction - 'LR' (left-right), 'TB' (top-bottom),
                      'RL' (right-left), 'BT' (bottom-top)
            theme: Mermaid theme to use
        """
        self.direction = direction
        self.theme = theme

    def generate(
        self,
        events: List[Dict[str, Any]],
        include_timing: bool = True,
        bottleneck_analysis: Optional["BottleneckAnalysis"] = None,
        title: Optional[str] = None,
    ) -> str:
        """
        Generate a Mermaid flowchart from event sequences.

        Args:
            events: List of event dictionaries with 'type', 'timestamp', 'case_id'
            include_timing: Include timing annotations on edges
            bottleneck_analysis: Optional bottleneck analysis for color coding
            title: Optional title for the diagram

        Returns:
            Mermaid markdown string
        """
        # Extract transitions from events
        transitions = self._extract_transitions(events)

        if not transitions:
            logger.warning("No transitions found in events")
            return self._empty_diagram(title)

        # Build the diagram
        lines = []

        # Add title if provided
        if title:
            lines.append(f"---")
            lines.append(f"title: {title}")
            lines.append(f"---")

        # Start flowchart
        lines.append(f"flowchart {self.direction}")

        # Collect all unique nodes
        nodes = set()
        for trans in transitions.values():
            nodes.add(trans.from_event)
            nodes.add(trans.to_event)

        # Define node shapes (rounded rectangles for events)
        for node in sorted(nodes, key=lambda x: SAP_O2C_EVENT_ORDER.index(x) if x in SAP_O2C_EVENT_ORDER else 999):
            label = EVENT_LABELS.get(node, node.replace("_", " "))
            lines.append(f"    {node}([{label}])")

        lines.append("")

        # Add edges with timing and styling
        style_definitions = []
        link_index = 0

        for (from_event, to_event), trans in sorted(
            transitions.items(),
            key=lambda x: (
                SAP_O2C_EVENT_ORDER.index(x[0][0]) if x[0][0] in SAP_O2C_EVENT_ORDER else 999,
                SAP_O2C_EVENT_ORDER.index(x[0][1]) if x[0][1] in SAP_O2C_EVENT_ORDER else 999,
            )
        ):
            # Build edge label
            edge_parts = []
            if include_timing and trans.durations:
                edge_parts.append(trans.format_duration())

            if trans.count > 1:
                edge_parts.append(f"n={trans.count}")

            edge_label = ", ".join(edge_parts) if edge_parts else ""

            # Determine bottleneck level for styling
            bottleneck_level = None
            if bottleneck_analysis:
                key = (from_event, to_event)
                if key in bottleneck_analysis.transition_levels:
                    bottleneck_level = bottleneck_analysis.transition_levels[key]

            # Add the edge
            if edge_label:
                lines.append(f"    {from_event} --> |{edge_label}| {to_event}")
            else:
                lines.append(f"    {from_event} --> {to_event}")

            # Add style for bottleneck coloring
            if bottleneck_level:
                style = self.BOTTLENECK_STYLES.get(bottleneck_level.value, "")
                if style:
                    style_definitions.append(f"    linkStyle {link_index} {style}")

            link_index += 1

        # Add style definitions
        if style_definitions:
            lines.append("")
            lines.extend(style_definitions)

        return "\n".join(lines)

    def generate_with_code_block(
        self,
        events: List[Dict[str, Any]],
        include_timing: bool = True,
        bottleneck_analysis: Optional["BottleneckAnalysis"] = None,
        title: Optional[str] = None,
    ) -> str:
        """
        Generate Mermaid diagram wrapped in markdown code block.

        Args:
            events: List of event dictionaries
            include_timing: Include timing annotations
            bottleneck_analysis: Optional bottleneck analysis
            title: Optional title

        Returns:
            Mermaid markdown with code block fences
        """
        diagram = self.generate(
            events,
            include_timing=include_timing,
            bottleneck_analysis=bottleneck_analysis,
            title=title,
        )
        return f"```mermaid\n{diagram}\n```"

    def _extract_transitions(
        self,
        events: List[Dict[str, Any]]
    ) -> Dict[Tuple[str, str], TransitionInfo]:
        """
        Extract transitions between event types from event sequences.

        Groups events by case_id and finds consecutive event pairs.

        Args:
            events: List of event dictionaries

        Returns:
            Dictionary mapping (from_event, to_event) to TransitionInfo
        """
        # Group events by case
        cases: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for event in events:
            case_id = event.get("case_id") or event.get("order_id") or event.get("document_number")
            if case_id:
                cases[case_id].append(event)

        # Sort events within each case by timestamp
        for case_id in cases:
            cases[case_id].sort(key=lambda e: self._parse_timestamp(e.get("timestamp")))

        # Extract transitions
        transitions: Dict[Tuple[str, str], TransitionInfo] = {}

        for case_id, case_events in cases.items():
            for i in range(len(case_events) - 1):
                from_event = case_events[i]
                to_event = case_events[i + 1]

                from_type = from_event.get("type") or from_event.get("event_type")
                to_type = to_event.get("type") or to_event.get("event_type")

                if not from_type or not to_type:
                    continue

                key = (from_type, to_type)

                if key not in transitions:
                    transitions[key] = TransitionInfo(from_event=from_type, to_event=to_type)

                transitions[key].count += 1

                # Calculate duration if timestamps available
                from_ts = self._parse_timestamp(from_event.get("timestamp") or from_event.get("time"))
                to_ts = self._parse_timestamp(to_event.get("timestamp") or to_event.get("time"))

                if from_ts and to_ts:
                    duration_hours = (to_ts - from_ts).total_seconds() / 3600
                    if duration_hours >= 0:  # Ignore negative durations
                        transitions[key].durations.append(duration_hours)

        return transitions

    def _parse_timestamp(self, value: Any) -> Optional[datetime]:
        """Parse a timestamp value into datetime."""
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            # Try common formats
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

    def _empty_diagram(self, title: Optional[str] = None) -> str:
        """Generate an empty diagram placeholder."""
        lines = []
        if title:
            lines.append(f"---")
            lines.append(f"title: {title}")
            lines.append(f"---")
        lines.append(f"flowchart {self.direction}")
        lines.append("    NoData([No process data available])")
        return "\n".join(lines)


def generate_mermaid_diagram(
    events: List[Dict[str, Any]],
    include_timing: bool = True,
    include_bottlenecks: bool = False,
    direction: str = "LR",
    title: Optional[str] = None,
    percentile_thresholds: Tuple[int, int] = (50, 85),
) -> str:
    """
    Convenience function to generate a Mermaid diagram.

    Args:
        events: List of event dictionaries with 'type', 'timestamp', 'case_id'
        include_timing: Include timing annotations on edges
        include_bottlenecks: Analyze and highlight bottlenecks
        direction: Flow direction ('LR', 'TB', 'RL', 'BT')
        title: Optional diagram title
        percentile_thresholds: Percentile thresholds for bottleneck coloring

    Returns:
        Mermaid markdown string
    """
    bottleneck_analysis = None

    if include_bottlenecks:
        from .bottleneck import BottleneckAnalyzer
        analyzer = BottleneckAnalyzer(percentile_thresholds=percentile_thresholds)
        bottleneck_analysis = analyzer.analyze(events)

    generator = MermaidGenerator(direction=direction)
    return generator.generate(
        events,
        include_timing=include_timing,
        bottleneck_analysis=bottleneck_analysis,
        title=title,
    )
