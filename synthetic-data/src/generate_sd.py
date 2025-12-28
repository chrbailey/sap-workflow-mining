#!/usr/bin/env python3
"""
SAP SD (Sales & Distribution) Synthetic Data Generator

Generates realistic synthetic data for SAP SD documents including:
- Sales Orders (VA01-style): VBAK header + VBAP items
- Deliveries (VL01N-style): LIKP header + LIPS items
- Invoices (VF01-style): VBRK header + VBRP items
- Document Flow (VBFA-style)
- Master Data (Customers, Materials, Users)

The generator creates complete document flow chains with realistic timing,
text patterns that correlate with outcomes, and proper organizational structure.

Usage:
    python src/generate_sd.py --count 10000 --output sample_output/ --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from faker import Faker


# =============================================================================
# TEXT PATTERNS CONFIGURATION
# =============================================================================

# Patterns that cause delays (longer cycle times)
DELAY_PATTERNS = {
    "HOLD": {
        "probability": 0.05,
        "delay_days": (10, 20),
        "variants": ["CREDIT HOLD", "hold for credit", "CR HLD", "CRED HOLD", "HLD", "ON HOLD"],
    },
    "BACKORDER": {
        "probability": 0.07,
        "delay_days": (15, 25),
        "variants": ["out of stock", "BO", "B/O", "BACK ORDER", "backorder", "OUT OF STK"],
    },
    "BLOCKED": {
        "probability": 0.03,
        "delay_days": (10, 30),
        "variants": ["BLK", "BLOCK", "blocked", "BLKD"],
    },
    "COMPLIANCE REVIEW": {
        "probability": 0.02,
        "delay_days": (14, 30),
        "variants": ["COMPL REV", "COMPLIANCE CHK"],
    },
}

# Patterns that expedite (shorter cycle times)
EXPEDITE_PATTERNS = {
    "EXPEDITE": {
        "probability": 0.08,
        "reduction_days": 2,
        "variants": ["EXP", "EXPED", "expedite", "EXPD", "EXPDT"],
    },
    "RUSH": {
        "probability": 0.05,
        "reduction_days": 3,
        "variants": ["RUSH ORDER", "rush", "RSH", "URGENT"],
    },
    "urgent": {
        "probability": 0.04,
        "reduction_days": 2,
        "variants": ["URG", "URGNT", "PRIORITY", "HOT"],
    },
}

# Patterns causing multiple deliveries
SPLIT_PATTERNS = {
    "SHIP PARTIAL": {
        "probability": 0.06,
        "extra_deliveries": (1, 2),
        "variants": ["PARTIAL SHIP", "partial shipment ok", "PART SHIP", "PARTIAL"],
    },
    "SPLIT DELIVERY": {
        "probability": 0.03,
        "extra_deliveries": (1, 2),
        "variants": ["SPLIT DEL", "SPLIT SHIP", "split delivery"],
    },
}

# Patterns affecting price
PRICE_PATTERNS = {
    "PRICE OVERRIDE": {
        "probability": 0.04,
        "price_factor": (1.10, 1.30),
        "variants": ["special pricing", "MANUAL PRICE", "PR OVRD", "OVERRIDE"],
    },
    "DISCOUNT": {
        "probability": 0.05,
        "price_factor": (0.80, 0.95),
        "variants": ["DISC", "DSC", "discount", "SPECIAL PRICE"],
    },
}

# Patterns indicating returns/issues
RETURN_PATTERNS = {
    "RETURN DUE TO DAMAGE": {
        "probability": 0.03,
        "variants": ["damaged goods", "DMG", "DAMAGED", "DEFECT", "damage"],
    },
    "RMA": {
        "probability": 0.02,
        "variants": ["RMA#", "RETURN AUTH", "rma"],
    },
}

# Neutral/noise patterns
NOISE_PATTERNS = [
    "CUSTOMER REQUEST", "per customer", "CUST REQ", "Customer request",
    "PO#", "REF:", "Standard order", "Per agreement", "As discussed",
    "Follow up", "Confirmed", "Phone order", "Web order", "EDI order",
    "Scheduled", "Recurring", "Contract", "See attached", "Per quote",
    "Updated", "Revised", "Amendment", "custmer request",  # typo intentional
    "CUSTMER REQ", "cust request",  # abbreviations and typos
]

# =============================================================================
# PRICING CONDITION CONFIGURATION (KONV)
# =============================================================================

# Standard SAP SD pricing procedure condition types
# Order follows typical SD pricing procedure (e.g., RVAA01)
PRICING_PROCEDURE = [
    # Step, Counter, CondType, Description, CalcType, FromStep, ToStep, Required, ManualPct
    (10, 0, "PR00", "Price", "C", None, None, True, 0.0),  # Base price from material/customer
    (20, 0, "K004", "Material Discount %", "A", 10, None, False, 0.15),  # % off PR00
    (30, 0, "K007", "Customer Discount %", "A", 10, None, False, 0.20),  # Customer-specific discount
    (40, 0, "K020", "Price Group Discount", "A", 10, None, False, 0.10),  # Price group discount
    (50, 0, "RA00", "Rebate Basis", "A", 10, None, False, 0.05),  # Rebate accrual
    (100, 0, "KF00", "Freight", "B", None, None, False, 0.30),  # Fixed freight cost
    (200, 0, "SKTO", "Cash Discount Basis", "X", 10, 100, False, 0.0),  # Subtotal
    (300, 0, "MWST", "Output Tax", "A", 200, None, True, 0.0),  # VAT/Tax
    (400, 0, "HD00", "Header Discount", "A", None, None, False, 0.08),  # Header-level discount
    (500, 0, "AMIW", "Min Value Surcharge", "B", None, None, False, 0.02),  # Minimum order surcharge
    (900, 0, "NETW", "Net Value", "X", None, None, True, 0.0),  # Final subtotal
]

# Manual override conditions (ZPR0, ZK01) - applied when PRICE OVERRIDE pattern present
MANUAL_PRICING_CONDITIONS = [
    (35, 1, "ZPR0", "Manual Price Override", "B", None, None),  # Fixed price override
    (45, 1, "ZK01", "Manual Discount", "A", 10, None),  # Manual % discount
]

# Tax rates by sales organization
TAX_RATES = {
    "1000": 0.0875,   # US - varies by state, using avg
    "2000": 0.19,     # EU - German VAT
    "3000": 0.10,     # APAC - Singapore GST
}

# =============================================================================
# ORGANIZATIONAL DATA
# =============================================================================

SALES_ORGS = {
    "1000": {"name": "US Sales", "region": "US", "currency": "USD"},
    "2000": {"name": "EU Sales", "region": "EU", "currency": "EUR"},
    "3000": {"name": "APAC Sales", "region": "APAC", "currency": "USD"},
}

PLANTS = {
    "1000": {"name": "US Main Plant", "sales_org": "1000"},
    "1100": {"name": "US Distribution", "sales_org": "1000"},
    "2000": {"name": "EU Manufacturing", "sales_org": "2000"},
    "3000": {"name": "APAC Hub", "sales_org": "3000"},
}

PLANT_TO_SALES_ORG = {
    "1000": ["1000", "1100"],
    "2000": ["2000"],
    "3000": ["3000"],
}

INDUSTRIES = ["RETAIL", "INDUSTRIAL", "WHOLESALE", "GOVERNMENT"]
MATERIAL_CATEGORIES = ["FINISHED", "SEMIFINISHED", "RAW"]


# =============================================================================
# DATA CLASSES FOR OUTPUT
# =============================================================================

@dataclass
class TextRecord:
    """Text record for header or item texts."""
    text_id: str
    text: str
    lang: str
    changed_at: str


@dataclass
class ScheduleLine:
    """VBEP-shaped schedule line for sales order items."""
    etenr: str  # Schedule line number (0001, 0002, etc.)
    edatu: str  # Confirmed delivery date
    wmeng: float  # Confirmed quantity
    bmeng: float  # Confirmed quantity (business)
    mbdat: str  # Material availability date (ATP result)
    lddat: str  # Loading date
    tddat: str  # Transportation planning date
    wadat: str  # Goods issue date
    lmeng: float  # Required quantity (from order)
    meins: str  # Unit of measure


@dataclass
class PricingCondition:
    """KONV-shaped pricing condition record."""
    knumv: str  # Condition document number
    kposn: str  # Condition item number (000000 for header, else item)
    stunr: str  # Step number in pricing procedure
    zaession: str  # Condition counter
    kschl: str  # Condition type (PR00, K004, MWST, etc.)
    kbetr: float  # Condition rate/amount
    konwa: str  # Condition currency/unit
    kpein: float  # Condition pricing unit
    kmein: str  # Condition unit of measure
    kwert: float  # Condition value
    krech: str  # Calculation type (A=%, B=fixed, C=quantity)
    kawrt: float  # Condition base value
    ktext: str  # Condition description


@dataclass
class SalesOrderItem:
    """VBAP-shaped sales order item."""
    posnr: str  # Item number (000010, 000020, etc.)
    matnr: str  # Material number
    werks: str  # Plant
    kwmeng: float  # Quantity (requested)
    netwr: float  # Net value
    waerk: str  # Currency
    pstyv: str  # Item category
    item_texts: List[Dict] = field(default_factory=list)
    schedule_lines: List[Dict] = field(default_factory=list)  # VBEP schedule lines


@dataclass
class SalesOrder:
    """VBAK-shaped sales order header."""
    vbeln: str  # Sales document number (10-digit)
    auart: str  # Order type (OR, ZOR, RE, CR)
    vkorg: str  # Sales organization
    vtweg: str  # Distribution channel
    spart: str  # Division
    kunnr: str  # Sold-to customer
    erdat: str  # Created date
    erzet: str  # Created time
    ernam: str  # Created by user
    vdatu: str  # Requested delivery date
    knumv: str = ""  # Condition document number (links to KONV)
    netwr: float = 0.0  # Net value of order
    waerk: str = "USD"  # Currency
    header_texts: List[Dict] = field(default_factory=list)
    items: List[Dict] = field(default_factory=list)
    conditions: List[Dict] = field(default_factory=list)  # KONV pricing conditions


@dataclass
class DeliveryItem:
    """LIPS-shaped delivery item."""
    posnr: str  # Item number
    matnr: str  # Material number
    lfimg: float  # Delivered quantity
    werks: str  # Plant
    vbeln_ref: str  # Reference sales order
    posnr_ref: str  # Reference item


@dataclass
class Delivery:
    """LIKP-shaped delivery header."""
    vbeln: str  # Delivery number
    erdat: str  # Creation date
    wadat: str  # Planned goods issue date
    wadat_ist: Optional[str]  # Actual goods issue date
    kunnr: str  # Ship-to customer
    items: List[Dict] = field(default_factory=list)


@dataclass
class InvoiceItem:
    """VBRP-shaped invoice item."""
    posnr: str  # Item number
    matnr: str  # Material number
    fkimg: float  # Billed quantity
    netwr: float  # Net value
    vbeln_ref: str  # Reference delivery
    posnr_ref: str  # Reference item


@dataclass
class Invoice:
    """VBRK-shaped invoice header."""
    vbeln: str  # Invoice number
    fkdat: str  # Billing date
    erdat: str  # Creation date
    netwr: float  # Net value
    waerk: str  # Currency
    kunrg: str  # Payer
    items: List[Dict] = field(default_factory=list)


@dataclass
class DocFlow:
    """VBFA-shaped document flow record."""
    vbelv: str  # Preceding document
    posnv: str  # Preceding item
    vbtyp_v: str  # Preceding document category
    vbeln: str  # Subsequent document
    posnn: str  # Subsequent item
    vbtyp_n: str  # Subsequent document category
    rfmng: float  # Transferred quantity
    erdat: str  # Creation date


@dataclass
class Customer:
    """Customer master data."""
    kunnr: str  # Customer number
    name1: str  # Customer name
    land1: str  # Country
    regio: str  # Region (derived from sales org)
    brsch: str  # Industry
    vkorg: str  # Sales organization


@dataclass
class Material:
    """Material master data."""
    matnr: str  # Material number
    maktx: str  # Material description
    mtart: str  # Material type (category)
    meins: str  # Base unit of measure
    brgew: float  # Gross weight
    gewei: str  # Weight unit
    base_price: float  # Base price for calculations


@dataclass
class UserMaster:
    """User master data (for created_by fields)."""
    bname: str  # User ID
    name_text: str  # User name
    vkorg: str  # Sales organization
    werks: List[str]  # Assigned plants


# =============================================================================
# MAIN GENERATOR CLASS
# =============================================================================

class SAPSDGenerator:
    """
    Synthetic data generator for SAP SD documents.

    Generates complete document chains: Sales Order -> Delivery -> Invoice
    with realistic timing, text patterns that correlate with outcomes,
    and proper organizational structure.
    """

    def __init__(
        self,
        count: int = 10000,
        seed: int = 42,
        output_dir: str = "sample_output",
        start_date: str = "2024-01-01",
        end_date: str = "2024-12-31",
    ):
        self.count = count
        self.seed = seed
        self.output_dir = Path(output_dir)
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        self.date_range_days = (self.end_date - self.start_date).days

        # Initialize random generators with seed for reproducibility
        self.rng = np.random.default_rng(seed)
        random.seed(seed)
        self.faker = Faker()
        Faker.seed(seed)

        # Document number counters
        self.order_counter = 0
        self.delivery_counter = 8000000000
        self.invoice_counter = 9000000000

        # Master data storage
        self.customers: List[Customer] = []
        self.materials: List[Material] = []
        self.users: List[UserMaster] = []

        # Transaction data storage
        self.sales_orders: List[SalesOrder] = []
        self.deliveries: List[Delivery] = []
        self.invoices: List[Invoice] = []
        self.doc_flows: List[DocFlow] = []

        # Lookup maps
        self.customer_by_id: Dict[str, Customer] = {}
        self.material_by_id: Dict[str, Material] = {}
        self.user_by_org: Dict[str, List[UserMaster]] = defaultdict(list)

        # Statistics tracking
        self.stats = {
            "orders_with_delay_text": 0,
            "orders_with_expedite_text": 0,
            "orders_with_split_text": 0,
            "orders_with_price_text": 0,
            "orders_with_return_text": 0,
            "orders_with_noise_text": 0,
            "cancellations": 0,
            "returns": 0,
            "credit_memos": 0,
            "deliveries_delayed": 0,
            "deliveries_severely_delayed": 0,
            "invoices_lagged": 0,
        }

    def _next_order_number(self) -> str:
        """Generate 10-digit order number."""
        self.order_counter += 1
        return f"{self.order_counter:010d}"

    def _next_delivery_number(self) -> str:
        """Generate delivery number."""
        self.delivery_counter += 1
        return str(self.delivery_counter)

    def _next_invoice_number(self) -> str:
        """Generate invoice number."""
        self.invoice_counter += 1
        return str(self.invoice_counter)

    def _random_date(self) -> datetime:
        """Generate random date within configured range."""
        days = self.rng.integers(0, self.date_range_days)
        return self.start_date + timedelta(days=int(days))

    def _random_time(self) -> str:
        """Generate random time string HH:MM:SS."""
        hour = self.rng.integers(6, 20)
        minute = self.rng.integers(0, 60)
        second = self.rng.integers(0, 60)
        return f"{hour:02d}:{minute:02d}:{second:02d}"

    def _weighted_choice(self, options: Dict[str, float]) -> str:
        """Select from weighted options."""
        choices = list(options.keys())
        weights = list(options.values())
        return self.rng.choice(choices, p=np.array(weights) / sum(weights))

    # =========================================================================
    # MASTER DATA GENERATION
    # =========================================================================

    def generate_customers(self, num_customers: int = 500) -> None:
        """Generate customer master data."""
        for i in range(num_customers):
            kunnr = f"CUST{i + 1:04d}"
            vkorg = self.rng.choice(list(SALES_ORGS.keys()))
            region = SALES_ORGS[vkorg]["region"]

            customer = Customer(
                kunnr=kunnr,
                name1=self.faker.company(),
                land1=region,
                regio=region,
                brsch=self.rng.choice(INDUSTRIES),
                vkorg=vkorg,
            )
            self.customers.append(customer)
            self.customer_by_id[kunnr] = customer

    def generate_materials(self, num_materials: int = 200) -> None:
        """Generate material master data."""
        for i in range(num_materials):
            matnr = f"MAT{i + 1:03d}"
            category = self.rng.choice(MATERIAL_CATEGORIES)

            # Price ranges by category
            price_ranges = {
                "FINISHED": (100.0, 5000.0),
                "SEMIFINISHED": (50.0, 2000.0),
                "RAW": (10.0, 500.0),
            }
            price_range = price_ranges[category]

            material = Material(
                matnr=matnr,
                maktx=f"{self.faker.word().title()} {self.faker.word().title()} {category}",
                mtart=category,
                meins="EA",
                brgew=round(self.rng.uniform(0.5, 50.0), 2),
                gewei="KG",
                base_price=round(self.rng.uniform(price_range[0], price_range[1]), 2),
            )
            self.materials.append(material)
            self.material_by_id[matnr] = material

    def generate_users(self, num_users: int = 50) -> None:
        """Generate user master data."""
        for i in range(num_users):
            bname = f"USER{i + 1:03d}"
            vkorg = self.rng.choice(list(SALES_ORGS.keys()))
            available_plants = PLANT_TO_SALES_ORG.get(vkorg, list(PLANTS.keys()))

            user = UserMaster(
                bname=bname,
                name_text=self.faker.name(),
                vkorg=vkorg,
                werks=list(available_plants),
            )
            self.users.append(user)
            self.user_by_org[vkorg].append(user)

    def _get_user_for_org(self, vkorg: str) -> str:
        """Get a random user for the given sales organization."""
        if self.user_by_org[vkorg]:
            return self.rng.choice(self.user_by_org[vkorg]).bname
        return self.rng.choice(self.users).bname

    # =========================================================================
    # TEXT PATTERN GENERATION
    # =========================================================================

    def _generate_text_pattern(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Generate text content with pattern or noise.
        Returns (text_content, pattern_category) where category is None for noise.
        """
        # 60% of orders have some text
        if self.rng.random() > 0.60:
            return None, None

        # Check each pattern category with its probability
        # Delay patterns
        for pattern, info in DELAY_PATTERNS.items():
            if self.rng.random() < info["probability"]:
                variants = [pattern] + info.get("variants", [])
                chosen = self.rng.choice(variants)
                self.stats["orders_with_delay_text"] += 1
                return self._add_text_noise(chosen), "delay"

        # Expedite patterns
        for pattern, info in EXPEDITE_PATTERNS.items():
            if self.rng.random() < info["probability"]:
                variants = [pattern] + info.get("variants", [])
                chosen = self.rng.choice(variants)
                self.stats["orders_with_expedite_text"] += 1
                return self._add_text_noise(chosen), "expedite"

        # Price patterns
        for pattern, info in PRICE_PATTERNS.items():
            if self.rng.random() < info["probability"]:
                variants = [pattern] + info.get("variants", [])
                chosen = self.rng.choice(variants)
                self.stats["orders_with_price_text"] += 1
                return self._add_text_noise(chosen), "price"

        # Split patterns
        for pattern, info in SPLIT_PATTERNS.items():
            if self.rng.random() < info["probability"]:
                variants = [pattern] + info.get("variants", [])
                chosen = self.rng.choice(variants)
                self.stats["orders_with_split_text"] += 1
                return self._add_text_noise(chosen), "split"

        # Return patterns
        for pattern, info in RETURN_PATTERNS.items():
            if self.rng.random() < info["probability"]:
                variants = [pattern] + info.get("variants", [])
                chosen = self.rng.choice(variants)
                self.stats["orders_with_return_text"] += 1
                return self._add_text_noise(chosen), "return"

        # Noise patterns (10% as specified)
        if self.rng.random() < 0.10:
            chosen = self.rng.choice(NOISE_PATTERNS)
            self.stats["orders_with_noise_text"] += 1
            return self._add_text_noise(chosen), "noise"

        return None, None

    def _add_text_noise(self, text: str) -> str:
        """Add realistic noise to text: context, abbreviations, typos."""
        noise_additions = [
            "",
            " - customer needs by Friday",
            f" - {self.faker.name()}",
            f" REF#{self.faker.bothify('####')}",
            " - please expedite",
            " per customer request",
            " - mgmt approved",
            f" {self.faker.date_this_year().strftime('%m/%d')}",
        ]

        # Randomly apply casing variations
        case_choice = self.rng.random()
        if case_choice < 0.3:
            text = text.upper()
        elif case_choice < 0.5:
            text = text.lower()

        # Add noise
        text += self.rng.choice(noise_additions)

        return text

    def _create_text_record(self, text: str, created_date: datetime) -> Dict:
        """Create a text record dictionary."""
        return {
            "text_id": self.faker.bothify("####"),
            "text": text,
            "lang": "EN",
            "changed_at": created_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    # =========================================================================
    # TIMING AND OUTCOME CALCULATIONS
    # =========================================================================

    def _calculate_delivery_timing(
        self,
        order_date: datetime,
        requested_date: datetime,
        text_patterns: List[str],
        pattern_category: Optional[str],
    ) -> Tuple[datetime, datetime, bool]:
        """
        Calculate planned and actual delivery dates based on patterns.
        Returns (planned_date, actual_date, is_delayed).
        """
        # Base delivery time: 3-7 days from order
        base_days = int(self.rng.integers(3, 8))
        planned_date = requested_date

        # Calculate actual date based on patterns
        actual_days = base_days

        # Check for delay patterns in text
        if pattern_category == "delay":
            # Find which delay pattern matched
            for pattern, info in DELAY_PATTERNS.items():
                all_variants = [pattern.upper()] + [v.upper() for v in info.get("variants", [])]
                if any(v in t.upper() for v in all_variants for t in text_patterns):
                    delay_min, delay_max = info["delay_days"]
                    actual_days += int(self.rng.integers(delay_min, delay_max + 1))
                    break

        # Check for expedite patterns
        elif pattern_category == "expedite":
            for pattern, info in EXPEDITE_PATTERNS.items():
                all_variants = [pattern.upper()] + [v.upper() for v in info.get("variants", [])]
                if any(v in t.upper() for v in all_variants for t in text_patterns):
                    reduction = info["reduction_days"]
                    actual_days = max(1, actual_days - reduction)
                    break

        # Random timing anomalies
        else:
            roll = self.rng.random()
            # 15% of deliveries: actual > requested (delays)
            if roll < 0.15:
                delay = int(self.rng.integers(1, 8))
                actual_days += delay
                self.stats["deliveries_delayed"] += 1

                # 5% significantly later (>10 days)
                if roll < 0.05:
                    actual_days += int(self.rng.integers(10, 20))
                    self.stats["deliveries_severely_delayed"] += 1

        actual_date = order_date + timedelta(days=actual_days)
        is_delayed = actual_date > planned_date

        return planned_date, actual_date, is_delayed

    def _calculate_invoice_date(
        self, delivery_date: datetime, text_patterns: List[str]
    ) -> datetime:
        """Calculate invoice date based on delivery date and patterns."""
        # Base: 1-3 days after delivery
        base_days = int(self.rng.integers(1, 4))

        # 10% of invoices: >7 days after delivery (invoice lag)
        if self.rng.random() < 0.10:
            base_days += int(self.rng.integers(7, 14))
            self.stats["invoices_lagged"] += 1

        return delivery_date + timedelta(days=base_days)

    def _determine_delivery_count(
        self, text_patterns: List[str], pattern_category: Optional[str]
    ) -> int:
        """Determine number of deliveries for an order."""
        # Check for split patterns
        if pattern_category == "split":
            for pattern, info in SPLIT_PATTERNS.items():
                all_variants = [pattern.upper()] + [v.upper() for v in info.get("variants", [])]
                if any(v in t.upper() for v in all_variants for t in text_patterns):
                    extra_min, extra_max = info["extra_deliveries"]
                    return 1 + int(self.rng.integers(extra_min, extra_max + 1))

        # Default distribution: 70% single, 20% two, 8% three, 2% more
        roll = self.rng.random()
        if roll < 0.70:
            return 1
        elif roll < 0.90:
            return 2
        elif roll < 0.98:
            return 3
        else:
            return int(self.rng.integers(3, 5))

    def _apply_price_modification(
        self, base_price: float, text_patterns: List[str], pattern_category: Optional[str]
    ) -> float:
        """Apply price modifications based on text patterns."""
        if pattern_category != "price":
            return base_price

        for pattern, info in PRICE_PATTERNS.items():
            all_variants = [pattern.upper()] + [v.upper() for v in info.get("variants", [])]
            if any(v in t.upper() for v in all_variants for t in text_patterns):
                factor_min, factor_max = info["price_factor"]
                factor = self.rng.uniform(factor_min, factor_max)
                return base_price * factor

        return base_price

    # =========================================================================
    # SCHEDULE LINE GENERATION (VBEP)
    # =========================================================================

    def _generate_schedule_lines(
        self,
        order_date: datetime,
        requested_date: datetime,
        quantity: float,
        text_patterns: List[str],
        pattern_category: Optional[str],
    ) -> List[Dict]:
        """
        Generate VBEP-style schedule lines for an item.

        Most items have 1 schedule line, but backorder/partial scenarios
        may have multiple lines representing split confirmations.
        """
        schedule_lines = []
        remaining_qty = quantity

        # Determine number of schedule lines
        num_lines = 1
        if pattern_category == "split":
            num_lines = int(self.rng.integers(2, 4))
        elif pattern_category == "delay":
            # Delayed items sometimes have partial confirmations
            if self.rng.random() < 0.3:
                num_lines = 2

        # Calculate base ATP date (material availability)
        base_atp_days = int(self.rng.integers(1, 4))
        if pattern_category == "delay":
            base_atp_days += int(self.rng.integers(5, 15))

        for line_idx in range(num_lines):
            etenr = f"{(line_idx + 1):04d}"

            # Quantity for this schedule line
            if line_idx < num_lines - 1:
                line_qty = round(remaining_qty * self.rng.uniform(0.3, 0.7), 0)
            else:
                line_qty = remaining_qty
            remaining_qty -= line_qty

            # Dates for this schedule line
            atp_offset = base_atp_days + (line_idx * int(self.rng.integers(3, 10)))
            mbdat = order_date + timedelta(days=atp_offset)

            # Loading date: 1-2 days after ATP
            lddat = mbdat + timedelta(days=int(self.rng.integers(1, 3)))

            # Transport planning: 1 day after loading
            tddat = lddat + timedelta(days=1)

            # Goods issue: 1-2 days after transport planning
            wadat = tddat + timedelta(days=int(self.rng.integers(1, 3)))

            # Confirmed delivery: requested or later based on ATP
            confirmed_date = max(requested_date, wadat + timedelta(days=int(self.rng.integers(1, 3))))
            if line_idx > 0:
                confirmed_date += timedelta(days=int(self.rng.integers(5, 15)))

            schedule_line = ScheduleLine(
                etenr=etenr,
                edatu=confirmed_date.strftime("%Y-%m-%d"),
                wmeng=line_qty,
                bmeng=line_qty,
                mbdat=mbdat.strftime("%Y-%m-%d"),
                lddat=lddat.strftime("%Y-%m-%d"),
                tddat=tddat.strftime("%Y-%m-%d"),
                wadat=wadat.strftime("%Y-%m-%d"),
                lmeng=quantity if line_idx == 0 else 0.0,  # Required qty only on first line
                meins="EA",
            )
            schedule_lines.append(asdict(schedule_line))

        return schedule_lines

    # =========================================================================
    # PRICING CONDITION GENERATION (KONV)
    # =========================================================================

    def _generate_pricing_conditions(
        self,
        vbeln: str,
        items: List[Dict],
        vkorg: str,
        pattern_category: Optional[str],
        text_patterns: List[str],
    ) -> Tuple[List[Dict], float]:
        """
        Generate KONV-style pricing conditions following standard pricing procedure.

        Returns (conditions_list, total_net_value).
        """
        knumv = f"K{vbeln}"  # Condition document number
        conditions = []
        currency = SALES_ORGS[vkorg]["currency"]
        tax_rate = TAX_RATES.get(vkorg, 0.10)

        # Track totals for header conditions
        total_gross = 0.0
        total_discounts = 0.0
        total_freight = 0.0
        total_tax = 0.0

        # Check if manual pricing is involved
        has_manual_pricing = pattern_category == "price" and any(
            "OVERRIDE" in t.upper() or "MANUAL" in t.upper()
            for t in text_patterns
        )

        # Generate item-level conditions
        for item in items:
            posnr = item["posnr"]
            base_value = item["netwr"]
            quantity = item["kwmeng"]
            unit_price = base_value / quantity if quantity > 0 else 0

            running_value = base_value
            item_gross = base_value

            for step_info in PRICING_PROCEDURE:
                step, counter, kschl, ktext, krech, from_step, to_step, required, prob = step_info

                # Skip subtotal steps at item level
                if krech == "X":
                    continue

                # Skip header-only conditions at item level
                if kschl in ("HD00", "AMIW", "NETW"):
                    continue

                # Determine if this condition applies
                applies = required
                if not required and prob > 0:
                    applies = self.rng.random() < prob

                if not applies:
                    continue

                # Calculate condition value
                if kschl == "PR00":
                    # Base price - already calculated
                    kbetr = unit_price
                    kwert = base_value
                elif kschl == "MWST":
                    # Tax on running value
                    kbetr = tax_rate * 100  # Tax rate as percentage
                    kwert = round(running_value * tax_rate, 2)
                    total_tax += kwert
                elif kschl == "KF00":
                    # Freight - fixed per item
                    kbetr = round(self.rng.uniform(5.0, 50.0), 2)
                    kwert = kbetr
                    total_freight += kwert
                elif krech == "A":
                    # Percentage discount
                    discount_pct = self.rng.uniform(0.02, 0.15)
                    kbetr = -round(discount_pct * 100, 2)  # Negative for discounts
                    kwert = -round(running_value * discount_pct, 2)
                    running_value += kwert  # Reduce running value
                    total_discounts += abs(kwert)
                else:
                    continue

                condition = PricingCondition(
                    knumv=knumv,
                    kposn=posnr,
                    stunr=f"{step:03d}",
                    zaession=f"{counter:02d}",
                    kschl=kschl,
                    kbetr=kbetr,
                    konwa=currency if krech != "A" else "%",
                    kpein=1.0,
                    kmein="EA",
                    kwert=kwert,
                    krech=krech,
                    kawrt=item_gross if krech == "A" else 0.0,
                    ktext=ktext,
                )
                conditions.append(asdict(condition))

            total_gross += item_gross

            # Add manual pricing conditions if applicable
            if has_manual_pricing:
                for manual_step, manual_counter, manual_kschl, manual_ktext, manual_krech, manual_from, manual_to in MANUAL_PRICING_CONDITIONS:
                    if self.rng.random() < 0.5:  # 50% chance each manual condition appears
                        if manual_krech == "B":
                            # Fixed override
                            override_value = round(self.rng.uniform(-100, 200), 2)
                            kwert = override_value
                            kbetr = override_value
                        else:
                            # Percentage adjustment
                            adj_pct = self.rng.uniform(-0.10, 0.15)
                            kbetr = round(adj_pct * 100, 2)
                            kwert = round(running_value * adj_pct, 2)

                        condition = PricingCondition(
                            knumv=knumv,
                            kposn=posnr,
                            stunr=f"{manual_step:03d}",
                            zaession=f"{manual_counter:02d}",
                            kschl=manual_kschl,
                            kbetr=kbetr,
                            konwa=currency if manual_krech == "B" else "%",
                            kpein=1.0,
                            kmein="EA",
                            kwert=kwert,
                            krech=manual_krech,
                            kawrt=running_value,
                            ktext=manual_ktext,
                        )
                        conditions.append(asdict(condition))

        # Add header-level conditions (kposn = "000000")
        # Header discount
        if self.rng.random() < 0.08:
            hd_pct = self.rng.uniform(0.02, 0.10)
            hd_value = -round(total_gross * hd_pct, 2)
            condition = PricingCondition(
                knumv=knumv,
                kposn="000000",
                stunr="400",
                zaession="00",
                kschl="HD00",
                kbetr=-round(hd_pct * 100, 2),
                konwa="%",
                kpein=1.0,
                kmein="",
                kwert=hd_value,
                krech="A",
                kawrt=total_gross,
                ktext="Header Discount",
            )
            conditions.append(asdict(condition))
            total_discounts += abs(hd_value)

        # Minimum order surcharge for small orders
        if total_gross < 100 and self.rng.random() < 0.5:
            surcharge = round(self.rng.uniform(10, 25), 2)
            condition = PricingCondition(
                knumv=knumv,
                kposn="000000",
                stunr="500",
                zaession="00",
                kschl="AMIW",
                kbetr=surcharge,
                konwa=currency,
                kpein=1.0,
                kmein="",
                kwert=surcharge,
                krech="B",
                kawrt=0.0,
                ktext="Minimum Value Surcharge",
            )
            conditions.append(asdict(condition))
            total_freight += surcharge

        # Calculate final net value
        net_value = round(total_gross - total_discounts + total_freight + total_tax, 2)

        # Add net value subtotal
        condition = PricingCondition(
            knumv=knumv,
            kposn="000000",
            stunr="900",
            zaession="00",
            kschl="NETW",
            kbetr=0.0,
            konwa=currency,
            kpein=1.0,
            kmein="",
            kwert=net_value,
            krech="X",
            kawrt=0.0,
            ktext="Net Value",
        )
        conditions.append(asdict(condition))

        return conditions, net_value

    # =========================================================================
    # DOCUMENT GENERATION
    # =========================================================================

    def _generate_sales_order(self, customer: Customer) -> SalesOrder:
        """Generate a single sales order with items."""
        order_date = self._random_date()
        vkorg = customer.vkorg
        ernam = self._get_user_for_org(vkorg)

        # Generate text pattern
        text_content, pattern_category = self._generate_text_pattern()
        text_patterns = [text_content] if text_content else []

        # Determine order type
        order_type_weights = {"OR": 0.85, "ZOR": 0.05, "RE": 0.03, "CR": 0.02}

        # Override for return patterns
        if pattern_category == "return":
            auart = "RE"
            self.stats["returns"] += 1
        else:
            auart = self._weighted_choice(order_type_weights)
            if auart == "RE":
                self.stats["returns"] += 1
            elif auart == "CR":
                self.stats["credit_memos"] += 1

        # ~5% cancellations (tracked separately)
        if self.rng.random() < 0.05 and auart == "OR":
            self.stats["cancellations"] += 1

        # Requested delivery date: 5-14 days from order
        vdatu = order_date + timedelta(days=int(self.rng.integers(5, 15)))

        # Generate items (1-5 items per order typically)
        num_items = int(self.rng.integers(1, 6))
        items = []
        available_plants = PLANT_TO_SALES_ORG.get(vkorg, list(PLANTS.keys()))

        for item_idx in range(1, num_items + 1):
            material = self.rng.choice(self.materials)
            kwmeng = float(self.rng.integers(1, 100))
            base_price = material.base_price
            price = self._apply_price_modification(base_price, text_patterns, pattern_category)
            netwr = round(kwmeng * price, 2)

            # Item category based on order type
            pstyv = "TAN" if auart not in ("RE", "CR") else "REN"

            # Item texts (15% of items have texts)
            item_texts = []
            if self.rng.random() < 0.15:
                item_text, _ = self._generate_text_pattern()
                if item_text:
                    item_texts.append(
                        self._create_text_record(item_text, order_date)
                    )

            # Generate schedule lines (VBEP) for this item
            schedule_lines = self._generate_schedule_lines(
                order_date=order_date,
                requested_date=vdatu,
                quantity=kwmeng,
                text_patterns=text_patterns,
                pattern_category=pattern_category,
            )

            item = SalesOrderItem(
                posnr=f"{item_idx * 10:06d}",
                matnr=material.matnr,
                werks=self.rng.choice(available_plants),
                kwmeng=kwmeng,
                netwr=netwr,
                waerk=SALES_ORGS[vkorg]["currency"],
                pstyv=pstyv,
                item_texts=item_texts,
                schedule_lines=schedule_lines,
            )
            items.append(asdict(item))

        # Header texts
        header_texts = []
        if text_content:
            header_texts.append(self._create_text_record(text_content, order_date))

        # Generate document number first (needed for pricing conditions)
        vbeln = self._next_order_number()

        # Generate pricing conditions (KONV)
        conditions, order_netwr = self._generate_pricing_conditions(
            vbeln=vbeln,
            items=items,
            vkorg=vkorg,
            pattern_category=pattern_category,
            text_patterns=text_patterns,
        )

        order = SalesOrder(
            vbeln=vbeln,
            auart=auart,
            vkorg=vkorg,
            vtweg=self.rng.choice(["10", "20"]),
            spart=self.rng.choice(["00", "10"]),
            kunnr=customer.kunnr,
            erdat=order_date.strftime("%Y-%m-%d"),
            erzet=self._random_time(),
            ernam=ernam,
            vdatu=vdatu.strftime("%Y-%m-%d"),
            knumv=f"K{vbeln}",  # Condition document number
            netwr=order_netwr,
            waerk=SALES_ORGS[vkorg]["currency"],
            header_texts=header_texts,
            items=items,
            conditions=conditions,
        )

        return order, text_patterns, pattern_category

    def _generate_deliveries(
        self,
        order: SalesOrder,
        text_patterns: List[str],
        pattern_category: Optional[str],
    ) -> List[Delivery]:
        """Generate deliveries for a sales order (0-3 per order)."""
        # Return orders and credit memos may not have deliveries
        if order.auart in ("CR",):
            return []

        # Determine number of deliveries
        num_deliveries = self._determine_delivery_count(text_patterns, pattern_category)

        # Random chance of no delivery (partial fulfillment scenarios)
        if self.rng.random() < 0.02:
            return []

        order_date = datetime.strptime(order.erdat, "%Y-%m-%d")
        requested_date = datetime.strptime(order.vdatu, "%Y-%m-%d")

        deliveries = []

        # Split items across deliveries
        items_per_delivery = [[] for _ in range(num_deliveries)]
        for idx, item in enumerate(order.items):
            delivery_idx = idx % num_deliveries
            items_per_delivery[delivery_idx].append(item)

        for del_idx, del_items in enumerate(items_per_delivery):
            if not del_items:
                continue

            # Calculate timing
            planned_date, actual_date, _ = self._calculate_delivery_timing(
                order_date, requested_date, text_patterns, pattern_category
            )

            # Stagger subsequent deliveries
            if del_idx > 0:
                actual_date += timedelta(days=int(self.rng.integers(3, 10)) * del_idx)
                planned_date = actual_date - timedelta(days=int(self.rng.integers(0, 3)))

            # Create delivery items
            delivery_items = []
            for item in del_items:
                del_item = DeliveryItem(
                    posnr=item["posnr"],
                    matnr=item["matnr"],
                    lfimg=item["kwmeng"],  # Full quantity delivered
                    werks=item["werks"],
                    vbeln_ref=order.vbeln,
                    posnr_ref=item["posnr"],
                )
                delivery_items.append(asdict(del_item))

            delivery = Delivery(
                vbeln=self._next_delivery_number(),
                erdat=order_date.strftime("%Y-%m-%d"),
                wadat=planned_date.strftime("%Y-%m-%d"),
                wadat_ist=actual_date.strftime("%Y-%m-%d"),
                kunnr=order.kunnr,
                items=delivery_items,
            )
            deliveries.append(delivery)

            # Create document flow records: Order -> Delivery
            for del_item in delivery_items:
                flow = DocFlow(
                    vbelv=order.vbeln,
                    posnv=del_item["posnr_ref"],
                    vbtyp_v="C",  # Sales Order
                    vbeln=delivery.vbeln,
                    posnn=del_item["posnr"],
                    vbtyp_n="J",  # Delivery
                    rfmng=del_item["lfimg"],
                    erdat=delivery.erdat,
                )
                self.doc_flows.append(flow)

        return deliveries

    def _generate_invoice(
        self,
        delivery: Delivery,
        order: SalesOrder,
        text_patterns: List[str],
    ) -> Optional[Invoice]:
        """Generate invoice for a delivery (0-1 per delivery)."""
        # ~5% of deliveries don't get invoiced immediately
        if self.rng.random() < 0.05:
            return None

        delivery_date = datetime.strptime(delivery.wadat_ist, "%Y-%m-%d")
        invoice_date = self._calculate_invoice_date(delivery_date, text_patterns)

        # Calculate invoice items and total
        invoice_items = []
        total_netwr = 0.0

        for del_item in delivery.items:
            # Find matching order item for pricing
            order_item = next(
                (oi for oi in order.items if oi["posnr"] == del_item["posnr_ref"]),
                None
            )
            if not order_item:
                continue

            netwr = round(
                del_item["lfimg"] * (order_item["netwr"] / order_item["kwmeng"]),
                2
            )
            total_netwr += netwr

            inv_item = InvoiceItem(
                posnr=del_item["posnr"],
                matnr=del_item["matnr"],
                fkimg=del_item["lfimg"],
                netwr=netwr,
                vbeln_ref=delivery.vbeln,
                posnr_ref=del_item["posnr"],
            )
            invoice_items.append(asdict(inv_item))

        invoice = Invoice(
            vbeln=self._next_invoice_number(),
            fkdat=invoice_date.strftime("%Y-%m-%d"),
            erdat=invoice_date.strftime("%Y-%m-%d"),
            netwr=round(total_netwr, 2),
            waerk=SALES_ORGS[order.vkorg]["currency"],
            kunrg=order.kunnr,
            items=invoice_items,
        )

        # Create document flow records: Delivery -> Invoice
        for inv_item in invoice_items:
            flow = DocFlow(
                vbelv=delivery.vbeln,
                posnv=inv_item["posnr_ref"],
                vbtyp_v="J",  # Delivery
                vbeln=invoice.vbeln,
                posnn=inv_item["posnr"],
                vbtyp_n="M",  # Invoice
                rfmng=inv_item["fkimg"],
                erdat=invoice.erdat,
            )
            self.doc_flows.append(flow)

        return invoice

    # =========================================================================
    # MAIN GENERATION AND OUTPUT
    # =========================================================================

    def generate_all(self) -> None:
        """Generate all synthetic data."""
        print("=" * 60)
        print("SAP SD Synthetic Data Generator")
        print("=" * 60)
        print(f"Seed: {self.seed}")
        print(f"Target Order Count: {self.count}")
        print(f"Date Range: {self.start_date.date()} to {self.end_date.date()}")
        print(f"Output Directory: {self.output_dir}")
        print("=" * 60)

        # Generate master data
        print("\nGenerating master data...")
        self.generate_customers(500)
        self.generate_materials(200)
        self.generate_users(50)
        print(f"  Customers: {len(self.customers)}")
        print(f"  Materials: {len(self.materials)}")
        print(f"  Users: {len(self.users)}")

        # Generate transaction data
        print(f"\nGenerating {self.count} sales orders with document chains...")

        for i in range(self.count):
            # Select customer (weighted toward some customers having more orders)
            customer = self.rng.choice(self.customers)

            # Generate sales order
            order, text_patterns, pattern_category = self._generate_sales_order(customer)
            self.sales_orders.append(order)

            # Generate deliveries
            order_deliveries = self._generate_deliveries(
                order, text_patterns, pattern_category
            )
            self.deliveries.extend(order_deliveries)

            # Generate invoices
            for delivery in order_deliveries:
                invoice = self._generate_invoice(delivery, order, text_patterns)
                if invoice:
                    self.invoices.append(invoice)

            # Progress update
            if (i + 1) % 1000 == 0:
                print(f"  Generated {i + 1} orders...")

        print(f"\nGeneration complete:")
        print(f"  Sales Orders: {len(self.sales_orders)}")
        print(f"  Deliveries: {len(self.deliveries)}")
        print(f"  Invoices: {len(self.invoices)}")
        print(f"  Document Flows: {len(self.doc_flows)}")

        # Print statistics
        print("\nText Pattern Statistics:")
        print(f"  Orders with DELAY patterns: {self.stats['orders_with_delay_text']}")
        print(f"  Orders with EXPEDITE patterns: {self.stats['orders_with_expedite_text']}")
        print(f"  Orders with SPLIT patterns: {self.stats['orders_with_split_text']}")
        print(f"  Orders with PRICE patterns: {self.stats['orders_with_price_text']}")
        print(f"  Orders with RETURN patterns: {self.stats['orders_with_return_text']}")
        print(f"  Orders with NOISE patterns: {self.stats['orders_with_noise_text']}")

        print("\nOutcome Statistics:")
        print(f"  Cancellations (~5%): {self.stats['cancellations']}")
        print(f"  Returns (~3%): {self.stats['returns']}")
        print(f"  Credit Memos (~2%): {self.stats['credit_memos']}")
        print(f"  Delayed Deliveries (15%): {self.stats['deliveries_delayed']}")
        print(f"  Severely Delayed (>10 days): {self.stats['deliveries_severely_delayed']}")
        print(f"  Invoice Lag (>7 days): {self.stats['invoices_lagged']}")

    def save_output(self) -> None:
        """Save all generated data to JSON files."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        def to_dict_list(items):
            """Convert dataclass items to dict list."""
            return [asdict(item) if hasattr(item, "__dataclass_fields__") else item for item in items]

        # Save transaction data as arrays of objects
        files = {
            "orders.json": [asdict(o) for o in self.sales_orders],
            "deliveries.json": [asdict(d) for d in self.deliveries],
            "invoices.json": [asdict(i) for i in self.invoices],
            "doc_flows.json": [asdict(df) for df in self.doc_flows],
            "customers.json": [asdict(c) for c in self.customers],
            "materials.json": [asdict(m) for m in self.materials],
            "vendors.json": [],  # Stub for MM module compatibility
        }

        print("\nSaving output files...")
        for filename, data in files.items():
            filepath = self.output_dir / filename
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            print(f"  {filepath} ({len(data)} records)")

        print("\nDone!")


def main():
    """Main entry point for the generator CLI."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic SAP SD (Sales & Distribution) data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/generate_sd.py --count 10000 --output sample_output/ --seed 42
  python src/generate_sd.py --count 5000 --seed 123
        """
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10000,
        help="Number of sales orders to generate (default: 10000)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="sample_output",
        help="Output directory for generated files (default: sample_output)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2024-01-01",
        help="Start date for documents (default: 2024-01-01)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default="2024-12-31",
        help="End date for documents (default: 2024-12-31)",
    )

    args = parser.parse_args()

    generator = SAPSDGenerator(
        count=args.count,
        seed=args.seed,
        output_dir=args.output,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    generator.generate_all()
    generator.save_output()


if __name__ == "__main__":
    main()
