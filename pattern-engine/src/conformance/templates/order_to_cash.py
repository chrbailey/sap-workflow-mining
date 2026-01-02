"""
SAP Order-to-Cash (O2C) Process Model Template.

Defines the expected flow for the standard SAP Sales and Distribution (SD)
Order-to-Cash process. This model represents the canonical process:

    Order -> Delivery -> Goods Issue -> Invoice

The model supports multiple levels of detail:
- Simple: Core 4-step process (Order -> Delivery -> GI -> Invoice)
- Detailed: Includes sub-activities (releases, changes, posts)

SAP Transaction Flow:
- VA01/VA02: Create/Change Sales Order
- VL01N/VL02N: Create/Change Delivery
- VL06G: Goods Issue (Post Goods Issue)
- VF01/VF02: Create/Change Billing Document

References:
- SAP SD Module Documentation
- SAP Best Practices for Order-to-Cash
"""

from typing import Dict, List

from ..models import (
    Activity,
    ActivityType,
    ProcessModel,
    ProcessModelBuilder,
    Transition,
)


# SAP Order-to-Cash Activity Definitions
SAP_O2C_ACTIVITIES: Dict[str, Activity] = {
    # Order activities
    "OrderCreated": Activity(
        name="OrderCreated",
        display_name="Sales Order Created",
        activity_type=ActivityType.START,
        sap_event_types=frozenset(["OrderCreated", "VA01", "VBAK_CREATE"]),
        description="Sales order created in SAP (VA01)"
    ),
    "OrderChanged": Activity(
        name="OrderChanged",
        display_name="Sales Order Changed",
        activity_type=ActivityType.OPTIONAL,
        sap_event_types=frozenset(["OrderChanged", "VA02", "VBAK_CHANGE"]),
        description="Sales order modified (VA02)"
    ),
    "OrderReleased": Activity(
        name="OrderReleased",
        display_name="Sales Order Released",
        activity_type=ActivityType.OPTIONAL,
        sap_event_types=frozenset(["OrderReleased", "ORDER_RELEASE"]),
        description="Sales order released for delivery"
    ),

    # Delivery activities
    "DeliveryCreated": Activity(
        name="DeliveryCreated",
        display_name="Delivery Created",
        activity_type=ActivityType.INTERMEDIATE,
        sap_event_types=frozenset(["DeliveryCreated", "VL01N", "LIKP_CREATE"]),
        description="Outbound delivery created (VL01N)"
    ),
    "DeliveryChanged": Activity(
        name="DeliveryChanged",
        display_name="Delivery Changed",
        activity_type=ActivityType.OPTIONAL,
        sap_event_types=frozenset(["DeliveryChanged", "VL02N", "LIKP_CHANGE"]),
        description="Delivery document modified (VL02N)"
    ),
    "PickingCompleted": Activity(
        name="PickingCompleted",
        display_name="Picking Completed",
        activity_type=ActivityType.OPTIONAL,
        sap_event_types=frozenset(["PickingCompleted", "PICKING_COMPLETE"]),
        description="Warehouse picking completed"
    ),
    "PackingCompleted": Activity(
        name="PackingCompleted",
        display_name="Packing Completed",
        activity_type=ActivityType.OPTIONAL,
        sap_event_types=frozenset(["PackingCompleted", "PACKING_COMPLETE"]),
        description="Goods packed for shipment"
    ),

    # Goods Issue activities
    "GoodsIssued": Activity(
        name="GoodsIssued",
        display_name="Goods Issue Posted",
        activity_type=ActivityType.MILESTONE,
        sap_event_types=frozenset(["GoodsIssued", "VL06G", "GOODS_ISSUE", "MIGO_GI"]),
        description="Goods issue posted - inventory reduced (VL06G/MIGO)"
    ),

    # Billing activities
    "InvoiceCreated": Activity(
        name="InvoiceCreated",
        display_name="Invoice Created",
        activity_type=ActivityType.END,
        sap_event_types=frozenset(["InvoiceCreated", "VF01", "VBRK_CREATE"]),
        description="Billing document created (VF01)"
    ),
    "InvoicePosted": Activity(
        name="InvoicePosted",
        display_name="Invoice Posted to FI",
        activity_type=ActivityType.OPTIONAL,
        sap_event_types=frozenset(["InvoicePosted", "INVOICE_POST", "FI_POST"]),
        description="Invoice posted to Financial Accounting"
    ),
    "PaymentReceived": Activity(
        name="PaymentReceived",
        display_name="Payment Received",
        activity_type=ActivityType.OPTIONAL,
        sap_event_types=frozenset(["PaymentReceived", "PAYMENT_RECEIVED", "F-28"]),
        description="Customer payment received"
    ),
}


