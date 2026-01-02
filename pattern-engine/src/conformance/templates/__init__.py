"""
Pre-built Process Model Templates for SAP Conformance Checking.

This module provides ready-to-use process models for common SAP
business processes. These templates can be used directly or
customized for specific organizational needs.

Available templates:
- order_to_cash: SAP Order-to-Cash (O2C) process model

Usage:
    from conformance.templates import get_o2c_model

    model = get_o2c_model()
    # Use with ConformanceChecker
"""

from .order_to_cash import (
    get_o2c_model,
    get_simple_o2c_model,
    get_detailed_o2c_model,
    SAP_O2C_ACTIVITIES,
)

__all__ = [
    "get_o2c_model",
    "get_simple_o2c_model",
    "get_detailed_o2c_model",
    "SAP_O2C_ACTIVITIES",
]
