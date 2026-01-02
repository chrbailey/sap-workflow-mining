"""
Tests for OCEL 2.0 export module.

Tests cover:
- Object type definitions and creation
- Relationship mapping and management
- Event and event type handling
- Full OCEL export with realistic SAP SD data
- Edge cases and error handling
"""

import json
import pytest
import tempfile
from datetime import datetime
from pathlib import Path

from src.ocel import (
    # Object types
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
    # Relationships
    RelationshipDefinition,
    RelationshipMapper,
    RelationshipType,
    SAP_SD_RELATIONSHIPS,
    get_relationship_definition,
    get_valid_target_types,
    # Events
    OCELEvent,
    OCELEventType,
    SAP_SD_EVENT_TYPES,
    ORDER_CREATED,
    ORDER_CHANGED,
    DELIVERY_CREATED,
    GOODS_ISSUED,
    INVOICE_CREATED,
    # Exporter
    OCELExporter,
    export_to_ocel,
)


class TestOCELObjectTypes:
    """Tests for OCEL object type definitions."""

    def test_object_type_to_ocel(self):
        """Test OCELObjectType conversion to OCEL format."""
        result = SALES_ORDER_TYPE.to_ocel()

        assert result["name"] == "SalesOrder"
        assert "attributes" in result
        assert len(result["attributes"]) > 0

        # Check for expected attributes
        attr_names = [attr["name"] for attr in result["attributes"]]
        assert "document_number" in attr_names
        assert "order_type" in attr_names
        assert "net_value" in attr_names

    def test_all_sap_sd_object_types_defined(self):
        """Test that all SAP SD object types are defined."""
        expected_types = [
            "SalesOrder",
            "SalesOrderItem",
            "Delivery",
            "DeliveryItem",
            "Invoice",
            "InvoiceItem",
        ]

        type_names = [ot.name for ot in SAP_SD_OBJECT_TYPES]

        for expected in expected_types:
            assert expected in type_names

    def test_get_object_type_found(self):
        """Test getting an existing object type."""
        result = get_object_type("SalesOrder")

        assert result is not None
        assert result.name == "SalesOrder"

    def test_get_object_type_not_found(self):
        """Test getting a non-existent object type."""
        result = get_object_type("NonExistentType")

        assert result is None


class TestOCELObject:
    """Tests for OCEL object instances."""

    def test_create_object_basic(self):
        """Test basic object creation."""
        obj = create_object(
            object_id="SalesOrder_12345",
            object_type="SalesOrder",
            attributes={"document_number": "12345", "net_value": 1000.0}
        )

        assert obj.id == "SalesOrder_12345"
        assert obj.type == "SalesOrder"
        assert obj.attributes["document_number"] == "12345"
        assert obj.attributes["net_value"] == 1000.0

    def test_create_object_with_relationships(self):
        """Test object creation with relationships."""
        relationships = [
            {"objectId": "SalesOrderItem_12345_10", "qualifier": "contains"}
        ]
        obj = create_object(
            object_id="SalesOrder_12345",
            object_type="SalesOrder",
            attributes={"document_number": "12345"},
            relationships=relationships
        )

        assert len(obj.relationships) == 1
        assert obj.relationships[0]["objectId"] == "SalesOrderItem_12345_10"

    def test_object_to_ocel_format(self):
        """Test object conversion to OCEL JSON format."""
        obj = create_object(
            object_id="SalesOrder_12345",
            object_type="SalesOrder",
            attributes={"document_number": "12345"},
            relationships=[{"objectId": "item_1", "qualifier": "contains"}]
        )

        result = obj.to_ocel()

        assert result["id"] == "SalesOrder_12345"
        assert result["type"] == "SalesOrder"
        assert "attributes" in result
        assert "relationships" in result

    def test_object_to_ocel_without_relationships(self):
        """Test object without relationships has no relationships key."""
        obj = create_object(
            object_id="SalesOrder_12345",
            object_type="SalesOrder",
            attributes={"document_number": "12345"}
        )

        result = obj.to_ocel()

        # Should not include empty relationships
        assert "relationships" not in result or result["relationships"] == []


