#!/usr/bin/env python3
"""
SAP MM (Materials Management) Synthetic Data Generator

Generates realistic synthetic data for SAP MM documents including:
- Purchase Orders (ME21N-style): EKKO header + EKPO items
- Goods Receipts (MIGO-style): MKPF header + MSEG items
- Invoice Receipts (MIRO-style): RBKP header + RSEG items
- Document Flow linking PO -> GR -> IR

The generator creates complete document chains with realistic timing,
text patterns that correlate with outcomes (invoice holds, quantity discrepancies),
and proper organizational structure.

Usage:
    python src/generate_mm.py --count 5000 --output sample_output/ --seed 42
"""

from __future__ import annotations

import argparse
import json
import random
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

# Patterns causing invoice holds
INVOICE_HOLD_PATTERNS = {
    "INVOICE HOLD": {
        "probability": 0.05,
        "hold_days": (7, 21),
        "variants": ["INV HOLD", "HOLD INVOICE", "inv hold", "INVOICE BLOCK", "INV BLK"],
    },
    "PRICE VARIANCE": {
        "probability": 0.04,
        "hold_days": (5, 14),
        "variants": ["PR VAR", "PRICE DIFF", "price variance", "PRICING ISSUE"],
    },
    "PENDING APPROVAL": {
        "probability": 0.03,
        "hold_days": (3, 10),
        "variants": ["PEND APPR", "APPROVAL NEEDED", "pending approval", "WAITING APPR"],
    },
    "3-WAY MATCH FAIL": {
        "probability": 0.03,
        "hold_days": (5, 15),
        "variants": ["3WAY FAIL", "MATCH FAIL", "3-way match", "MATCHING ERROR"],
    },
}

# Patterns indicating quantity discrepancies
QTY_DISCREPANCY_PATTERNS = {
    "SHORT SHIP": {
        "probability": 0.05,
        "qty_factor": (0.70, 0.95),
        "variants": ["SHRT SHIP", "SHORT SHIPMENT", "short ship", "UNDER DELIVERY"],
    },
    "OVER SHIP": {
        "probability": 0.03,
        "qty_factor": (1.05, 1.20),
        "variants": ["OVR SHIP", "OVER SHIPMENT", "over ship", "OVER DELIVERY"],
    },
    "PARTIAL RECEIPT": {
        "probability": 0.04,
        "qty_factor": (0.40, 0.80),
        "variants": ["PART RCV", "PARTIAL GR", "partial receipt", "PARTIAL"],
    },
}

# Quality-related patterns
QUALITY_PATTERNS = {
    "QC HOLD": {
        "probability": 0.03,
        "hold_days": (3, 14),
        "variants": ["QUALITY HOLD", "QA HOLD", "qc hold", "QUALITY CHECK"],
    },
    "DAMAGED GOODS": {
        "probability": 0.02,
        "reject_rate": (0.05, 0.20),
        "variants": ["DMG", "DAMAGED", "damaged goods", "DAMAGE REPORT"],
    },
}

# Neutral/noise patterns
NOISE_PATTERNS = [
    "PO#", "REF:", "Standard order", "Per contract", "Blanket PO",
    "Scheduled delivery", "Regular order", "Recurring", "As per agreement",
    "See attachment", "Per quote", "Updated", "Revised", "Amendment",
    "Vendor confirmed", "CONF", "ACK", "Acknowledged",
]

# =============================================================================
# ORGANIZATIONAL DATA
# =============================================================================

PURCHASING_ORGS = {
    "1000": {"name": "US Purchasing", "region": "US", "currency": "USD"},
    "2000": {"name": "EU Purchasing", "region": "EU", "currency": "EUR"},
    "3000": {"name": "APAC Purchasing", "region": "APAC", "currency": "USD"},
}

PLANTS = {
    "1000": {"name": "US Main Plant", "purch_org": "1000"},
    "1100": {"name": "US Distribution", "purch_org": "1000"},
    "2000": {"name": "EU Manufacturing", "purch_org": "2000"},
    "3000": {"name": "APAC Hub", "purch_org": "3000"},
}

STORAGE_LOCATIONS = ["0001", "0002", "0003", "0010", "0020"]

VENDOR_INDUSTRIES = ["MANUFACTURING", "DISTRIBUTOR", "TRADING", "SERVICE"]
MATERIAL_CATEGORIES = ["RAW", "SEMIFINISHED", "SPARE", "CONSUMABLE"]


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
class POItem:
    """EKPO-shaped purchase order item."""
    ebelp: str  # Item number (00010, 00020, etc.)
    matnr: str  # Material number
    werks: str  # Plant
    menge: float  # Quantity
    meins: str  # Unit of measure
    netpr: float  # Net price
    netwr: float  # Net value
    waers: str  # Currency
    item_texts: List[Dict] = field(default_factory=list)


