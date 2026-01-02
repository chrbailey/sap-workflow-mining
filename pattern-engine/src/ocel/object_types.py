"""
SAP SD Object Type Definitions for OCEL 2.0.

Defines the object types used in SAP Sales and Distribution (SD) processes,
mapped to their corresponding SAP tables (VBAK, VBAP, LIKP, LIPS, VBRK, VBRP).

OCEL 2.0 object types represent business entities that participate in events.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class OCELObjectType:
    """
    OCEL 2.0 object type definition.

    Represents a type of business object in the process (e.g., SalesOrder, Delivery).
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
class OCELObject:
    """
    OCEL 2.0 object instance.

    Represents a specific instance of a business object (e.g., order #12345).
    """
    id: str
    type: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    relationships: List[Dict[str, str]] = field(default_factory=list)

    def to_ocel(self) -> Dict[str, Any]:
        """Convert to OCEL 2.0 JSON format."""
        result = {
            "id": self.id,
            "type": self.type,
            "attributes": self.attributes
        }
        if self.relationships:
            result["relationships"] = self.relationships
        return result


# SAP SD Object Type Definitions
# These correspond to SAP standard tables

SALES_ORDER_TYPE = OCELObjectType(
    name="SalesOrder",
    attributes=[
        {"name": "document_number", "type": "string"},  # VBELN
        {"name": "order_type", "type": "string"},       # AUART
        {"name": "sales_org", "type": "string"},        # VKORG
        {"name": "distribution_channel", "type": "string"},  # VTWEG
        {"name": "division", "type": "string"},         # SPART
        {"name": "sold_to_party", "type": "string"},    # KUNNR
        {"name": "created_date", "type": "datetime"},   # ERDAT
        {"name": "created_by", "type": "string"},       # ERNAM
        {"name": "net_value", "type": "float"},         # NETWR
        {"name": "currency", "type": "string"},         # WAERK
        {"name": "requested_delivery_date", "type": "datetime"},  # VDATU
    ]
)

SALES_ORDER_ITEM_TYPE = OCELObjectType(
    name="SalesOrderItem",
    attributes=[
        {"name": "document_number", "type": "string"},  # VBELN
        {"name": "item_number", "type": "string"},      # POSNR
        {"name": "material", "type": "string"},         # MATNR
        {"name": "quantity", "type": "float"},          # KWMENG
        {"name": "unit", "type": "string"},             # VRKME
        {"name": "net_value", "type": "float"},         # NETWR
        {"name": "item_category", "type": "string"},    # PSTYV
        {"name": "rejection_reason", "type": "string"}, # ABGRU
    ]
)

DELIVERY_TYPE = OCELObjectType(
    name="Delivery",
    attributes=[
        {"name": "document_number", "type": "string"},  # VBELN
        {"name": "delivery_type", "type": "string"},    # LFART
        {"name": "shipping_point", "type": "string"},   # VSTEL
        {"name": "ship_to_party", "type": "string"},    # KUNNR
        {"name": "created_date", "type": "datetime"},   # ERDAT
        {"name": "planned_gi_date", "type": "datetime"},  # WADAT
        {"name": "actual_gi_date", "type": "datetime"},   # WADAT_IST
        {"name": "total_weight", "type": "float"},      # BTGEW
        {"name": "weight_unit", "type": "string"},      # GEWEI
    ]
)

DELIVERY_ITEM_TYPE = OCELObjectType(
    name="DeliveryItem",
    attributes=[
        {"name": "document_number", "type": "string"},  # VBELN
        {"name": "item_number", "type": "string"},      # POSNR
        {"name": "material", "type": "string"},         # MATNR
        {"name": "delivery_quantity", "type": "float"}, # LFIMG
        {"name": "unit", "type": "string"},             # MEINS
        {"name": "reference_doc", "type": "string"},    # VGBEL (ref to sales order)
        {"name": "reference_item", "type": "string"},   # VGPOS
    ]
)

INVOICE_TYPE = OCELObjectType(
    name="Invoice",
    attributes=[
        {"name": "document_number", "type": "string"},  # VBELN
        {"name": "billing_type", "type": "string"},     # FKART
        {"name": "billing_date", "type": "datetime"},   # FKDAT
        {"name": "payer", "type": "string"},            # KUNRG
        {"name": "net_value", "type": "float"},         # NETWR
        {"name": "tax_amount", "type": "float"},        # MWSBK
        {"name": "currency", "type": "string"},         # WAERK
        {"name": "created_date", "type": "datetime"},   # ERDAT
    ]
)

INVOICE_ITEM_TYPE = OCELObjectType(
    name="InvoiceItem",
    attributes=[
        {"name": "document_number", "type": "string"},  # VBELN
        {"name": "item_number", "type": "string"},      # POSNR
        {"name": "material", "type": "string"},         # MATNR
        {"name": "billed_quantity", "type": "float"},   # FKIMG
        {"name": "net_value", "type": "float"},         # NETWR
        {"name": "reference_doc", "type": "string"},    # VGBEL (ref to delivery)
        {"name": "reference_item", "type": "string"},   # VGPOS
    ]
)

# All SAP SD object types
SAP_SD_OBJECT_TYPES: List[OCELObjectType] = [
    SALES_ORDER_TYPE,
    SALES_ORDER_ITEM_TYPE,
    DELIVERY_TYPE,
    DELIVERY_ITEM_TYPE,
    INVOICE_TYPE,
    INVOICE_ITEM_TYPE,
]


def get_object_type(type_name: str) -> Optional[OCELObjectType]:
    """
    Get an object type definition by name.

    Args:
        type_name: Name of the object type (e.g., 'SalesOrder')

    Returns:
        The OCELObjectType if found, None otherwise
    """
    for obj_type in SAP_SD_OBJECT_TYPES:
        if obj_type.name == type_name:
            return obj_type
    return None


def create_object(
    object_id: str,
    object_type: str,
    attributes: Optional[Dict[str, Any]] = None,
    relationships: Optional[List[Dict[str, str]]] = None
) -> OCELObject:
    """
    Create an OCEL object instance.

    Args:
        object_id: Unique identifier for the object
        object_type: Type of the object (e.g., 'SalesOrder')
        attributes: Object attributes as key-value pairs
        relationships: List of relationship definitions

    Returns:
        An OCELObject instance
    """
    return OCELObject(
        id=object_id,
        type=object_type,
        attributes=attributes or {},
        relationships=relationships or []
    )
