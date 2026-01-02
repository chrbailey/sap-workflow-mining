"""
GraphViz DOT Format Generation for SAP Process Graphs.

Generates DOT-format graphs for complex process visualization,
supporting SAP Order-to-Cash workflows with timing annotations,
bottleneck highlighting, and SVG output.

GraphViz provides more control over layout and styling than Mermaid,
making it suitable for complex process models and publications.

Output example:
    digraph ProcessFlow {
        rankdir=LR;
        node [shape=box, style=rounded];

        OrderCreated [label="Order Created"];
        DeliveryCreated [label="Delivery Created"];

        OrderCreated -> DeliveryCreated [label="2.5 days", color="#22c55e"];
    }
"""

import logging
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
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
    "OrderCreated": "Order\\nCreated",
    "OrderChanged": "Order\\nChanged",
    "OrderReleased": "Order\\nReleased",
    "DeliveryCreated": "Delivery\\nCreated",
    "GoodsIssued": "Goods\\nIssued",
    "InvoiceCreated": "Invoice\\nCreated",
    "InvoicePosted": "Invoice\\nPosted",
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


class GraphVizGenerator:
    """
    Generates GraphViz DOT format diagrams from event sequences.

    Supports:
    - DOT format output for GraphViz
    - SVG rendering (requires graphviz installation)
    - Timing annotations on edges
    - Color-coded bottleneck highlighting
    - Customizable node and edge styles
    """

    # Color definitions for bottleneck levels
    BOTTLENECK_COLORS = {
        "fast": "#22c55e",     # Green
        "medium": "#eab308",   # Yellow
        "slow": "#ef4444",     # Red
    }

    # Pen widths for bottleneck levels
    BOTTLENECK_PENWIDTHS = {
        "fast": "1.5",
        "medium": "2.5",
        "slow": "3.5",
    }

    def __init__(
        self,
        rankdir: str = "LR",
        node_shape: str = "box",
        node_style: str = "rounded,filled",
        node_fillcolor: str = "#f8fafc",
        node_fontname: str = "Arial",
        edge_fontname: str = "Arial",
        edge_fontsize: str = "10",
    ):
        """
        Initialize the GraphViz generator.

        Args:
            rankdir: Graph direction - 'LR', 'TB', 'RL', 'BT'
            node_shape: Node shape (box, ellipse, diamond, etc.)
            node_style: Node style (rounded, filled, etc.)
            node_fillcolor: Default node fill color
            node_fontname: Font for node labels
            edge_fontname: Font for edge labels
            edge_fontsize: Font size for edge labels
        """
        self.rankdir = rankdir
        self.node_shape = node_shape
        self.node_style = node_style
        self.node_fillcolor = node_fillcolor
        self.node_fontname = node_fontname
        self.edge_fontname = edge_fontname
        self.edge_fontsize = edge_fontsize

    def generate(
        self,
        events: List[Dict[str, Any]],
        include_timing: bool = True,
        bottleneck_analysis: Optional["BottleneckAnalysis"] = None,
        title: Optional[str] = None,
        graph_name: str = "ProcessFlow",
    ) -> str:
        """
        Generate a DOT format graph from event sequences.

        Args:
            events: List of event dictionaries with 'type', 'timestamp', 'case_id'
            include_timing: Include timing annotations on edges
            bottleneck_analysis: Optional bottleneck analysis for color coding
            title: Optional title for the graph
            graph_name: Name of the digraph

        Returns:
            DOT format string
        """
        # Extract transitions from events
        transitions = self._extract_transitions(events)

        if not transitions:
            logger.warning("No transitions found in events")
            return self._empty_graph(title, graph_name)

        # Build the DOT graph
        lines = []
        lines.append(f"digraph {graph_name} {{")

        # Graph attributes
        lines.append(f"    rankdir={self.rankdir};")
        lines.append(f"    bgcolor=white;")
        lines.append(f"    margin=0.5;")

        if title:
            lines.append(f'    label="{title}";')
            lines.append("    labelloc=t;")
            lines.append("    fontsize=16;")
            lines.append(f"    fontname=\"{self.node_fontname}\";")

        lines.append("")

        # Node defaults
        lines.append(f"    node [")
        lines.append(f"        shape={self.node_shape},")
        lines.append(f"        style=\"{self.node_style}\",")
        lines.append(f"        fillcolor=\"{self.node_fillcolor}\",")
        lines.append(f"        fontname=\"{self.node_fontname}\",")
        lines.append(f"        fontsize=11,")
        lines.append(f"        margin=\"0.2,0.1\"")
        lines.append(f"    ];")
        lines.append("")

        # Edge defaults
        lines.append(f"    edge [")
        lines.append(f"        fontname=\"{self.edge_fontname}\",")
        lines.append(f"        fontsize={self.edge_fontsize},")
        lines.append(f"        color=\"#64748b\"")
        lines.append(f"    ];")
        lines.append("")

        # Collect all unique nodes
        nodes = set()
        for trans in transitions.values():
            nodes.add(trans.from_event)
            nodes.add(trans.to_event)

        # Define nodes
        for node in sorted(nodes, key=lambda x: SAP_O2C_EVENT_ORDER.index(x) if x in SAP_O2C_EVENT_ORDER else 999):
            label = EVENT_LABELS.get(node, node.replace("_", "\\n"))
            lines.append(f'    {node} [label="{label}"];')

        lines.append("")

        # Add edges with timing and styling
        for (from_event, to_event), trans in sorted(
            transitions.items(),
            key=lambda x: (
                SAP_O2C_EVENT_ORDER.index(x[0][0]) if x[0][0] in SAP_O2C_EVENT_ORDER else 999,
                SAP_O2C_EVENT_ORDER.index(x[0][1]) if x[0][1] in SAP_O2C_EVENT_ORDER else 999,
            )
        ):
            edge_attrs = []

            # Build edge label
            label_parts = []
            if include_timing and trans.durations:
                label_parts.append(trans.format_duration())

            if trans.count > 1:
                label_parts.append(f"n={trans.count}")

            if label_parts:
                edge_attrs.append(f'label="{", ".join(label_parts)}"')

            # Determine bottleneck level for styling
            if bottleneck_analysis:
                key = (from_event, to_event)
                if key in bottleneck_analysis.transition_levels:
                    level = bottleneck_analysis.transition_levels[key]
                    color = self.BOTTLENECK_COLORS.get(level.value, "#64748b")
                    penwidth = self.BOTTLENECK_PENWIDTHS.get(level.value, "1.5")
                    edge_attrs.append(f'color="{color}"')
                    edge_attrs.append(f'penwidth={penwidth}')
                    edge_attrs.append(f'fontcolor="{color}"')

            # Build edge definition
            if edge_attrs:
                attrs_str = ", ".join(edge_attrs)
                lines.append(f"    {from_event} -> {to_event} [{attrs_str}];")
            else:
                lines.append(f"    {from_event} -> {to_event};")

        lines.append("}")

        return "\n".join(lines)

    def generate_svg(
        self,
        events: List[Dict[str, Any]],
        include_timing: bool = True,
        bottleneck_analysis: Optional["BottleneckAnalysis"] = None,
        title: Optional[str] = None,
        graph_name: str = "ProcessFlow",
    ) -> str:
        """
        Generate an SVG diagram from event sequences.

        Requires graphviz to be installed on the system.

        Args:
            events: List of event dictionaries
            include_timing: Include timing annotations
            bottleneck_analysis: Optional bottleneck analysis
            title: Optional title
            graph_name: Name of the digraph

        Returns:
            SVG string

        Raises:
            RuntimeError: If graphviz is not installed or fails
        """
        dot_code = self.generate(
            events,
            include_timing=include_timing,
            bottleneck_analysis=bottleneck_analysis,
            title=title,
            graph_name=graph_name,
        )

        return self._render_svg(dot_code)

    def _render_svg(self, dot_code: str) -> str:
        """
        Render DOT code to SVG using graphviz.

        Args:
            dot_code: DOT format string

        Returns:
            SVG string

        Raises:
            RuntimeError: If graphviz is not available or rendering fails
        """
        try:
            # Try using the 'dot' command
            result = subprocess.run(
                ["dot", "-Tsvg"],
                input=dot_code.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )

            if result.returncode != 0:
                error_msg = result.stderr.decode("utf-8", errors="replace")
                raise RuntimeError(f"GraphViz dot command failed: {error_msg}")

            return result.stdout.decode("utf-8")

        except FileNotFoundError:
            logger.error("GraphViz 'dot' command not found. Install graphviz to render SVG.")
            raise RuntimeError(
                "GraphViz is not installed. Install it with:\n"
                "  - macOS: brew install graphviz\n"
                "  - Ubuntu: apt-get install graphviz\n"
                "  - Windows: choco install graphviz"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("GraphViz rendering timed out")

    def save_svg(
        self,
        events: List[Dict[str, Any]],
        output_path: str,
        include_timing: bool = True,
        bottleneck_analysis: Optional["BottleneckAnalysis"] = None,
        title: Optional[str] = None,
    ) -> Path:
        """
        Generate and save an SVG diagram to a file.

        Args:
            events: List of event dictionaries
            output_path: Path to save the SVG file
            include_timing: Include timing annotations
            bottleneck_analysis: Optional bottleneck analysis
            title: Optional title

        Returns:
            Path to the created file
        """
        svg_content = self.generate_svg(
            events,
            include_timing=include_timing,
            bottleneck_analysis=bottleneck_analysis,
            title=title,
        )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

        logger.info(f"Saved SVG diagram to: {output_path}")
        return output_path

    def _extract_transitions(
        self,
        events: List[Dict[str, Any]]
    ) -> Dict[Tuple[str, str], TransitionInfo]:
        """
        Extract transitions between event types from event sequences.

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
                    if duration_hours >= 0:
                        transitions[key].durations.append(duration_hours)

        return transitions

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

    def _empty_graph(self, title: Optional[str], graph_name: str) -> str:
        """Generate an empty graph placeholder."""
        lines = [f"digraph {graph_name} {{"]
        lines.append(f"    rankdir={self.rankdir};")
        if title:
            lines.append(f'    label="{title}";')
            lines.append("    labelloc=t;")
        lines.append('    NoData [label="No process data available", shape=box, style="rounded,filled", fillcolor="#fef2f2"];')
        lines.append("}")
        return "\n".join(lines)


def generate_dot_diagram(
    events: List[Dict[str, Any]],
    include_timing: bool = True,
    include_bottlenecks: bool = False,
    rankdir: str = "LR",
    title: Optional[str] = None,
    percentile_thresholds: Tuple[int, int] = (50, 85),
) -> str:
    """
    Convenience function to generate a DOT format diagram.

    Args:
        events: List of event dictionaries with 'type', 'timestamp', 'case_id'
        include_timing: Include timing annotations on edges
        include_bottlenecks: Analyze and highlight bottlenecks
        rankdir: Graph direction ('LR', 'TB', 'RL', 'BT')
        title: Optional diagram title
        percentile_thresholds: Percentile thresholds for bottleneck coloring

    Returns:
        DOT format string
    """
    bottleneck_analysis = None

    if include_bottlenecks:
        from .bottleneck import BottleneckAnalyzer
        analyzer = BottleneckAnalyzer(percentile_thresholds=percentile_thresholds)
        bottleneck_analysis = analyzer.analyze(events)

    generator = GraphVizGenerator(rankdir=rankdir)
    return generator.generate(
        events,
        include_timing=include_timing,
        bottleneck_analysis=bottleneck_analysis,
        title=title,
    )


def generate_svg_diagram(
    events: List[Dict[str, Any]],
    include_timing: bool = True,
    include_bottlenecks: bool = False,
    rankdir: str = "LR",
    title: Optional[str] = None,
    percentile_thresholds: Tuple[int, int] = (50, 85),
) -> str:
    """
    Convenience function to generate an SVG diagram.

    Requires graphviz to be installed on the system.

    Args:
        events: List of event dictionaries with 'type', 'timestamp', 'case_id'
        include_timing: Include timing annotations on edges
        include_bottlenecks: Analyze and highlight bottlenecks
        rankdir: Graph direction ('LR', 'TB', 'RL', 'BT')
        title: Optional diagram title
        percentile_thresholds: Percentile thresholds for bottleneck coloring

    Returns:
        SVG string
    """
    bottleneck_analysis = None

    if include_bottlenecks:
        from .bottleneck import BottleneckAnalyzer
        analyzer = BottleneckAnalyzer(percentile_thresholds=percentile_thresholds)
        bottleneck_analysis = analyzer.analyze(events)

    generator = GraphVizGenerator(rankdir=rankdir)
    return generator.generate_svg(
        events,
        include_timing=include_timing,
        bottleneck_analysis=bottleneck_analysis,
        title=title,
    )