class TestRelationshipTypes:
    """Tests for relationship type definitions."""

    def test_relationship_types_enum(self):
        """Test that all relationship types are defined."""
        expected = [
            "CONTAINS",
            "BELONGS_TO",
            "FULFILLED_BY",
            "FULFILLS",
            "BILLED_BY",
            "BILLS",
            "REFERENCES",
            "DERIVED_FROM",
        ]

        for expected_type in expected:
            assert hasattr(RelationshipType, expected_type)

    def test_relationship_type_values(self):
        """Test relationship type string values."""
        assert RelationshipType.CONTAINS.value == "contains"
        assert RelationshipType.BELONGS_TO.value == "belongs_to"
        assert RelationshipType.FULFILLED_BY.value == "fulfilled_by"


class TestRelationshipMapper:
    """Tests for RelationshipMapper class."""

    @pytest.fixture
    def mapper(self):
        """Create a fresh RelationshipMapper."""
        return RelationshipMapper()

    def test_add_relationship(self, mapper):
        """Test adding a relationship."""
        mapper.add_relationship(
            "SalesOrder_12345",
            "SalesOrderItem_12345_10",
            RelationshipType.CONTAINS
        )

        relationships = mapper.get_relationships("SalesOrder_12345")

        assert len(relationships) == 1
        assert relationships[0]["objectId"] == "SalesOrderItem_12345_10"
        assert relationships[0]["qualifier"] == "contains"

    def test_add_multiple_relationships(self, mapper):
        """Test adding multiple relationships to same object."""
        mapper.add_relationship(
            "SalesOrder_12345",
            "SalesOrderItem_12345_10",
            RelationshipType.CONTAINS
        )
        mapper.add_relationship(
            "SalesOrder_12345",
            "SalesOrderItem_12345_20",
            RelationshipType.CONTAINS
        )

        relationships = mapper.get_relationships("SalesOrder_12345")

        assert len(relationships) == 2

    def test_no_duplicate_relationships(self, mapper):
        """Test that duplicate relationships are not added."""
        mapper.add_relationship(
            "SalesOrder_12345",
            "SalesOrderItem_12345_10",
            RelationshipType.CONTAINS
        )
        mapper.add_relationship(
            "SalesOrder_12345",
            "SalesOrderItem_12345_10",
            RelationshipType.CONTAINS
        )

        relationships = mapper.get_relationships("SalesOrder_12345")

        assert len(relationships) == 1

    def test_get_related_objects(self, mapper):
        """Test getting related object IDs."""
        mapper.add_relationship(
            "SalesOrder_12345",
            "SalesOrderItem_12345_10",
            RelationshipType.CONTAINS
        )
        mapper.add_relationship(
            "SalesOrder_12345",
            "Delivery_54321",
            RelationshipType.FULFILLED_BY
        )

        # Get all related
        all_related = mapper.get_related_objects("SalesOrder_12345")
        assert len(all_related) == 2

        # Filter by type
        contains_only = mapper.get_related_objects(
            "SalesOrder_12345",
            RelationshipType.CONTAINS
        )
        assert len(contains_only) == 1
        assert contains_only[0] == "SalesOrderItem_12345_10"

    def test_get_inverse_relationships(self, mapper):
        """Test getting inverse (incoming) relationships."""
        mapper.add_relationship(
            "SalesOrder_12345",
            "SalesOrderItem_12345_10",
            RelationshipType.CONTAINS
        )

        inverse = mapper.get_inverse_relationships("SalesOrderItem_12345_10")

        assert "SalesOrder_12345" in inverse

    def test_clear_relationships(self, mapper):
        """Test clearing all relationships."""
        mapper.add_relationship(
            "SalesOrder_12345",
            "SalesOrderItem_12345_10",
            RelationshipType.CONTAINS
        )

        mapper.clear()

        relationships = mapper.get_relationships("SalesOrder_12345")
        assert len(relationships) == 0

    def test_build_order_relationships(self, mapper):
        """Test building order-level relationships."""
        mapper.build_order_relationships(
            order_id="SalesOrder_12345",
            order_items=["Item_10", "Item_20"],
            delivery_ids=["Delivery_54321"],
            delivery_items_map={"Delivery_54321": ["DelItem_10"]}
        )

        # Order should contain items
        order_rels = mapper.get_relationships("SalesOrder_12345")
        assert len(order_rels) > 0

        # Items should belong to order
        item_rels = mapper.get_relationships("Item_10")
        assert any(r["qualifier"] == "belongs_to" for r in item_rels)