@dataclass
class PurchaseOrder:
    """EKKO-shaped purchase order header."""
    ebeln: str  # PO number (10-digit)
    bsart: str  # Document type (NB, ZNB, FO)
    ekorg: str  # Purchasing organization
    ekgrp: str  # Purchasing group
    lifnr: str  # Vendor number
    erdat: str  # Created date
    erzet: str  # Created time
    ernam: str  # Created by user
    bedat: str  # Document date
    eindt: str  # Delivery date
    header_texts: List[Dict] = field(default_factory=list)
    items: List[Dict] = field(default_factory=list)


@dataclass
class GRItem:
    """MSEG-shaped goods receipt item."""
    zeession: str  # Item number
    matnr: str  # Material number
    werks: str  # Plant
    lgort: str  # Storage location
    menge: float  # Quantity received
    meins: str  # Unit of measure
    ebeln: str  # Reference PO number
    ebelp: str  # Reference PO item


@dataclass
class GoodsReceipt:
    """MKPF-shaped goods receipt header."""
    mblnr: str  # Material document number
    mjahr: str  # Material document year
    bldat: str  # Document date
    budat: str  # Posting date
    usnam: str  # User name
    items: List[Dict] = field(default_factory=list)


@dataclass
class IRItem:
    """RSEG-shaped invoice receipt item."""
    buzei: str  # Item number
    matnr: str  # Material number
    menge: float  # Quantity invoiced
    wrbtr: float  # Amount in document currency
    ebeln: str  # Reference PO number
    ebelp: str  # Reference PO item
    mblnr: str  # Reference GR number


@dataclass
class InvoiceReceipt:
    """RBKP-shaped invoice receipt header."""
    belnr: str  # Invoice document number
    gjahr: str  # Fiscal year
    bldat: str  # Document date
    budat: str  # Posting date
    lifnr: str  # Vendor number
    rmwwr: float  # Gross invoice amount
    waers: str  # Currency
    zlspr: str  # Payment block (empty or block code)
    items: List[Dict] = field(default_factory=list)


@dataclass
class MMDocFlow:
    """Document flow record for MM documents."""
    vbelv: str  # Preceding document
    posnv: str  # Preceding item
    vbtyp_v: str  # Preceding doc type (F=PO, E=GR, P=IR)
    vbeln: str  # Subsequent document
    posnn: str  # Subsequent item
    vbtyp_n: str  # Subsequent doc type
    rfmng: float  # Transferred quantity
    erdat: str  # Creation date


@dataclass
class Vendor:
    """Vendor master data."""
    lifnr: str  # Vendor number
    name1: str  # Vendor name
    land1: str  # Country
    brsch: str  # Industry
    ekorg: str  # Purchasing organization


@dataclass
class MMMaterial:
    """Material master data for MM."""
    matnr: str  # Material number
    maktx: str  # Material description
    mtart: str  # Material type
    meins: str  # Base unit of measure
    base_price: float  # Base price


@dataclass
class MMUser:
    """User master data for MM."""
    bname: str  # User ID
    name_text: str  # User name
    ekorg: str  # Purchasing organization


# =============================================================================
# MAIN GENERATOR CLASS
# =============================================================================

