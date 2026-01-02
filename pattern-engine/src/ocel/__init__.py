"""
OCEL 2.0 Exporter Module for SAP SD Process Data.

This module provides functionality to export SAP Sales and Distribution (SD)
process data to the Object-Centric Event Log (OCEL) 2.0 standard format.

OCEL 2.0 is a standard for representing event logs that involve multiple
object types and their relationships, making it ideal for complex business
processes like SAP Order-to-Cash.

Main components:
- object_types: SAP SD object type definitions (Order, Delivery, Invoice, etc.)
- relationships: Object relationship mapping and management
- exporter: Main OCEL 2.0 JSON exporter

Example usage:
    from ocel import OCELExporter, export_to_ocel
    from ingest.loader import DataLoader

    # Load data
    loader = DataLoader()
    records = loader.load_all(data_dir)

    # Export to OCEL 2.0
    exporter = OCELExporter()
    ocel_data = exporter.export(records)

    # Or save to file
    exporter.export_to_file(records, "output.ocel.json")

    # Or use convenience function
    export_to_ocel(records, "output.ocel.json")
"""

from .object_types import (
    OCELObject,
    OCELObjectType,
    SAP_SD_OBJECT_TYPES,
    SALES_ORDER_TYPE,
    SALES_ORDER_ITEM_TYPE,
    DELIVERY_TYPE,
    DELIVERY_ITEM_TYPE,
    INVOICE_TYPE,
    INVOICE_ITEM_TYPE,
    create_object,
    get_object_type,
)

from .relationships import (
    RelationshipDefinition,
    RelationshipMapper,
    RelationshipType,
    SAP_SD_RELATIONSHIPS,
    get_relationship_definition,
    get_valid_target_types,
)

from .exporter import (
    OCELEvent,
    OCELEventType,
    OCELExporter,
    SAP_SD_EVENT_TYPES,
    ORDER_CREATED,
    ORDER_CHANGED,
    ORDER_RELEASED,
    DELIVERY_CREATED,
    GOODS_ISSUED,
    INVOICE_CREATED,
    INVOICE_POSTED,
    export_to_ocel,
)

__all__ = [
    # Object types
    "OCELObject",
    "OCELObjectType",
    "SAP_SD_OBJECT_TYPES",
    "SALES_ORDER_TYPE",
    "SALES_ORDER_ITEM_TYPE",
    "DELIVERY_TYPE",
    "DELIVERY_ITEM_TYPE",
    "INVOICE_TYPE",
    "INVOICE_ITEM_TYPE",
    "create_object",
    "get_object_type",
    # Relationships
    "RelationshipDefinition",
    "RelationshipMapper",
    "RelationshipType",
    "SAP_SD_RELATIONSHIPS",
    "get_relationship_definition",
    "get_valid_target_types",
    # Events
    "OCELEvent",
    "OCELEventType",
    "SAP_SD_EVENT_TYPES",
    "ORDER_CREATED",
    "ORDER_CHANGED",
    "ORDER_RELEASED",
    "DELIVERY_CREATED",
    "GOODS_ISSUED",
    "INVOICE_CREATED",
    "INVOICE_POSTED",
    # Exporter
    "OCELExporter",
    "export_to_ocel",
]
