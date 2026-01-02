"""
OCEL 2.0 JSON Exporter for SAP SD Process Data.

Exports SAP Sales and Distribution (SD) process data to the Object-Centric
Event Log (OCEL) 2.0 standard format.

The OCEL 2.0 format captures:
- Object types (e.g., SalesOrder, Delivery, Invoice)
- Event types (e.g., OrderCreated, GoodsIssued)
- Object instances with attributes and relationships
- Event instances with timestamps and object associations
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from .object_types import (
    OCELObject,
    OCELObjectType,
    SAP_SD_OBJECT_TYPES,
    create_object,
)
from .relationships import RelationshipMapper, RelationshipType

logger = logging.getLogger(__name__)


@dataclass
class OCELEventType:
    """
    OCEL 2.0 event type definition.

    Represents a type of business event (e.g., OrderCreated, GoodsIssued).
    """
    name: str
    attributes: List[Dict[str, str]] = field(default_factory=list)

    def to_ocel(self) -> Dict[str, Any]:
        """Convert to OCEL 2.0 JSON format."""
        return {
            "name": self.name,
            "attributes": self.attributes
        }


@dataclass
class OCELEvent:
    """
    OCEL 2.0 event instance.

    Represents a specific occurrence of an event with timestamp and objects.
    """
    id: str
    type: str
    timestamp: datetime
    attributes: Dict[str, Any] = field(default_factory=dict)
    relationships: List[Dict[str, str]] = field(default_factory=list)

    def to_ocel(self) -> Dict[str, Any]:
        """Convert to OCEL 2.0 JSON format."""
        # Format timestamp as ISO 8601
        if isinstance(self.timestamp, datetime):
            ts_str = self.timestamp.isoformat()
        else:
            ts_str = str(self.timestamp)

        result = {
            "id": self.id,
            "type": self.type,
            "time": ts_str,
            "attributes": self.attributes,
            "relationships": self.relationships
        }
        return result


# SAP SD Event Type Definitions
ORDER_CREATED = OCELEventType(
    name="OrderCreated",
    attributes=[
        {"name": "user", "type": "string"},
        {"name": "order_type", "type": "string"},
    ]
)

ORDER_CHANGED = OCELEventType(
    name="OrderChanged",
    attributes=[
        {"name": "user", "type": "string"},
        {"name": "change_type", "type": "string"},
    ]
)

ORDER_RELEASED = OCELEventType(
    name="OrderReleased",
    attributes=[
        {"name": "user", "type": "string"},
    ]
)

DELIVERY_CREATED = OCELEventType(
    name="DeliveryCreated",
    attributes=[
        {"name": "user", "type": "string"},
        {"name": "delivery_type", "type": "string"},
    ]
)

GOODS_ISSUED = OCELEventType(
    name="GoodsIssued",
    attributes=[
        {"name": "user", "type": "string"},
        {"name": "movement_type", "type": "string"},
    ]
)

INVOICE_CREATED = OCELEventType(
    name="InvoiceCreated",
    attributes=[
        {"name": "user", "type": "string"},
        {"name": "billing_type", "type": "string"},
    ]
)

INVOICE_POSTED = OCELEventType(
    name="InvoicePosted",
    attributes=[
        {"name": "user", "type": "string"},
    ]
)

# All SAP SD event types
SAP_SD_EVENT_TYPES: List[OCELEventType] = [
    ORDER_CREATED,
    ORDER_CHANGED,
    ORDER_RELEASED,
    DELIVERY_CREATED,
    GOODS_ISSUED,
    INVOICE_CREATED,
    INVOICE_POSTED,
]


class OCELExporter:
    """
    Exports SAP SD data to OCEL 2.0 JSON format.

    Takes unified document records from the data loader and converts them
    to the OCEL 2.0 standard, preserving object relationships and events.
    """

    def __init__(self):
        """Initialize the OCEL exporter."""
        self._objects: Dict[str, OCELObject] = {}
        self._events: List[OCELEvent] = []
        self._relationship_mapper = RelationshipMapper()
        self._event_counter = 0
        self._used_object_types: Set[str] = set()
        self._used_event_types: Set[str] = set()

    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        self._event_counter += 1
        return f"event_{self._event_counter}"

    def _parse_timestamp(
        self,
        date_value: Optional[Union[str, datetime]]
    ) -> Optional[datetime]:
        """
        Parse a date value into a datetime object.

        Args:
            date_value: Date as string or datetime

        Returns:
            Parsed datetime or None
        """
        if date_value is None:
            return None

        if isinstance(date_value, datetime):
            return date_value

        # Try common date formats
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%d.%m.%Y",
            "%Y%m%d",
        ]

        date_str = str(date_value).strip()

        # Handle timezone offset
        if "+" in date_str or (
            len(date_str) > 6 and date_str[-6] == "-"
        ):
            try:
                return datetime.fromisoformat(date_str)
            except ValueError:
                pass

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        logger.debug(f"Could not parse timestamp: {date_value}")
        return None

    def _create_order_object(
        self,
        order: Dict[str, Any]
    ) -> OCELObject:
        """
        Create an OCEL object for a sales order.

        Args:
            order: Sales order data from loader

        Returns:
            OCELObject for the order
        """
        doc_num = order.get("document_number", order.get("vbeln", ""))
        object_id = f"SalesOrder_{doc_num}"

        attributes = {
            "document_number": doc_num,
            "order_type": order.get("order_type", order.get("auart", "")),
            "sales_org": order.get("sales_org", order.get("vkorg", "")),
            "distribution_channel": order.get(
                "distribution_channel", order.get("vtweg", "")
            ),
            "division": order.get("division", order.get("spart", "")),
            "sold_to_party": order.get("customer", order.get("kunnr", "")),
            "created_date": order.get("created_date", order.get("erdat", "")),
            "net_value": order.get("net_value", order.get("netwr", 0)),
            "currency": order.get("currency", order.get("waerk", "")),
            "requested_delivery_date": order.get(
                "requested_delivery_date", order.get("vdatu", "")
            ),
        }

        # Remove empty values
        attributes = {k: v for k, v in attributes.items() if v}

        self._used_object_types.add("SalesOrder")
        return create_object(object_id, "SalesOrder", attributes)

    def _create_order_item_objects(
        self,
        order: Dict[str, Any]
    ) -> List[OCELObject]:
        """
        Create OCEL objects for sales order items.

        Args:
            order: Sales order data containing items

        Returns:
            List of OCELObject for each item
        """
        items = []
        doc_num = order.get("document_number", order.get("vbeln", ""))

        for item in order.get("items", []):
            item_num = item.get("item_number", item.get("posnr", ""))
            object_id = f"SalesOrderItem_{doc_num}_{item_num}"

            attributes = {
                "document_number": doc_num,
                "item_number": item_num,
                "material": item.get("material", item.get("matnr", "")),
                "quantity": item.get("quantity", item.get("kwmeng", 0)),
                "unit": item.get("unit", item.get("vrkme", "")),
                "net_value": item.get("net_value", item.get("netwr", 0)),
                "item_category": item.get(
                    "item_category", item.get("pstyv", "")
                ),
            }

            attributes = {k: v for k, v in attributes.items() if v}
            self._used_object_types.add("SalesOrderItem")
            items.append(create_object(object_id, "SalesOrderItem", attributes))

        return items

    def _create_delivery_object(
        self,
        delivery: Dict[str, Any]
    ) -> OCELObject:
        """
        Create an OCEL object for a delivery.

        Args:
            delivery: Delivery data from loader

        Returns:
            OCELObject for the delivery
        """
        doc_num = delivery.get("document_number", delivery.get("vbeln", ""))
        object_id = f"Delivery_{doc_num}"

        attributes = {
            "document_number": doc_num,
            "delivery_type": delivery.get(
                "delivery_type", delivery.get("lfart", "")
            ),
            "shipping_point": delivery.get(
                "shipping_point", delivery.get("vstel", "")
            ),
            "ship_to_party": delivery.get("customer", delivery.get("kunnr", "")),
            "created_date": delivery.get("created_date", delivery.get("erdat", "")),
            "planned_gi_date": delivery.get(
                "planned_gi_date", delivery.get("wadat", "")
            ),
            "actual_gi_date": delivery.get(
                "actual_gi_date", delivery.get("wadat_ist", "")
            ),
        }

        attributes = {k: v for k, v in attributes.items() if v}
        self._used_object_types.add("Delivery")
        return create_object(object_id, "Delivery", attributes)

    def _create_delivery_item_objects(
        self,
        delivery: Dict[str, Any]
    ) -> List[OCELObject]:
        """
        Create OCEL objects for delivery items.

        Args:
            delivery: Delivery data containing items

        Returns:
            List of OCELObject for each item
        """
        items = []
        doc_num = delivery.get("document_number", delivery.get("vbeln", ""))

        for item in delivery.get("items", []):
            item_num = item.get("item_number", item.get("posnr", ""))
            object_id = f"DeliveryItem_{doc_num}_{item_num}"

            attributes = {
                "document_number": doc_num,
                "item_number": item_num,
                "material": item.get("material", item.get("matnr", "")),
                "delivery_quantity": item.get(
                    "delivery_quantity", item.get("lfimg", 0)
                ),
                "unit": item.get("unit", item.get("meins", "")),
                "reference_doc": item.get(
                    "reference_doc", item.get("vgbel", "")
                ),
                "reference_item": item.get(
                    "reference_item", item.get("vgpos", "")
                ),
            }

            attributes = {k: v for k, v in attributes.items() if v}
            self._used_object_types.add("DeliveryItem")
            items.append(create_object(object_id, "DeliveryItem", attributes))

        return items

    def _create_invoice_object(
        self,
        invoice: Dict[str, Any]
    ) -> OCELObject:
        """
        Create an OCEL object for an invoice.

        Args:
            invoice: Invoice data from loader

        Returns:
            OCELObject for the invoice
        """
        doc_num = invoice.get("document_number", invoice.get("vbeln", ""))
        object_id = f"Invoice_{doc_num}"

        attributes = {
            "document_number": doc_num,
            "billing_type": invoice.get(
                "billing_type", invoice.get("fkart", "")
            ),
            "billing_date": invoice.get(
                "billing_date", invoice.get("fkdat", "")
            ),
            "payer": invoice.get("payer", invoice.get("kunrg", "")),
            "net_value": invoice.get("net_value", invoice.get("netwr", 0)),
            "tax_amount": invoice.get("tax_amount", invoice.get("mwsbk", 0)),
            "currency": invoice.get("currency", invoice.get("waerk", "")),
            "created_date": invoice.get("created_date", invoice.get("erdat", "")),
        }

        attributes = {k: v for k, v in attributes.items() if v}
        self._used_object_types.add("Invoice")
        return create_object(object_id, "Invoice", attributes)

    def _create_invoice_item_objects(
        self,
        invoice: Dict[str, Any]
    ) -> List[OCELObject]:
        """
        Create OCEL objects for invoice items.

        Args:
            invoice: Invoice data containing items

        Returns:
            List of OCELObject for each item
        """
        items = []
        doc_num = invoice.get("document_number", invoice.get("vbeln", ""))

        for item in invoice.get("items", []):
            item_num = item.get("item_number", item.get("posnr", ""))
            object_id = f"InvoiceItem_{doc_num}_{item_num}"

            attributes = {
                "document_number": doc_num,
                "item_number": item_num,
                "material": item.get("material", item.get("matnr", "")),
                "billed_quantity": item.get(
                    "billed_quantity", item.get("fkimg", 0)
                ),
                "net_value": item.get("net_value", item.get("netwr", 0)),
                "reference_doc": item.get(
                    "reference_doc", item.get("vgbel", "")
                ),
                "reference_item": item.get(
                    "reference_item", item.get("vgpos", "")
                ),
            }

            attributes = {k: v for k, v in attributes.items() if v}
            self._used_object_types.add("InvoiceItem")
            items.append(create_object(object_id, "InvoiceItem", attributes))

        return items

    def _create_order_events(
        self,
        order: Dict[str, Any],
        related_object_ids: List[str]
    ) -> List[OCELEvent]:
        """
        Create events for a sales order based on timestamps.

        Args:
            order: Sales order data
            related_object_ids: IDs of related objects (order + items)

        Returns:
            List of events for the order
        """
        events = []

        # OrderCreated event from created_date
        created_date = self._parse_timestamp(
            order.get("created_date", order.get("erdat"))
        )
        if created_date:
            event = OCELEvent(
                id=self._generate_event_id(),
                type="OrderCreated",
                timestamp=created_date,
                attributes={
                    "user": order.get("created_by", order.get("ernam", "")),
                    "order_type": order.get("order_type", order.get("auart", "")),
                },
                relationships=[
                    {"objectId": obj_id, "qualifier": "involved"}
                    for obj_id in related_object_ids
                ]
            )
            self._used_event_types.add("OrderCreated")
            events.append(event)

        # OrderReleased event if release_date exists
        release_date = self._parse_timestamp(
            order.get("release_date", order.get("release_status_date"))
        )
        if release_date:
            event = OCELEvent(
                id=self._generate_event_id(),
                type="OrderReleased",
                timestamp=release_date,
                attributes={
                    "user": order.get("released_by", ""),
                },
                relationships=[
                    {"objectId": obj_id, "qualifier": "involved"}
                    for obj_id in related_object_ids
                ]
            )
            self._used_event_types.add("OrderReleased")
            events.append(event)

        return events

    def _create_delivery_events(
        self,
        delivery: Dict[str, Any],
        related_object_ids: List[str]
    ) -> List[OCELEvent]:
        """
        Create events for a delivery based on timestamps.

        Args:
            delivery: Delivery data
            related_object_ids: IDs of related objects (delivery + items)

        Returns:
            List of events for the delivery
        """
        events = []

        # DeliveryCreated event
        created_date = self._parse_timestamp(
            delivery.get("created_date", delivery.get("erdat"))
        )
        if created_date:
            event = OCELEvent(
                id=self._generate_event_id(),
                type="DeliveryCreated",
                timestamp=created_date,
                attributes={
                    "user": delivery.get("created_by", delivery.get("ernam", "")),
                    "delivery_type": delivery.get(
                        "delivery_type", delivery.get("lfart", "")
                    ),
                },
                relationships=[
                    {"objectId": obj_id, "qualifier": "involved"}
                    for obj_id in related_object_ids
                ]
            )
            self._used_event_types.add("DeliveryCreated")
            events.append(event)

        # GoodsIssued event from actual_gi_date
        gi_date = self._parse_timestamp(
            delivery.get("actual_gi_date", delivery.get("wadat_ist"))
        )
        if gi_date:
            event = OCELEvent(
                id=self._generate_event_id(),
                type="GoodsIssued",
                timestamp=gi_date,
                attributes={
                    "user": delivery.get("gi_user", ""),
                    "movement_type": delivery.get("movement_type", "601"),
                },
                relationships=[
                    {"objectId": obj_id, "qualifier": "involved"}
                    for obj_id in related_object_ids
                ]
            )
            self._used_event_types.add("GoodsIssued")
            events.append(event)

        return events

    def _create_invoice_events(
        self,
        invoice: Dict[str, Any],
        related_object_ids: List[str]
    ) -> List[OCELEvent]:
        """
        Create events for an invoice based on timestamps.

        Args:
            invoice: Invoice data
            related_object_ids: IDs of related objects (invoice + items)

        Returns:
            List of events for the invoice
        """
        events = []

        # InvoiceCreated event
        created_date = self._parse_timestamp(
            invoice.get("created_date", invoice.get("erdat"))
        )
        if created_date:
            event = OCELEvent(
                id=self._generate_event_id(),
                type="InvoiceCreated",
                timestamp=created_date,
                attributes={
                    "user": invoice.get("created_by", invoice.get("ernam", "")),
                    "billing_type": invoice.get(
                        "billing_type", invoice.get("fkart", "")
                    ),
                },
                relationships=[
                    {"objectId": obj_id, "qualifier": "involved"}
                    for obj_id in related_object_ids
                ]
            )
            self._used_event_types.add("InvoiceCreated")
            events.append(event)

        # InvoicePosted event from posting_date
        posting_date = self._parse_timestamp(
            invoice.get("posting_date", invoice.get("billing_date"))
        )
        if posting_date and posting_date != created_date:
            event = OCELEvent(
                id=self._generate_event_id(),
                type="InvoicePosted",
                timestamp=posting_date,
                attributes={
                    "user": invoice.get("posted_by", ""),
                },
                relationships=[
                    {"objectId": obj_id, "qualifier": "involved"}
                    for obj_id in related_object_ids
                ]
            )
            self._used_event_types.add("InvoicePosted")
            events.append(event)

        return events

    def process_unified_record(self, record: Dict[str, Any]) -> None:
        """
        Process a unified document record into OCEL objects and events.

        Args:
            record: Unified record from DataLoader containing order,
                   deliveries, and invoices
        """
        order = record.get("order", {})
        deliveries = record.get("deliveries", [])
        invoices = record.get("invoices", [])

        if not order:
            logger.warning(f"Skipping record with no order data: {record.get('doc_key')}")
            return

        # Create order object and items
        order_obj = self._create_order_object(order)
        self._objects[order_obj.id] = order_obj

        order_item_objs = self._create_order_item_objects(order)
        for item_obj in order_item_objs:
            self._objects[item_obj.id] = item_obj
            # Add containment relationship
            self._relationship_mapper.add_relationship(
                order_obj.id, item_obj.id, RelationshipType.CONTAINS
            )
            self._relationship_mapper.add_relationship(
                item_obj.id, order_obj.id, RelationshipType.BELONGS_TO
            )

        # Create order events
        order_related_ids = [order_obj.id] + [o.id for o in order_item_objs]
        self._events.extend(self._create_order_events(order, order_related_ids))

        # Process deliveries
        for delivery in deliveries:
            delivery_obj = self._create_delivery_object(delivery)
            self._objects[delivery_obj.id] = delivery_obj

            # Order -> Delivery relationship
            self._relationship_mapper.add_relationship(
                order_obj.id, delivery_obj.id, RelationshipType.FULFILLED_BY
            )
            self._relationship_mapper.add_relationship(
                delivery_obj.id, order_obj.id, RelationshipType.FULFILLS
            )

            delivery_item_objs = self._create_delivery_item_objects(delivery)
            for item_obj in delivery_item_objs:
                self._objects[item_obj.id] = item_obj
                self._relationship_mapper.add_relationship(
                    delivery_obj.id, item_obj.id, RelationshipType.CONTAINS
                )
                self._relationship_mapper.add_relationship(
                    item_obj.id, delivery_obj.id, RelationshipType.BELONGS_TO
                )

            # Create delivery events
            delivery_related_ids = (
                [delivery_obj.id] + [o.id for o in delivery_item_objs]
            )
            self._events.extend(
                self._create_delivery_events(delivery, delivery_related_ids)
            )

        # Process invoices
        for invoice in invoices:
            invoice_obj = self._create_invoice_object(invoice)
            self._objects[invoice_obj.id] = invoice_obj

            # Find which delivery this invoice references
            for item in invoice.get("items", []):
                ref_doc = item.get("reference_doc", item.get("vgbel", ""))
                if ref_doc:
                    delivery_id = f"Delivery_{ref_doc}"
                    if delivery_id in self._objects:
                        self._relationship_mapper.add_relationship(
                            delivery_id, invoice_obj.id, RelationshipType.BILLED_BY
                        )
                        self._relationship_mapper.add_relationship(
                            invoice_obj.id, delivery_id, RelationshipType.BILLS
                        )
                        break

            invoice_item_objs = self._create_invoice_item_objects(invoice)
            for item_obj in invoice_item_objs:
                self._objects[item_obj.id] = item_obj
                self._relationship_mapper.add_relationship(
                    invoice_obj.id, item_obj.id, RelationshipType.CONTAINS
                )
                self._relationship_mapper.add_relationship(
                    item_obj.id, invoice_obj.id, RelationshipType.BELONGS_TO
                )

            # Create invoice events
            invoice_related_ids = (
                [invoice_obj.id] + [o.id for o in invoice_item_objs]
            )
            self._events.extend(
                self._create_invoice_events(invoice, invoice_related_ids)
            )

    def export(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Export unified records to OCEL 2.0 JSON format.

        Args:
            records: List of unified records from DataLoader

        Returns:
            OCEL 2.0 JSON structure as a dictionary
        """
        # Reset state
        self._objects.clear()
        self._events.clear()
        self._relationship_mapper.clear()
        self._event_counter = 0
        self._used_object_types.clear()
        self._used_event_types.clear()

        # Process all records
        for record in records:
            self.process_unified_record(record)

        # Add relationships to objects
        for obj_id, obj in self._objects.items():
            obj.relationships = self._relationship_mapper.get_relationships(obj_id)

        # Sort events by timestamp
        self._events.sort(key=lambda e: e.timestamp or datetime.min)

        # Build OCEL 2.0 structure
        # Only include object types that are actually used
        object_types = [
            ot.to_ocel()
            for ot in SAP_SD_OBJECT_TYPES
            if ot.name in self._used_object_types
        ]

        # Only include event types that are actually used
        event_types = [
            et.to_ocel()
            for et in SAP_SD_EVENT_TYPES
            if et.name in self._used_event_types
        ]

        ocel_data = {
            "objectTypes": object_types,
            "eventTypes": event_types,
            "objects": [obj.to_ocel() for obj in self._objects.values()],
            "events": [event.to_ocel() for event in self._events]
        }

        logger.info(
            f"Exported OCEL 2.0: {len(self._objects)} objects, "
            f"{len(self._events)} events"
        )

        return ocel_data

    def export_to_file(
        self,
        records: List[Dict[str, Any]],
        output_path: Union[str, Path],
        indent: int = 2
    ) -> Path:
        """
        Export unified records to an OCEL 2.0 JSON file.

        Args:
            records: List of unified records from DataLoader
            output_path: Path to the output file
            indent: JSON indentation level

        Returns:
            Path to the created file
        """
        output_path = Path(output_path)
        ocel_data = self.export(records)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ocel_data, f, indent=indent, default=str)

        logger.info(f"Wrote OCEL 2.0 file: {output_path}")
        return output_path

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the exported data.

        Returns:
            Dictionary with export statistics
        """
        object_type_counts = {}
        for obj in self._objects.values():
            obj_type = obj.type
            object_type_counts[obj_type] = object_type_counts.get(obj_type, 0) + 1

        event_type_counts = {}
        for event in self._events:
            event_type = event.type
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1

        return {
            "total_objects": len(self._objects),
            "total_events": len(self._events),
            "object_types": object_type_counts,
            "event_types": event_type_counts,
        }


def export_to_ocel(
    records: List[Dict[str, Any]],
    output_path: Optional[Union[str, Path]] = None
) -> Union[Dict[str, Any], Path]:
    """
    Convenience function to export records to OCEL 2.0 format.

    Args:
        records: List of unified records from DataLoader
        output_path: Optional path to save JSON file

    Returns:
        OCEL 2.0 data dict if no output_path, else Path to created file
    """
    exporter = OCELExporter()

    if output_path:
        return exporter.export_to_file(records, output_path)
    else:
        return exporter.export(records)