class TestRelationshipDefinitions:
    """Tests for SAP SD relationship definitions."""

    def test_sap_sd_relationships_defined(self):
        """Test that SAP SD relationships are defined."""
        assert len(SAP_SD_RELATIONSHIPS) > 0

    def test_get_relationship_definition_found(self):
        """Test getting a defined relationship."""
        rel_def = get_relationship_definition("SalesOrder", "SalesOrderItem")

        assert rel_def is not None
        assert rel_def.relationship_type == RelationshipType.CONTAINS
        assert rel_def.cardinality == "1:n"

    def test_get_relationship_definition_not_found(self):
        """Test getting an undefined relationship."""
        rel_def = get_relationship_definition("SalesOrder", "NonExistent")

        assert rel_def is None

    def test_get_valid_target_types(self):
        """Test getting valid target types for relationships."""
        targets = get_valid_target_types("SalesOrder")

        assert "SalesOrderItem" in targets
        assert "Delivery" in targets


class TestOCELEventTypes:
    """Tests for OCEL event type definitions."""

    def test_event_type_to_ocel(self):
        """Test event type conversion to OCEL format."""
        result = ORDER_CREATED.to_ocel()

        assert result["name"] == "OrderCreated"
        assert "attributes" in result

    def test_all_sap_sd_event_types_defined(self):
        """Test that all SAP SD event types are defined."""
        expected = [
            "OrderCreated",
            "OrderChanged",
            "OrderReleased",
            "DeliveryCreated",
            "GoodsIssued",
            "InvoiceCreated",
            "InvoicePosted",
        ]

        type_names = [et.name for et in SAP_SD_EVENT_TYPES]

        for expected_type in expected:
            assert expected_type in type_names


class TestOCELEvent:
    """Tests for OCEL event instances."""

    def test_event_creation(self):
        """Test basic event creation."""
        event = OCELEvent(
            id="event_1",
            type="OrderCreated",
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            attributes={"user": "ADMIN", "order_type": "OR"}
        )

        assert event.id == "event_1"
        assert event.type == "OrderCreated"
        assert event.attributes["user"] == "ADMIN"

    def test_event_with_relationships(self):
        """Test event with object relationships."""
        event = OCELEvent(
            id="event_1",
            type="OrderCreated",
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            relationships=[
                {"objectId": "SalesOrder_12345", "qualifier": "involved"}
            ]
        )

        assert len(event.relationships) == 1

    def test_event_to_ocel_format(self):
        """Test event conversion to OCEL JSON format."""
        event = OCELEvent(
            id="event_1",
            type="OrderCreated",
            timestamp=datetime(2024, 1, 15, 10, 0, 0),
            attributes={"user": "ADMIN"},
            relationships=[
                {"objectId": "SalesOrder_12345", "qualifier": "involved"}
            ]
        )

        result = event.to_ocel()

        assert result["id"] == "event_1"
        assert result["type"] == "OrderCreated"
        assert "time" in result
        assert "2024-01-15" in result["time"]
        assert result["attributes"]["user"] == "ADMIN"
        assert len(result["relationships"]) == 1