class SAPMMGenerator:
    """
    Synthetic data generator for SAP MM documents.

    Generates complete document chains: Purchase Order -> Goods Receipt -> Invoice Receipt
    with realistic timing, text patterns that correlate with outcomes,
    and proper organizational structure.
    """

    def __init__(
        self,
        count: int = 5000,
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

        # Initialize random generators
        self.rng = np.random.default_rng(seed)
        random.seed(seed)
        self.faker = Faker()
        Faker.seed(seed)

        # Document number counters
        self.po_counter = 4500000000
        self.gr_counter = 5000000000
        self.ir_counter = 5100000000

        # Master data storage
        self.vendors: List[Vendor] = []
        self.materials: List[MMMaterial] = []
        self.users: List[MMUser] = []

        # Transaction data storage
        self.purchase_orders: List[PurchaseOrder] = []
        self.goods_receipts: List[GoodsReceipt] = []
        self.invoice_receipts: List[InvoiceReceipt] = []
        self.doc_flows: List[MMDocFlow] = []

        # Lookup maps
        self.vendor_by_id: Dict[str, Vendor] = {}
        self.material_by_id: Dict[str, MMMaterial] = {}
        self.user_by_org: Dict[str, List[MMUser]] = defaultdict(list)

        # Statistics
        self.stats = {
            "pos_with_invoice_hold_text": 0,
            "pos_with_qty_discrepancy_text": 0,
            "pos_with_quality_text": 0,
            "pos_with_noise_text": 0,
            "invoices_on_hold": 0,
            "grs_with_qty_variance": 0,
        }

    def _next_po_number(self) -> str:
        """Generate 10-digit PO number."""
        self.po_counter += 1
        return str(self.po_counter)

    def _next_gr_number(self) -> str:
        """Generate material document number."""
        self.gr_counter += 1
        return str(self.gr_counter)

    def _next_ir_number(self) -> str:
        """Generate invoice document number."""
        self.ir_counter += 1
        return str(self.ir_counter)

    def _random_date(self) -> datetime:
        """Generate random date within range."""
        days = self.rng.integers(0, self.date_range_days)
        return self.start_date + timedelta(days=int(days))

    def _random_time(self) -> str:
        """Generate random time string."""
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

    def generate_vendors(self, num_vendors: int = 200) -> None:
        """Generate vendor master data."""
        for i in range(num_vendors):
            lifnr = f"VEND{i + 1:04d}"
            ekorg = self.rng.choice(list(PURCHASING_ORGS.keys()))

            vendor = Vendor(
                lifnr=lifnr,
                name1=self.faker.company(),
                land1=PURCHASING_ORGS[ekorg]["region"],
                brsch=self.rng.choice(VENDOR_INDUSTRIES),
                ekorg=ekorg,
            )
            self.vendors.append(vendor)
            self.vendor_by_id[lifnr] = vendor

    def generate_materials(self, num_materials: int = 150) -> None:
        """Generate material master data for MM."""
        for i in range(num_materials):
            matnr = f"MMAT{i + 1:03d}"
            category = self.rng.choice(MATERIAL_CATEGORIES)

            price_ranges = {
                "RAW": (10.0, 200.0),
                "SEMIFINISHED": (50.0, 500.0),
                "SPARE": (5.0, 150.0),
                "CONSUMABLE": (1.0, 50.0),
            }
            price_range = price_ranges[category]

            material = MMMaterial(
                matnr=matnr,
                maktx=f"{self.faker.word().title()} {self.faker.word().title()} {category}",
                mtart=category,
                meins="EA",
                base_price=round(self.rng.uniform(price_range[0], price_range[1]), 2),
            )
            self.materials.append(material)
            self.material_by_id[matnr] = material

    def generate_users(self, num_users: int = 30) -> None:
        """Generate user master data for MM."""
        for i in range(num_users):
            bname = f"MMUSER{i + 1:03d}"
            ekorg = self.rng.choice(list(PURCHASING_ORGS.keys()))

            user = MMUser(
                bname=bname,
                name_text=self.faker.name(),
                ekorg=ekorg,
            )
            self.users.append(user)
            self.user_by_org[ekorg].append(user)

    def _get_user_for_org(self, ekorg: str) -> str:
        """Get a random user for the given purchasing organization."""
        if self.user_by_org[ekorg]:
            return self.rng.choice(self.user_by_org[ekorg]).bname
        return self.rng.choice(self.users).bname

    # =========================================================================
    # TEXT PATTERN GENERATION
    # =========================================================================

    def _generate_text_pattern(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Generate text content with pattern or noise.
        Returns (text_content, pattern_category).
        """
        if self.rng.random() > 0.50:
            return None, None

        # Invoice hold patterns
        for pattern, info in INVOICE_HOLD_PATTERNS.items():
            if self.rng.random() < info["probability"]:
                variants = [pattern] + info.get("variants", [])
                chosen = self.rng.choice(variants)
                self.stats["pos_with_invoice_hold_text"] += 1
                return self._add_text_noise(chosen), "invoice_hold"

        # Quantity discrepancy patterns
        for pattern, info in QTY_DISCREPANCY_PATTERNS.items():
            if self.rng.random() < info["probability"]:
                variants = [pattern] + info.get("variants", [])
                chosen = self.rng.choice(variants)
                self.stats["pos_with_qty_discrepancy_text"] += 1
                return self._add_text_noise(chosen), "qty_discrepancy"

        # Quality patterns
        for pattern, info in QUALITY_PATTERNS.items():
            if self.rng.random() < info["probability"]:
                variants = [pattern] + info.get("variants", [])
                chosen = self.rng.choice(variants)
                self.stats["pos_with_quality_text"] += 1
                return self._add_text_noise(chosen), "quality"

        # Noise patterns
        if self.rng.random() < 0.15:
            chosen = self.rng.choice(NOISE_PATTERNS)
            self.stats["pos_with_noise_text"] += 1
            return self._add_text_noise(chosen), "noise"

        return None, None

    def _add_text_noise(self, text: str) -> str:
        """Add realistic noise to text."""
        noise_additions = [
            "",
            f" - {self.faker.name()}",
            f" REF#{self.faker.bothify('####')}",
            " - please review",
            " - vendor notified",
            f" {self.faker.date_this_year().strftime('%m/%d')}",
        ]

        case_choice = self.rng.random()
        if case_choice < 0.3:
            text = text.upper()
        elif case_choice < 0.5:
            text = text.lower()

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

    def _calculate_gr_timing(
        self,
        po_date: datetime,
        delivery_date: datetime,
        text_patterns: List[str],
        pattern_category: Optional[str],
    ) -> datetime:
        """Calculate goods receipt date based on patterns."""
        base_days = int(self.rng.integers(1, 5))
        actual_date = delivery_date + timedelta(days=base_days)

        # Quality hold adds delay
        if pattern_category == "quality":
            for pattern, info in QUALITY_PATTERNS.items():
                if "hold_days" in info:
                    hold_min, hold_max = info["hold_days"]
                    actual_date += timedelta(days=int(self.rng.integers(hold_min, hold_max + 1)))
                    break

        return actual_date

    def _calculate_ir_timing(
        self,
        gr_date: datetime,
        text_patterns: List[str],
        pattern_category: Optional[str],
    ) -> Tuple[datetime, str]:
        """Calculate invoice receipt date and payment block."""
        base_days = int(self.rng.integers(3, 10))
        invoice_date = gr_date + timedelta(days=base_days)
        payment_block = ""

        # Invoice hold patterns
        if pattern_category == "invoice_hold":
            for pattern, info in INVOICE_HOLD_PATTERNS.items():
                all_variants = [pattern.upper()] + [v.upper() for v in info.get("variants", [])]
                if any(v in t.upper() for v in all_variants for t in text_patterns):
                    hold_min, hold_max = info["hold_days"]
                    invoice_date += timedelta(days=int(self.rng.integers(hold_min, hold_max + 1)))
                    payment_block = "A"  # Blocked for payment
                    self.stats["invoices_on_hold"] += 1
                    break

        return invoice_date, payment_block

    def _calculate_qty_factor(
        self, text_patterns: List[str], pattern_category: Optional[str]
    ) -> float:
        """Calculate quantity factor for GR (short/over ship scenarios)."""
        if pattern_category != "qty_discrepancy":
            return 1.0

        for pattern, info in QTY_DISCREPANCY_PATTERNS.items():
            all_variants = [pattern.upper()] + [v.upper() for v in info.get("variants", [])]
            if any(v in t.upper() for v in all_variants for t in text_patterns):
                factor_min, factor_max = info["qty_factor"]
                self.stats["grs_with_qty_variance"] += 1
                return self.rng.uniform(factor_min, factor_max)

        return 1.0

    # =========================================================================
    # DOCUMENT GENERATION
    # =========================================================================

    def _generate_purchase_order(self, vendor: Vendor) -> Tuple[PurchaseOrder, List[str], Optional[str]]:
        """Generate a single purchase order with items."""
        po_date = self._random_date()
        ekorg = vendor.ekorg
        ernam = self._get_user_for_org(ekorg)

        # Generate text pattern
        text_content, pattern_category = self._generate_text_pattern()
        text_patterns = [text_content] if text_content else []

        # PO type
        bsart = self._weighted_choice({"NB": 0.80, "ZNB": 0.15, "FO": 0.05})

        # Delivery date: 7-30 days from PO
        eindt = po_date + timedelta(days=int(self.rng.integers(7, 31)))

        # Generate items
        num_items = int(self.rng.integers(1, 6))
        items = []
        available_plants = [p for p, info in PLANTS.items() if info["purch_org"] == ekorg]
        if not available_plants:
            available_plants = list(PLANTS.keys())

        for item_idx in range(1, num_items + 1):
            material = self.rng.choice(self.materials)
            menge = float(self.rng.integers(10, 500))
            netpr = material.base_price
            netwr = round(menge * netpr, 2)

            item_texts = []
            if self.rng.random() < 0.10:
                item_text, _ = self._generate_text_pattern()
                if item_text:
                    item_texts.append(self._create_text_record(item_text, po_date))

            item = POItem(
                ebelp=f"{item_idx * 10:05d}",
                matnr=material.matnr,
                werks=self.rng.choice(available_plants),
                menge=menge,
                meins=material.meins,
                netpr=netpr,
                netwr=netwr,
                waers=PURCHASING_ORGS[ekorg]["currency"],
                item_texts=item_texts,
            )
            items.append(asdict(item))

        header_texts = []
        if text_content:
            header_texts.append(self._create_text_record(text_content, po_date))

        po = PurchaseOrder(
            ebeln=self._next_po_number(),
            bsart=bsart,
            ekorg=ekorg,
            ekgrp=f"P{self.rng.integers(1, 10):02d}",
            lifnr=vendor.lifnr,
            erdat=po_date.strftime("%Y-%m-%d"),
            erzet=self._random_time(),
            ernam=ernam,
            bedat=po_date.strftime("%Y-%m-%d"),
            eindt=eindt.strftime("%Y-%m-%d"),
            header_texts=header_texts,
            items=items,
        )

        return po, text_patterns, pattern_category

    def _generate_goods_receipt(
        self,
        po: PurchaseOrder,
        text_patterns: List[str],
        pattern_category: Optional[str],
    ) -> Optional[GoodsReceipt]:
        """Generate goods receipt for a purchase order."""
        # 3% chance of no GR (cancelled PO, etc.)
        if self.rng.random() < 0.03:
            return None

        po_date = datetime.strptime(po.erdat, "%Y-%m-%d")
        delivery_date = datetime.strptime(po.eindt, "%Y-%m-%d")
        gr_date = self._calculate_gr_timing(po_date, delivery_date, text_patterns, pattern_category)

        qty_factor = self._calculate_qty_factor(text_patterns, pattern_category)

        gr_items = []
        for po_item in po.items:
            received_qty = round(po_item["menge"] * qty_factor, 2)

            gr_item = GRItem(
                zeession=po_item["ebelp"],
                matnr=po_item["matnr"],
                werks=po_item["werks"],
                lgort=self.rng.choice(STORAGE_LOCATIONS),
                menge=received_qty,
                meins=po_item["meins"],
                ebeln=po.ebeln,
                ebelp=po_item["ebelp"],
            )
            gr_items.append(asdict(gr_item))

        gr = GoodsReceipt(
            mblnr=self._next_gr_number(),
            mjahr=str(gr_date.year),
            bldat=gr_date.strftime("%Y-%m-%d"),
            budat=gr_date.strftime("%Y-%m-%d"),
            usnam=self._get_user_for_org(po.ekorg),
            items=gr_items,
        )

        # Create document flow: PO -> GR
        for gr_item in gr_items:
            flow = MMDocFlow(
                vbelv=po.ebeln,
                posnv=gr_item["ebelp"],
                vbtyp_v="F",  # PO
                vbeln=gr.mblnr,
                posnn=gr_item["zeession"],
                vbtyp_n="E",  # GR
                rfmng=gr_item["menge"],
                erdat=gr.budat,
            )
            self.doc_flows.append(flow)

        return gr

    def _generate_invoice_receipt(
        self,
        po: PurchaseOrder,
        gr: GoodsReceipt,
        text_patterns: List[str],
        pattern_category: Optional[str],
    ) -> Optional[InvoiceReceipt]:
        """Generate invoice receipt for a goods receipt."""
        # 5% chance of no IR yet
        if self.rng.random() < 0.05:
            return None

        gr_date = datetime.strptime(gr.budat, "%Y-%m-%d")
        ir_date, payment_block = self._calculate_ir_timing(gr_date, text_patterns, pattern_category)

        ir_items = []
        total_amount = 0.0

        for gr_item in gr.items:
            # Find matching PO item for pricing
            po_item = next(
                (pi for pi in po.items if pi["ebelp"] == gr_item["ebelp"]),
                None
            )
            if not po_item:
                continue

            wrbtr = round(gr_item["menge"] * po_item["netpr"], 2)
            total_amount += wrbtr

            ir_item = IRItem(
                buzei=gr_item["zeession"],
                matnr=gr_item["matnr"],
                menge=gr_item["menge"],
                wrbtr=wrbtr,
                ebeln=gr_item["ebeln"],
                ebelp=gr_item["ebelp"],
                mblnr=gr.mblnr,
            )
            ir_items.append(asdict(ir_item))

        vendor = self.vendor_by_id.get(po.lifnr)
        currency = PURCHASING_ORGS[po.ekorg]["currency"] if vendor else "USD"

        ir = InvoiceReceipt(
            belnr=self._next_ir_number(),
            gjahr=str(ir_date.year),
            bldat=ir_date.strftime("%Y-%m-%d"),
            budat=ir_date.strftime("%Y-%m-%d"),
            lifnr=po.lifnr,
            rmwwr=round(total_amount, 2),
            waers=currency,
            zlspr=payment_block,
            items=ir_items,
        )

        # Create document flow: GR -> IR
        for ir_item in ir_items:
            flow = MMDocFlow(
                vbelv=gr.mblnr,
                posnv=ir_item["buzei"],
                vbtyp_v="E",  # GR
                vbeln=ir.belnr,
                posnn=ir_item["buzei"],
                vbtyp_n="P",  # IR
                rfmng=ir_item["menge"],
                erdat=ir.budat,
            )
            self.doc_flows.append(flow)

        return ir

    # =========================================================================
    # MAIN GENERATION AND OUTPUT
    # =========================================================================

    def generate_all(self) -> None:
        """Generate all synthetic MM data."""
        print("=" * 60)
        print("SAP MM Synthetic Data Generator")
        print("=" * 60)
        print(f"Seed: {self.seed}")
        print(f"Target PO Count: {self.count}")
        print(f"Date Range: {self.start_date.date()} to {self.end_date.date()}")
        print(f"Output Directory: {self.output_dir}")
        print("=" * 60)

        # Generate master data
        print("\nGenerating master data...")
        self.generate_vendors(200)
        self.generate_materials(150)
        self.generate_users(30)
        print(f"  Vendors: {len(self.vendors)}")
        print(f"  Materials: {len(self.materials)}")
        print(f"  Users: {len(self.users)}")

        # Generate transaction data
        print(f"\nGenerating {self.count} purchase orders with document chains...")

        for i in range(self.count):
            vendor = self.rng.choice(self.vendors)

            po, text_patterns, pattern_category = self._generate_purchase_order(vendor)
            self.purchase_orders.append(po)

            gr = self._generate_goods_receipt(po, text_patterns, pattern_category)
            if gr:
                self.goods_receipts.append(gr)

                ir = self._generate_invoice_receipt(po, gr, text_patterns, pattern_category)
                if ir:
                    self.invoice_receipts.append(ir)

            if (i + 1) % 1000 == 0:
                print(f"  Generated {i + 1} POs...")

        print(f"\nGeneration complete:")
        print(f"  Purchase Orders: {len(self.purchase_orders)}")
        print(f"  Goods Receipts: {len(self.goods_receipts)}")
        print(f"  Invoice Receipts: {len(self.invoice_receipts)}")
        print(f"  Document Flows: {len(self.doc_flows)}")

        print("\nText Pattern Statistics:")
        print(f"  POs with INVOICE HOLD patterns: {self.stats['pos_with_invoice_hold_text']}")
        print(f"  POs with QTY DISCREPANCY patterns: {self.stats['pos_with_qty_discrepancy_text']}")
        print(f"  POs with QUALITY patterns: {self.stats['pos_with_quality_text']}")
        print(f"  POs with NOISE patterns: {self.stats['pos_with_noise_text']}")

        print("\nOutcome Statistics:")
        print(f"  Invoices on Hold: {self.stats['invoices_on_hold']}")
        print(f"  GRs with Qty Variance: {self.stats['grs_with_qty_variance']}")

    def save_output(self) -> None:
        """Save all generated data to JSON files."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        files = {
            "purchase_orders.json": [asdict(po) for po in self.purchase_orders],
            "goods_receipts.json": [asdict(gr) for gr in self.goods_receipts],
            "invoice_receipts.json": [asdict(ir) for ir in self.invoice_receipts],
            "mm_doc_flows.json": [asdict(df) for df in self.doc_flows],
            "vendors.json": [asdict(v) for v in self.vendors],
            "mm_materials.json": [asdict(m) for m in self.materials],
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
        description="Generate synthetic SAP MM (Materials Management) data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/generate_mm.py --count 5000 --output sample_output/ --seed 42
  python src/generate_mm.py --count 2500 --seed 123
        """
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5000,
        help="Number of purchase orders to generate (default: 5000)",
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

    generator = SAPMMGenerator(
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
