"""
Configuration settings for SAP SD Synthetic Data Generator.

This module contains all configurable parameters for generating synthetic
SAP Sales & Distribution documents with realistic distributions and patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class GeneratorConfig:
    """Main configuration for the synthetic data generator."""

    # Random seed for reproducibility
    seed: int = 42

    # Output counts
    num_sales_orders: int = 10000
    num_customers: int = 250
    num_materials: int = 100
    num_users: int = 30

    # Organizational structure
    sales_orgs: List[str] = field(default_factory=lambda: [
        "1000", "1100", "1200", "2000", "2100", "3000", "3100", "4000"
    ])

    plants: List[str] = field(default_factory=lambda: [
        "1000", "1100", "1200", "1300", "1400",
        "2000", "2100", "2200",
        "3000", "3100", "3200", "3300",
        "4000", "4100"
    ])

    # Plant to sales org mapping
    plant_sales_org_map: Dict[str, List[str]] = field(default_factory=lambda: {
        "1000": ["1000", "1100", "1200", "1300", "1400"],
        "1100": ["1000", "1100", "1200"],
        "1200": ["1000", "1100", "1200"],
        "2000": ["2000", "2100", "2200"],
        "2100": ["2000", "2100"],
        "3000": ["3000", "3100", "3200", "3300"],
        "3100": ["3000", "3100"],
        "4000": ["4000", "4100"],
    })

    distribution_channels: List[str] = field(default_factory=lambda: ["10", "20", "30"])
    divisions: List[str] = field(default_factory=lambda: ["00", "01", "02", "03"])

    # Document types
    order_types: Dict[str, float] = field(default_factory=lambda: {
        "OR": 0.70,   # Standard Order
        "ZOR": 0.10,  # Custom Standard Order
        "RE": 0.08,   # Return Order
        "CR": 0.05,   # Credit Memo Request
        "DR": 0.04,   # Debit Memo Request
        "SO": 0.03,   # Rush Order
    })

    delivery_types: Dict[str, float] = field(default_factory=lambda: {
        "LF": 0.85,   # Outbound Delivery
        "LO": 0.10,   # Delivery without Reference
        "LR": 0.05,   # Return Delivery
    })

    invoice_types: Dict[str, float] = field(default_factory=lambda: {
        "F2": 0.75,   # Invoice
        "RE": 0.10,   # Credit Memo
        "L2": 0.08,   # Debit Memo
        "S1": 0.05,   # Cancellation
        "IV": 0.02,   # Intercompany Invoice
    })

    # Item counts per document
    items_per_order: Dict[str, float] = field(default_factory=lambda: {
        "1": 0.30,
        "2": 0.25,
        "3": 0.20,
        "4": 0.10,
        "5": 0.08,
        "6-10": 0.05,
        "11-20": 0.02,
    })

    # Delivery split probabilities
    deliveries_per_order: Dict[str, float] = field(default_factory=lambda: {
        "1": 0.70,    # Single delivery
        "2": 0.18,    # Split into 2
        "3": 0.08,    # Split into 3
        "4+": 0.04,   # 4 or more
    })

    # Date range for generation
    start_date: str = "2023-01-01"
    end_date: str = "2024-12-31"

    # Timing distributions (in days)
    timing: Dict[str, Any] = field(default_factory=lambda: {
        # Order to requested delivery date
        "requested_delivery": {
            "mean": 7,
            "std": 3,
            "min": 1,
            "max": 30,
        },
        # Order to actual delivery (normal processing)
        "normal_delivery": {
            "mean": 5,
            "std": 2,
            "min": 1,
            "max": 14,
        },
        # Rush order delivery
        "rush_delivery": {
            "mean": 2,
            "std": 1,
            "min": 0,  # Same day
            "max": 3,
        },
        # Delayed delivery (credit hold, blocked, etc.)
        "delayed_delivery": {
            "mean": 21,
            "std": 10,
            "min": 10,
            "max": 60,
        },
        # Delivery to invoice
        "delivery_to_invoice": {
            "mean": 3,
            "std": 2,
            "min": 0,
            "max": 14,
        },
        # Anomaly rates
        "delay_rate": 0.08,      # 8% significantly delayed
        "same_day_rate": 0.05,   # 5% same-day delivery
        "early_rate": 0.10,      # 10% early delivery
    })


@dataclass
class TextPatternConfig:
    """Configuration for text patterns that correlate with outcomes."""

    # Patterns that cause delays (longer cycle times)
    delay_patterns: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "CREDIT HOLD": {"probability": 0.05, "delay_days": (10, 30), "variants": ["CR HLD", "CREDIT-HOLD", "credit hold", "CRED HOLD"]},
        "WAITING APPROVAL": {"probability": 0.04, "delay_days": (5, 20), "variants": ["WAIT APPR", "PENDING APPROVAL", "AWAITING APPR", "waiting approval"]},
        "HOLD": {"probability": 0.03, "delay_days": (7, 25), "variants": ["ON HOLD", "HELD", "hold", "HLD"]},
        "BLOCKED": {"probability": 0.03, "delay_days": (10, 45), "variants": ["BLK", "BLOCK", "blocked", "BLKD"]},
        "COMPLIANCE REVIEW": {"probability": 0.02, "delay_days": (14, 30), "variants": ["COMPL REV", "COMPLIANCE CHK"]},
        "EXPORT CONTROL": {"probability": 0.01, "delay_days": (21, 60), "variants": ["EXP CTRL", "EXPORT CHK", "ITAR REVIEW"]},
    })

    # Patterns that expedite (shorter cycle times)
    expedite_patterns: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "EXPEDITE": {"probability": 0.06, "reduction_pct": (30, 50), "variants": ["EXP", "EXPED", "expedite", "EXPD"]},
        "RUSH": {"probability": 0.05, "reduction_pct": (40, 60), "variants": ["RUSH ORDER", "rush", "RSH"]},
        "URGENT": {"probability": 0.04, "reduction_pct": (35, 55), "variants": ["URG", "URGNT", "urgent", "PRIORITY"]},
        "HOT": {"probability": 0.02, "reduction_pct": (50, 70), "variants": ["HOT ORDER", "hot", "CRITICAL"]},
        "PRTY": {"probability": 0.03, "reduction_pct": (25, 45), "variants": ["PRIORITY", "HIGH PRIORITY", "PRI"]},
    })

    # Patterns causing multiple deliveries
    split_patterns: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "SHIP PARTIAL": {"probability": 0.08, "extra_deliveries": (1, 3), "variants": ["PARTIAL SHIP", "PART SHIP", "ship partial", "PARTIAL"]},
        "BACKORDER": {"probability": 0.06, "extra_deliveries": (1, 2), "variants": ["BO", "BACK ORDER", "backorder", "B/O"]},
        "SPLIT DELIVERY": {"probability": 0.04, "extra_deliveries": (1, 2), "variants": ["SPLIT DEL", "SPLIT SHIP", "split delivery"]},
        "MULTIPLE SHIP": {"probability": 0.02, "extra_deliveries": (2, 4), "variants": ["MULTI SHIP", "MULT DEL"]},
    })

    # Patterns affecting price
    price_patterns: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "PRICE OVERRIDE": {"probability": 0.05, "price_factor": (1.05, 1.25), "variants": ["PR OVRD", "MANUAL PRICE", "price override", "OVERRIDE"]},
        "MANUAL PRICE": {"probability": 0.04, "price_factor": (0.90, 1.30), "variants": ["MAN PR", "MANUAL", "manual price"]},
        "DISCOUNT": {"probability": 0.08, "price_factor": (0.75, 0.95), "variants": ["DISC", "DSC", "discount", "SPECIAL PRICE"]},
        "SURCHARGE": {"probability": 0.03, "price_factor": (1.05, 1.15), "variants": ["SURCHG", "ADD CHG", "EXTRA CHG"]},
    })

    # Patterns indicating returns/issues
    return_patterns: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "RETURN": {"probability": 0.05, "variants": ["RET", "RTN", "return", "RETURNED"]},
        "RMA": {"probability": 0.04, "variants": ["RMA#", "RMA NUMBER", "rma", "RETURN AUTH"]},
        "DAMAGE": {"probability": 0.03, "variants": ["DMG", "DAMAGED", "damage", "DEFECT"]},
        "QUALITY ISSUE": {"probability": 0.02, "variants": ["QA ISSUE", "QUAL PROB", "quality issue", "QC FAIL"]},
        "WRONG ITEM": {"probability": 0.02, "variants": ["WRONG", "INCORRECT", "WRONG PRODUCT"]},
    })

    # Neutral/noise patterns (common text that doesn't affect outcomes)
    noise_patterns: List[str] = field(default_factory=lambda: [
        "PO#", "REF:", "Customer request", "Standard order",
        "Per agreement", "As discussed", "Follow up", "Confirmed",
        "Phone order", "Web order", "EDI order", "Email order",
        "Scheduled", "Recurring", "Contract", "Blanket order",
        "See attached", "Per quote", "As per", "RE:", "FW:",
        "Updated", "Revised", "Amendment", "Change order",
    ])

    # Probability of having any text note
    text_probability: float = 0.40

    # Probability of noise vs. meaningful pattern when text exists
    noise_vs_meaningful: float = 0.50  # 50% noise, 50% meaningful


@dataclass
class CustomerConfig:
    """Configuration for customer master data generation."""

    regions: List[str] = field(default_factory=lambda: [
        "NORTH", "SOUTH", "EAST", "WEST", "CENTRAL",
        "NORTHEAST", "SOUTHEAST", "NORTHWEST", "SOUTHWEST",
        "INTERNATIONAL"
    ])

    industries: List[str] = field(default_factory=lambda: [
        "MANUFACTURING", "RETAIL", "WHOLESALE", "TECHNOLOGY",
        "HEALTHCARE", "AUTOMOTIVE", "AEROSPACE", "CHEMICALS",
        "CONSUMER_GOODS", "FOOD_BEVERAGE", "PHARMACEUTICAL",
        "ENERGY", "CONSTRUCTION", "LOGISTICS", "GOVERNMENT"
    ])

    tiers: Dict[str, float] = field(default_factory=lambda: {
        "PLATINUM": 0.05,
        "GOLD": 0.15,
        "SILVER": 0.30,
        "BRONZE": 0.50,
    })

    # Order frequency by tier (orders per year per customer average)
    order_frequency_by_tier: Dict[str, Tuple[int, int]] = field(default_factory=lambda: {
        "PLATINUM": (50, 200),
        "GOLD": (20, 80),
        "SILVER": (5, 30),
        "BRONZE": (1, 10),
    })


@dataclass
class MaterialConfig:
    """Configuration for material master data generation."""

    categories: List[str] = field(default_factory=lambda: [
        "FINISHED_GOODS", "SEMI_FINISHED", "RAW_MATERIAL",
        "TRADING_GOODS", "SERVICES", "SPARE_PARTS"
    ])

    product_groups: List[str] = field(default_factory=lambda: [
        "ELECTRONICS", "MECHANICAL", "ELECTRICAL", "HYDRAULIC",
        "PNEUMATIC", "CONSUMABLES", "PACKAGING", "CHEMICALS",
        "COMPONENTS", "ASSEMBLIES", "ACCESSORIES", "TOOLS"
    ])

    # Price ranges by category
    price_ranges: Dict[str, Tuple[float, float]] = field(default_factory=lambda: {
        "FINISHED_GOODS": (100.0, 10000.0),
        "SEMI_FINISHED": (50.0, 5000.0),
        "RAW_MATERIAL": (10.0, 500.0),
        "TRADING_GOODS": (25.0, 2500.0),
        "SERVICES": (50.0, 1000.0),
        "SPARE_PARTS": (5.0, 500.0),
    })

    # Weight ranges (kg)
    weight_ranges: Dict[str, Tuple[float, float]] = field(default_factory=lambda: {
        "FINISHED_GOODS": (0.5, 100.0),
        "SEMI_FINISHED": (1.0, 200.0),
        "RAW_MATERIAL": (0.1, 50.0),
        "TRADING_GOODS": (0.1, 50.0),
        "SERVICES": (0.0, 0.0),
        "SPARE_PARTS": (0.01, 10.0),
    })


@dataclass
class OutputConfig:
    """Configuration for output files."""

    output_dir: str = "sample_output"

    files: Dict[str, str] = field(default_factory=lambda: {
        "sales_orders": "sales_orders.json",
        "deliveries": "deliveries.json",
        "invoices": "invoices.json",
        "doc_flow": "doc_flow.json",
        "customers": "customers.json",
        "materials": "materials.json",
        "users": "users.json",
    })

    # Pretty print JSON
    indent: int = 2

    # Include metadata in output
    include_metadata: bool = True


def get_default_config() -> Dict[str, Any]:
    """Get all default configuration as a dictionary."""
    return {
        "generator": GeneratorConfig(),
        "text_patterns": TextPatternConfig(),
        "customer": CustomerConfig(),
        "material": MaterialConfig(),
        "output": OutputConfig(),
    }


# Preset configurations for different scenarios
PRESETS = {
    "small": {
        "num_sales_orders": 5000,
        "num_customers": 100,
        "num_materials": 50,
        "num_users": 20,
    },
    "medium": {
        "num_sales_orders": 10000,
        "num_customers": 250,
        "num_materials": 100,
        "num_users": 30,
    },
    "large": {
        "num_sales_orders": 25000,
        "num_customers": 400,
        "num_materials": 150,
        "num_users": 40,
    },
    "xlarge": {
        "num_sales_orders": 50000,
        "num_customers": 500,
        "num_materials": 200,
        "num_users": 50,
    },
}


def apply_preset(config: GeneratorConfig, preset_name: str) -> GeneratorConfig:
    """Apply a preset configuration."""
    if preset_name not in PRESETS:
        raise ValueError(f"Unknown preset: {preset_name}. Available: {list(PRESETS.keys())}")

    preset = PRESETS[preset_name]
    for key, value in preset.items():
        setattr(config, key, value)

    return config