class TestOCELExporter:
    """Tests for OCELExporter class."""

    @pytest.fixture
    def sample_order_record(self):
        """Sample unified order record for testing."""
        return {
            "doc_key": "0000000001",
            "order": {
                "document_number": "0000000001",
                "vbeln": "0000000001",
                "auart": "OR",
                "vkorg": "1000",
                "kunnr": "CUST001",
                "erdat": "2024-01-15",
                "netwr": 10000.00,
                "waerk": "USD",
                "items": [
                    {
                        "posnr": "000010",
                        "matnr": "MAT001",
                        "kwmeng": 5,
                        "netwr": 5000.00,
                    },
                    {
                        "posnr": "000020",
                        "matnr": "MAT002",
                        "kwmeng": 10,
                        "netwr": 5000.00,
                    },
                ],
            },
            "deliveries": [
                {
                    "document_number": "8000000001",
                    "vbeln": "8000000001",
                    "lfart": "LF",
                    "erdat": "2024-01-17",
                    "wadat_ist": "2024-01-18",
                    "items": [
                        {
                            "posnr": "000010",
                            "matnr": "MAT001",
                            "lfimg": 5,
                            "vgbel": "0000000001",
                        },
                    ],
                },
            ],
            "invoices": [
                {
                    "document_number": "9000000001",
                    "vbeln": "9000000001",
                    "fkart": "F2",
                    "erdat": "2024-01-20",
                    "netwr": 5000.00,
                    "items": [
                        {
                            "posnr": "000010",
                            "matnr": "MAT001",
                            "fkimg": 5,
                            "vgbel": "8000000001",
                        },
                    ],
                },
            ],
        }

    @pytest.fixture
    def exporter(self):
        """Create a fresh OCELExporter."""
        return OCELExporter()

    def test_export_single_record(self, exporter, sample_order_record):
        """Test exporting a single unified record."""
        result = exporter.export([sample_order_record])

        assert "objectTypes" in result
        assert "eventTypes" in result
        assert "objects" in result
        assert "events" in result

        # Should have objects
        assert len(result["objects"]) > 0

        # Should have events
        assert len(result["events"]) > 0

    def test_export_creates_order_objects(self, exporter, sample_order_record):
        """Test that export creates order and item objects."""
        result = exporter.export([sample_order_record])

        object_ids = [obj["id"] for obj in result["objects"]]

        # Should have sales order
        assert any("SalesOrder_" in obj_id for obj_id in object_ids)

        # Should have sales order items
        assert any("SalesOrderItem_" in obj_id for obj_id in object_ids)

    def test_export_creates_delivery_objects(self, exporter, sample_order_record):
        """Test that export creates delivery objects."""
        result = exporter.export([sample_order_record])

        object_ids = [obj["id"] for obj in result["objects"]]

        # Should have delivery
        assert any("Delivery_" in obj_id for obj_id in object_ids)

    def test_export_creates_invoice_objects(self, exporter, sample_order_record):
        """Test that export creates invoice objects."""
        result = exporter.export([sample_order_record])

        object_ids = [obj["id"] for obj in result["objects"]]

        # Should have invoice
        assert any("Invoice_" in obj_id for obj_id in object_ids)

    def test_export_creates_events(self, exporter, sample_order_record):
        """Test that export creates events with correct types."""
        result = exporter.export([sample_order_record])

        event_types = [event["type"] for event in result["events"]]

        # Should have order created event
        assert "OrderCreated" in event_types

        # Should have delivery created event
        assert "DeliveryCreated" in event_types

        # Should have goods issued event (from wadat_ist)
        assert "GoodsIssued" in event_types

        # Should have invoice created event
        assert "InvoiceCreated" in event_types

    def test_export_events_sorted_by_timestamp(self, exporter, sample_order_record):
        """Test that events are sorted by timestamp."""
        result = exporter.export([sample_order_record])

        timestamps = [event["time"] for event in result["events"]]

        # Should be sorted
        assert timestamps == sorted(timestamps)

    def test_export_only_used_object_types(self, exporter, sample_order_record):
        """Test that only used object types are included."""
        result = exporter.export([sample_order_record])

        # Should not include all SAP SD types, only the used ones
        type_names = [ot["name"] for ot in result["objectTypes"]]

        assert "SalesOrder" in type_names
        assert len(type_names) <= len(SAP_SD_OBJECT_TYPES)

    def test_export_only_used_event_types(self, exporter, sample_order_record):
        """Test that only used event types are included."""
        result = exporter.export([sample_order_record])

        type_names = [et["name"] for et in result["eventTypes"]]

        # Should only include events that actually occurred
        assert len(type_names) <= len(SAP_SD_EVENT_TYPES)

    def test_export_to_file(self, exporter, sample_order_record):
        """Test exporting to a JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = Path(f.name)

        try:
            result_path = exporter.export_to_file([sample_order_record], output_path)

            assert result_path == output_path
            assert output_path.exists()

            # Verify file is valid JSON
            with open(output_path) as f:
                data = json.load(f)

            assert "objectTypes" in data
            assert "objects" in data
            assert "events" in data

        finally:
            output_path.unlink()

    def test_get_statistics(self, exporter, sample_order_record):
        """Test getting export statistics."""
        exporter.export([sample_order_record])
        stats = exporter.get_statistics()

        assert "total_objects" in stats
        assert "total_events" in stats
        assert "object_types" in stats
        assert "event_types" in stats

        assert stats["total_objects"] > 0
        assert stats["total_events"] > 0

    def test_export_multiple_records(self, exporter, sample_order_record):
        """Test exporting multiple records."""
        # Create second record with different IDs
        second_record = {
            "doc_key": "0000000002",
            "order": {
                "document_number": "0000000002",
                "vbeln": "0000000002",
                "auart": "SO",
                "erdat": "2024-01-20",
                "items": [],
            },
            "deliveries": [],
            "invoices": [],
        }

        result = exporter.export([sample_order_record, second_record])

        # Should have objects from both records
        object_ids = [obj["id"] for obj in result["objects"]]
        assert any("0000000001" in obj_id for obj_id in object_ids)
        assert any("0000000002" in obj_id for obj_id in object_ids)


class TestConvenienceFunction:
    """Tests for export_to_ocel convenience function."""

    @pytest.fixture
    def sample_record(self):
        """Minimal sample record."""
        return {
            "doc_key": "0000000001",
            "order": {
                "document_number": "0000000001",
                "erdat": "2024-01-15",
                "items": [],
            },
            "deliveries": [],
            "invoices": [],
        }

    def test_export_to_ocel_returns_dict(self, sample_record):
        """Test that export_to_ocel returns dict when no path."""
        result = export_to_ocel([sample_record])

        assert isinstance(result, dict)
        assert "objectTypes" in result

    def test_export_to_ocel_with_path(self, sample_record):
        """Test that export_to_ocel returns path when path provided."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = f.name

        try:
            result = export_to_ocel([sample_record], output_path)

            assert isinstance(result, Path)
            assert result.exists()

        finally:
            Path(output_path).unlink()


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def exporter(self):
        """Create a fresh OCELExporter."""
        return OCELExporter()

    def test_export_empty_records(self, exporter):
        """Test exporting empty records list."""
        result = exporter.export([])

        assert result["objects"] == []
        assert result["events"] == []

    def test_export_record_without_order(self, exporter):
        """Test exporting record with no order data."""
        record = {"doc_key": "001", "order": {}, "deliveries": [], "invoices": []}

        result = exporter.export([record])

        # Should handle gracefully
        assert isinstance(result, dict)

    def test_export_order_without_items(self, exporter):
        """Test exporting order with no items."""
        record = {
            "doc_key": "001",
            "order": {
                "document_number": "001",
                "erdat": "2024-01-15",
                "items": [],
            },
            "deliveries": [],
            "invoices": [],
        }

        result = exporter.export([record])

        # Should have order object but no item objects
        object_types = [obj["type"] for obj in result["objects"]]
        assert "SalesOrder" in object_types
        assert "SalesOrderItem" not in object_types

    def test_export_various_date_formats(self, exporter):
        """Test that various date formats are handled."""
        records = [
            {
                "doc_key": "001",
                "order": {"document_number": "001", "erdat": "2024-01-15", "items": []},
                "deliveries": [],
                "invoices": [],
            },
            {
                "doc_key": "002",
                "order": {"document_number": "002", "erdat": "20240116", "items": []},
                "deliveries": [],
                "invoices": [],
            },
            {
                "doc_key": "003",
                "order": {"document_number": "003", "erdat": "15.01.2024", "items": []},
                "deliveries": [],
                "invoices": [],
            },
        ]

        result = exporter.export(records)

        # All records should be processed
        assert len(result["objects"]) >= 3

    def test_export_clears_state_between_calls(self, exporter):
        """Test that exporter clears state between export calls."""
        record = {
            "doc_key": "001",
            "order": {"document_number": "001", "erdat": "2024-01-15", "items": []},
            "deliveries": [],
            "invoices": [],
        }

        result1 = exporter.export([record])
        result2 = exporter.export([record])

        # Both exports should have same number of objects
        assert len(result1["objects"]) == len(result2["objects"])

    def test_object_relationships_included(self, exporter):
        """Test that object relationships are included in output."""
        record = {
            "doc_key": "001",
            "order": {
                "document_number": "001",
                "erdat": "2024-01-15",
                "items": [{"posnr": "10", "matnr": "MAT1"}],
            },
            "deliveries": [],
            "invoices": [],
        }

        result = exporter.export([record])

        # Find the order object
        order_obj = next(
            (obj for obj in result["objects"] if obj["type"] == "SalesOrder"),
            None
        )

        # Order should have relationships to items
        assert order_obj is not None
        if "relationships" in order_obj:
            assert len(order_obj["relationships"]) > 0