def get_simple_o2c_model() -> ProcessModel:
    """
    Get the simple (4-step) Order-to-Cash process model.

    This model represents the core O2C flow:
    Order -> Delivery -> Goods Issue -> Invoice

    Returns:
        ProcessModel for simple O2C process
    """
    builder = ProcessModelBuilder(
        name="sap_o2c_simple",
        display_name="SAP Order-to-Cash (Simple)",
        description="Standard SAP O2C process: Order -> Delivery -> GI -> Invoice",
        version="1.0.0"
    )

    # Add core activities
    builder.add_activity(
        "OrderCreated",
        "Sales Order Created",
        ActivityType.START,
        sap_event_types=["OrderCreated", "VA01", "VBAK_CREATE"],
        description="Sales order created in SAP"
    )

    builder.add_activity(
        "DeliveryCreated",
        "Delivery Created",
        ActivityType.INTERMEDIATE,
        sap_event_types=["DeliveryCreated", "VL01N", "LIKP_CREATE"],
        description="Outbound delivery created"
    )

    builder.add_activity(
        "GoodsIssued",
        "Goods Issue Posted",
        ActivityType.MILESTONE,
        sap_event_types=["GoodsIssued", "VL06G", "GOODS_ISSUE"],
        description="Goods issue posted"
    )

    builder.add_activity(
        "InvoiceCreated",
        "Invoice Created",
        ActivityType.END,
        sap_event_types=["InvoiceCreated", "VF01", "VBRK_CREATE"],
        description="Billing document created"
    )

    # Add sequential flow
    builder.add_sequence([
        "OrderCreated",
        "DeliveryCreated",
        "GoodsIssued",
        "InvoiceCreated"
    ])

    return builder.build()


def get_detailed_o2c_model() -> ProcessModel:
    """
    Get the detailed Order-to-Cash process model.

    This model includes optional activities and sub-processes:
    - Order creation, changes, and release
    - Delivery creation with picking and packing
    - Goods issue
    - Invoice creation and posting
    - Payment receipt

    Returns:
        ProcessModel for detailed O2C process
    """
    builder = ProcessModelBuilder(
        name="sap_o2c_detailed",
        display_name="SAP Order-to-Cash (Detailed)",
        description="Detailed SAP O2C process with sub-activities",
        version="1.0.0"
    )

    # Order phase activities
    builder.add_activity(
        "OrderCreated",
        "Sales Order Created",
        ActivityType.START,
        sap_event_types=["OrderCreated", "VA01", "VBAK_CREATE"],
        description="Sales order created in SAP (VA01)"
    )

    builder.add_activity(
        "OrderChanged",
        "Sales Order Changed",
        ActivityType.OPTIONAL,
        sap_event_types=["OrderChanged", "VA02", "VBAK_CHANGE"],
        description="Sales order modified (VA02)"
    )

    builder.add_activity(
        "OrderReleased",
        "Sales Order Released",
        ActivityType.OPTIONAL,
        sap_event_types=["OrderReleased", "ORDER_RELEASE"],
        description="Sales order released for delivery"
    )

    # Delivery phase activities
    builder.add_activity(
        "DeliveryCreated",
        "Delivery Created",
        ActivityType.INTERMEDIATE,
        sap_event_types=["DeliveryCreated", "VL01N", "LIKP_CREATE"],
        description="Outbound delivery created (VL01N)"
    )

    builder.add_activity(
        "DeliveryChanged",
        "Delivery Changed",
        ActivityType.OPTIONAL,
        sap_event_types=["DeliveryChanged", "VL02N", "LIKP_CHANGE"],
        description="Delivery document modified (VL02N)"
    )

    builder.add_activity(
        "PickingCompleted",
        "Picking Completed",
        ActivityType.OPTIONAL,
        sap_event_types=["PickingCompleted", "PICKING_COMPLETE"],
        description="Warehouse picking completed"
    )

    builder.add_activity(
        "PackingCompleted",
        "Packing Completed",
        ActivityType.OPTIONAL,
        sap_event_types=["PackingCompleted", "PACKING_COMPLETE"],
        description="Goods packed for shipment"
    )

    # Goods Issue
    builder.add_activity(
        "GoodsIssued",
        "Goods Issue Posted",
        ActivityType.MILESTONE,
        sap_event_types=["GoodsIssued", "VL06G", "GOODS_ISSUE"],
        description="Goods issue posted - inventory reduced"
    )

    # Billing phase activities
    builder.add_activity(
        "InvoiceCreated",
        "Invoice Created",
        ActivityType.INTERMEDIATE,
        sap_event_types=["InvoiceCreated", "VF01", "VBRK_CREATE"],
        description="Billing document created (VF01)"
    )

    builder.add_activity(
        "InvoicePosted",
        "Invoice Posted",
        ActivityType.OPTIONAL,
        sap_event_types=["InvoicePosted", "INVOICE_POST", "FI_POST"],
        description="Invoice posted to Financial Accounting"
    )

    builder.add_activity(
        "PaymentReceived",
        "Payment Received",
        ActivityType.END,
        sap_event_types=["PaymentReceived", "PAYMENT_RECEIVED"],
        description="Customer payment received"
    )

    # Define transitions

    # Order phase
    builder.add_transition("OrderCreated", "OrderChanged", is_mandatory=False)
    builder.add_transition("OrderCreated", "OrderReleased", is_mandatory=False)
    builder.add_transition("OrderCreated", "DeliveryCreated")
    builder.add_transition("OrderChanged", "OrderReleased", is_mandatory=False)
    builder.add_transition("OrderChanged", "DeliveryCreated")
    builder.add_transition("OrderReleased", "DeliveryCreated")

    # Delivery phase
    builder.add_transition("DeliveryCreated", "DeliveryChanged", is_mandatory=False)
    builder.add_transition("DeliveryCreated", "PickingCompleted", is_mandatory=False)
    builder.add_transition("DeliveryCreated", "GoodsIssued")
    builder.add_transition("DeliveryChanged", "PickingCompleted", is_mandatory=False)
    builder.add_transition("DeliveryChanged", "GoodsIssued")
    builder.add_transition("PickingCompleted", "PackingCompleted", is_mandatory=False)
    builder.add_transition("PickingCompleted", "GoodsIssued")
    builder.add_transition("PackingCompleted", "GoodsIssued")

    # Billing phase
    builder.add_transition("GoodsIssued", "InvoiceCreated")
    builder.add_transition("InvoiceCreated", "InvoicePosted", is_mandatory=False)
    builder.add_transition("InvoiceCreated", "PaymentReceived")
    builder.add_transition("InvoicePosted", "PaymentReceived")

    return builder.build()


