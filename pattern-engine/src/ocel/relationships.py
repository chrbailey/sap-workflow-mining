"""
SAP SD Object Relationship Mapping for OCEL 2.0.

Defines how objects in the SAP SD process relate to each other:
- SalesOrder contains SalesOrderItems
- SalesOrder is fulfilled by Deliveries
- Delivery contains DeliveryItems
- Delivery is billed by Invoices
- Invoice contains InvoiceItems

These relationships follow the SAP document flow (VBFA table) patterns.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class RelationshipType(Enum):
    """Types of relationships between SAP objects."""

    # Structural relationships (parent-child)
    CONTAINS = "contains"           # Order -> Items
    BELONGS_TO = "belongs_to"       # Items -> Order (inverse)

    # Document flow relationships
    FULFILLED_BY = "fulfilled_by"   # Order -> Delivery
    FULFILLS = "fulfills"           # Delivery -> Order (inverse)
    BILLED_BY = "billed_by"         # Delivery -> Invoice
    BILLS = "bills"                 # Invoice -> Delivery (inverse)

    # Cross-references
    REFERENCES = "references"       # Generic reference
    DERIVED_FROM = "derived_from"   # Generic derivation


@dataclass
class RelationshipDefinition:
    """
    Definition of a relationship between two object types.

    Attributes:
        source_type: The source object type name
        target_type: The target object type name
        relationship_type: Type of relationship
        cardinality: Relationship cardinality ('1:1', '1:n', 'n:m')
        description: Human-readable description
    """
    source_type: str
    target_type: str
    relationship_type: RelationshipType
    cardinality: str
    description: str


# SAP SD Relationship Definitions
# These define how documents relate in the Order-to-Cash process

SAP_SD_RELATIONSHIPS: List[RelationshipDefinition] = [
    # Sales Order structure
    RelationshipDefinition(
        source_type="SalesOrder",
        target_type="SalesOrderItem",
        relationship_type=RelationshipType.CONTAINS,
        cardinality="1:n",
        description="Sales order contains line items"
    ),
    RelationshipDefinition(
        source_type="SalesOrderItem",
        target_type="SalesOrder",
        relationship_type=RelationshipType.BELONGS_TO,
        cardinality="n:1",
        description="Sales order item belongs to order"
    ),

    # Order to Delivery flow
    RelationshipDefinition(
        source_type="SalesOrder",
        target_type="Delivery",
        relationship_type=RelationshipType.FULFILLED_BY,
        cardinality="1:n",
        description="Sales order is fulfilled by one or more deliveries"
    ),
    RelationshipDefinition(
        source_type="SalesOrderItem",
        target_type="DeliveryItem",
        relationship_type=RelationshipType.FULFILLED_BY,
        cardinality="1:n",
        description="Order item is fulfilled by delivery items"
    ),
    RelationshipDefinition(
        source_type="Delivery",
        target_type="SalesOrder",
        relationship_type=RelationshipType.FULFILLS,
        cardinality="n:1",
        description="Delivery fulfills a sales order"
    ),

    # Delivery structure
    RelationshipDefinition(
        source_type="Delivery",
        target_type="DeliveryItem",
        relationship_type=RelationshipType.CONTAINS,
        cardinality="1:n",
        description="Delivery contains line items"
    ),
    RelationshipDefinition(
        source_type="DeliveryItem",
        target_type="Delivery",
        relationship_type=RelationshipType.BELONGS_TO,
        cardinality="n:1",
        description="Delivery item belongs to delivery"
    ),

    # Delivery to Invoice flow
    RelationshipDefinition(
        source_type="Delivery",
        target_type="Invoice",
        relationship_type=RelationshipType.BILLED_BY,
        cardinality="1:n",
        description="Delivery is billed by one or more invoices"
    ),
    RelationshipDefinition(
        source_type="DeliveryItem",
        target_type="InvoiceItem",
        relationship_type=RelationshipType.BILLED_BY,
        cardinality="1:n",
        description="Delivery item is billed by invoice items"
    ),
    RelationshipDefinition(
        source_type="Invoice",
        target_type="Delivery",
        relationship_type=RelationshipType.BILLS,
        cardinality="n:1",
        description="Invoice bills a delivery"
    ),

    # Invoice structure
    RelationshipDefinition(
        source_type="Invoice",
        target_type="InvoiceItem",
        relationship_type=RelationshipType.CONTAINS,
        cardinality="1:n",
        description="Invoice contains line items"
    ),
    RelationshipDefinition(
        source_type="InvoiceItem",
        target_type="Invoice",
        relationship_type=RelationshipType.BELONGS_TO,
        cardinality="n:1",
        description="Invoice item belongs to invoice"
    ),
]


class RelationshipMapper:
    """
    Maps relationships between SAP SD objects.

    Builds and tracks object relationships based on document references
    and document flow data.
    """

    def __init__(self):
        """Initialize the relationship mapper."""
        self._relationships: Dict[str, List[Dict[str, str]]] = {}
        self._inverse_map: Dict[str, Set[str]] = {}

    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: RelationshipType
    ) -> None:
        """
        Add a relationship between two objects.

        Args:
            source_id: ID of the source object
            target_id: ID of the target object
            relationship_type: Type of relationship
        """
        if source_id not in self._relationships:
            self._relationships[source_id] = []

        relationship = {
            "objectId": target_id,
            "qualifier": relationship_type.value
        }

        # Avoid duplicates
        if relationship not in self._relationships[source_id]:
            self._relationships[source_id].append(relationship)

        # Track inverse for lookups
        if target_id not in self._inverse_map:
            self._inverse_map[target_id] = set()
        self._inverse_map[target_id].add(source_id)

    def get_relationships(self, object_id: str) -> List[Dict[str, str]]:
        """
        Get all relationships for an object.

        Args:
            object_id: ID of the object

        Returns:
            List of relationship definitions
        """
        return self._relationships.get(object_id, [])

    def get_related_objects(
        self,
        object_id: str,
        relationship_type: Optional[RelationshipType] = None
    ) -> List[str]:
        """
        Get IDs of objects related to the given object.

        Args:
            object_id: ID of the object
            relationship_type: Optional filter by relationship type

        Returns:
            List of related object IDs
        """
        relationships = self._relationships.get(object_id, [])

        if relationship_type is None:
            return [r["objectId"] for r in relationships]

        return [
            r["objectId"]
            for r in relationships
            if r["qualifier"] == relationship_type.value
        ]

    def get_inverse_relationships(self, object_id: str) -> Set[str]:
        """
        Get objects that reference this object.

        Args:
            object_id: ID of the object

        Returns:
            Set of object IDs that reference this object
        """
        return self._inverse_map.get(object_id, set())

    def build_order_relationships(
        self,
        order_id: str,
        order_items: List[str],
        delivery_ids: List[str],
        delivery_items_map: Dict[str, List[str]]
    ) -> None:
        """
        Build all relationships for a sales order and its related documents.

        Args:
            order_id: Sales order ID
            order_items: List of order item IDs
            delivery_ids: List of delivery IDs
            delivery_items_map: Map of delivery ID -> list of item IDs
        """
        # Order -> Items
        for item_id in order_items:
            self.add_relationship(order_id, item_id, RelationshipType.CONTAINS)
            self.add_relationship(item_id, order_id, RelationshipType.BELONGS_TO)

        # Order -> Deliveries
        for delivery_id in delivery_ids:
            self.add_relationship(
                order_id, delivery_id, RelationshipType.FULFILLED_BY
            )
            self.add_relationship(
                delivery_id, order_id, RelationshipType.FULFILLS
            )

            # Delivery -> Items
            for item_id in delivery_items_map.get(delivery_id, []):
                self.add_relationship(
                    delivery_id, item_id, RelationshipType.CONTAINS
                )
                self.add_relationship(
                    item_id, delivery_id, RelationshipType.BELONGS_TO
                )

    def build_delivery_invoice_relationships(
        self,
        delivery_id: str,
        invoice_ids: List[str],
        invoice_items_map: Dict[str, List[str]]
    ) -> None:
        """
        Build relationships between deliveries and invoices.

        Args:
            delivery_id: Delivery ID
            invoice_ids: List of invoice IDs
            invoice_items_map: Map of invoice ID -> list of item IDs
        """
        for invoice_id in invoice_ids:
            self.add_relationship(
                delivery_id, invoice_id, RelationshipType.BILLED_BY
            )
            self.add_relationship(
                invoice_id, delivery_id, RelationshipType.BILLS
            )

            # Invoice -> Items
            for item_id in invoice_items_map.get(invoice_id, []):
                self.add_relationship(
                    invoice_id, item_id, RelationshipType.CONTAINS
                )
                self.add_relationship(
                    item_id, invoice_id, RelationshipType.BELONGS_TO
                )

    def clear(self) -> None:
        """Clear all relationships."""
        self._relationships.clear()
        self._inverse_map.clear()


def get_relationship_definition(
    source_type: str,
    target_type: str
) -> Optional[RelationshipDefinition]:
    """
    Get the relationship definition between two object types.

    Args:
        source_type: Source object type name
        target_type: Target object type name

    Returns:
        RelationshipDefinition if found, None otherwise
    """
    for rel_def in SAP_SD_RELATIONSHIPS:
        if rel_def.source_type == source_type and rel_def.target_type == target_type:
            return rel_def
    return None


def get_valid_target_types(source_type: str) -> List[str]:
    """
    Get valid target types for relationships from a source type.

    Args:
        source_type: Source object type name

    Returns:
        List of valid target type names
    """
    return [
        rel_def.target_type
        for rel_def in SAP_SD_RELATIONSHIPS
        if rel_def.source_type == source_type
    ]
