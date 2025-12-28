"""
Pytest configuration and fixtures for pattern engine tests.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Define package aliases for test imports
# Tests can import using pattern_engine.xxx or src.xxx
import importlib.util
src_path = project_root / 'src'

# Try to set up pattern_engine as an alias for src
try:
    import src
    sys.modules['pattern_engine'] = src
except ImportError:
    pass


@pytest.fixture
def sample_sales_orders():
    """Sample sales order data for testing."""
    return [
        {
            'order_number': 'SO0001',
            'order_date': '2024-01-15',
            'requested_delivery_date': '2024-01-22',
            'order_text': 'EXPEDITE this order - customer is VIP. Rush delivery required.',
            'customer_po_text': 'PO-12345',
            'internal_notes': 'High priority customer, expedite processing',
        },
        {
            'order_number': 'SO0002',
            'order_date': '2024-01-16',
            'requested_delivery_date': '2024-01-30',
            'order_text': 'Standard order, normal processing.',
            'customer_po_text': 'PO-12346',
            'internal_notes': 'Regular customer order',
        },
        {
            'order_number': 'SO0003',
            'order_date': '2024-01-17',
            'requested_delivery_date': '2024-01-25',
            'order_text': 'CREDIT HOLD - payment pending. Do not ship.',
            'customer_po_text': 'PO-12347',
            'internal_notes': 'Customer has outstanding invoices',
        },
    ]


@pytest.fixture
def sample_deliveries():
    """Sample delivery data for testing."""
    return [
        {
            'delivery_number': 'DL0001',
            'sales_order': 'SO0001',
            'delivery_date': '2024-01-20',
            'delivery_text': 'Express shipping arranged. Carrier: FedEx Priority.',
        },
        {
            'delivery_number': 'DL0002',
            'sales_order': 'SO0002',
            'delivery_date': '2024-01-28',
            'delivery_text': 'Standard ground shipping.',
        },
    ]


@pytest.fixture
def sample_invoices():
    """Sample invoice data for testing."""
    return [
        {
            'invoice_number': 'IV0001',
            'sales_order': 'SO0001',
            'invoice_date': '2024-01-21',
            'invoice_text': 'Invoice for expedited order.',
        },
        {
            'invoice_number': 'IV0002',
            'sales_order': 'SO0002',
            'invoice_date': '2024-01-30',
            'invoice_text': 'Standard terms invoice.',
        },
    ]


@pytest.fixture
def sample_unified_documents():
    """Sample unified documents with timing data."""
    return [
        {
            'doc_key': 'SO0001',
            'consolidated_text': 'EXPEDITE this order rush delivery VIP customer priority',
            'timing': {
                'order_to_delivery_days': 5,
                'delivery_delay_days': -2,  # Early delivery
                'invoice_lag_days': 1,
                'order_to_invoice_days': 6,
            },
            'n_deliveries': 1,
            'sales_org': 'US01',
            'customer_industry': 'Manufacturing',
        },
        {
            'doc_key': 'SO0002',
            'consolidated_text': 'Standard order normal processing regular shipping',
            'timing': {
                'order_to_delivery_days': 12,
                'delivery_delay_days': -2,  # Early delivery
                'invoice_lag_days': 2,
                'order_to_invoice_days': 14,
            },
            'n_deliveries': 1,
            'sales_org': 'US01',
            'customer_industry': 'Retail',
        },
        {
            'doc_key': 'SO0003',
            'consolidated_text': 'Credit hold blocked payment pending customer',
            'timing': {
                'order_to_delivery_days': None,
                'delivery_delay_days': None,
                'invoice_lag_days': None,
                'order_to_invoice_days': None,
            },
            'n_deliveries': 0,
            'sales_org': 'EU01',
            'customer_industry': 'Services',
        },
    ]


@pytest.fixture
def sample_cluster_result():
    """Sample clustering result."""
    return {
        'labels': [0, 1, 2],
        'n_clusters': 3,
        'cluster_info': {
            0: {'n_documents': 1, 'avg_text_length': 50, 'percentage': 33.3},
            1: {'n_documents': 1, 'avg_text_length': 45, 'percentage': 33.3},
            2: {'n_documents': 1, 'avg_text_length': 40, 'percentage': 33.3},
        },
        'top_phrases': {
            0: [('expedite', 0.5), ('rush', 0.4), ('priority', 0.3)],
            1: [('standard', 0.5), ('normal', 0.4), ('regular', 0.3)],
            2: [('credit', 0.5), ('hold', 0.4), ('blocked', 0.3)],
        },
        'parameters': {
            'embedding_model': 'tfidf',
            'clustering_algorithm': 'kmeans',
            'n_clusters': 3,
            'min_cluster_size': 1,
            'random_seed': 42,
        },
    }