def get_o2c_model(detailed: bool = False) -> ProcessModel:
    """
    Get the SAP Order-to-Cash process model.

    Args:
        detailed: If True, return detailed model; otherwise simple model

    Returns:
        ProcessModel for O2C process
    """
    if detailed:
        return get_detailed_o2c_model()
    return get_simple_o2c_model()


# Pre-defined valid and invalid trace examples for testing
VALID_O2C_TRACES: List[List[Dict[str, str]]] = [
    # Perfect trace
    [
        {"activity": "OrderCreated", "timestamp": "2024-01-01T10:00:00"},
        {"activity": "DeliveryCreated", "timestamp": "2024-01-02T10:00:00"},
        {"activity": "GoodsIssued", "timestamp": "2024-01-03T10:00:00"},
        {"activity": "InvoiceCreated", "timestamp": "2024-01-04T10:00:00"},
    ],
    # With order change (valid)
    [
        {"activity": "OrderCreated", "timestamp": "2024-01-01T10:00:00"},
        {"activity": "OrderChanged", "timestamp": "2024-01-01T14:00:00"},
        {"activity": "DeliveryCreated", "timestamp": "2024-01-02T10:00:00"},
        {"activity": "GoodsIssued", "timestamp": "2024-01-03T10:00:00"},
        {"activity": "InvoiceCreated", "timestamp": "2024-01-04T10:00:00"},
    ],
]

INVALID_O2C_TRACES: List[List[Dict[str, str]]] = [
    # Missing order (critical)
    [
        {"activity": "DeliveryCreated", "timestamp": "2024-01-02T10:00:00"},
        {"activity": "GoodsIssued", "timestamp": "2024-01-03T10:00:00"},
        {"activity": "InvoiceCreated", "timestamp": "2024-01-04T10:00:00"},
    ],
    # Invoice before goods issue (wrong order)
    [
        {"activity": "OrderCreated", "timestamp": "2024-01-01T10:00:00"},
        {"activity": "DeliveryCreated", "timestamp": "2024-01-02T10:00:00"},
        {"activity": "InvoiceCreated", "timestamp": "2024-01-03T10:00:00"},
        {"activity": "GoodsIssued", "timestamp": "2024-01-04T10:00:00"},
    ],
    # Skipped delivery
    [
        {"activity": "OrderCreated", "timestamp": "2024-01-01T10:00:00"},
        {"activity": "GoodsIssued", "timestamp": "2024-01-03T10:00:00"},
        {"activity": "InvoiceCreated", "timestamp": "2024-01-04T10:00:00"},
    ],
]
