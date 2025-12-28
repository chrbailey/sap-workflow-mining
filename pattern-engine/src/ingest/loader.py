"""
Data loader for MCP tool outputs and synthetic SAP data.

Loads sales_orders.json, deliveries.json, invoices.json, and doc_flow.json,
then builds unified document records with all text consolidated.

Validates schema and reports missing fields.
"""

import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of schema validation."""
    valid: bool
    missing_fields: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class LoadResult:
    """Result of data loading."""
    documents: List[Dict[str, Any]]
    validation: Dict[str, ValidationResult]
    stats: Dict[str, int]


class DataLoader:
    """Loads and unifies SAP workflow data from JSON files."""

    # Expected file names for SAP workflow data
    FILE_NAMES = {
        'sales_orders': ['sales_orders.json', 'orders.json'],
        'deliveries': ['deliveries.json', 'delivery.json'],
        'invoices': ['invoices.json', 'invoice.json', 'billing.json'],
        'doc_flow': ['doc_flow.json', 'doc_flows.json', 'document_flow.json', 'flow.json'],
        'customers': ['customers.json', 'customer.json'],
        'materials': ['materials.json', 'material.json'],
    }

    # Field name mappings: normalized name -> possible SAP field names
    # This allows the loader to handle both standard names and SAP technical names
    FIELD_MAPPINGS = {
        'document_number': ['document_number', 'vbeln', 'order_number', 'doc_number'],
        'created_date': ['created_date', 'erdat', 'order_date', 'creation_date'],
        'billing_date': ['billing_date', 'fkdat', 'invoice_date', 'erdat'],
        'requested_delivery_date': ['requested_delivery_date', 'vdatu', 'req_delivery_date'],
        'actual_gi_date': ['actual_gi_date', 'wadat_ist', 'goods_issue_date'],
        'planned_gi_date': ['planned_gi_date', 'wadat', 'lfdat', 'planned_date'],
        'customer': ['customer', 'kunnr', 'customer_id', 'sold_to', 'kunrg'],
        'customer_id': ['customer_id', 'kunnr', 'customer_number', 'id'],
        'sales_org': ['sales_org', 'vkorg', 'sales_organization'],
        'industry': ['industry', 'brsch', 'industry_code'],
        'material_id': ['material_id', 'matnr', 'material_number', 'material'],
        'preceding_doc': ['preceding_doc', 'vbelv', 'source_doc', 'from_doc'],
        'subsequent_doc': ['subsequent_doc', 'vbeln', 'target_doc', 'to_doc'],
        'preceding_category': ['preceding_category', 'vbtyp_v', 'source_category'],
        'subsequent_category': ['subsequent_category', 'vbtyp_n', 'target_category'],
        'reference_doc': ['reference_doc', 'vbeln_ref', 'ref_doc', 'source_document'],
        'reference_item': ['reference_item', 'posnr_ref', 'ref_item', 'source_item'],
        # Item fields
        'item_number': ['item_number', 'posnr', 'line_number'],
        'quantity': ['quantity', 'kwmeng', 'lfimg', 'fkimg', 'menge'],
        'delivery_quantity': ['delivery_quantity', 'lfimg', 'quantity'],
        'net_value': ['net_value', 'netwr', 'amount'],
        'item_category': ['item_category', 'pstyv', 'category'],
        # Schedule lines (VBEP)
        'schedule_lines': ['schedule_lines', 'vbep', 'schedules'],
        'confirmed_date': ['confirmed_date', 'edatu', 'delivery_date'],
        'confirmed_qty': ['confirmed_qty', 'wmeng', 'bmeng', 'confirmed_quantity'],
        # Pricing conditions (KONV)
        'conditions': ['conditions', 'konv', 'pricing_conditions'],
        'condition_type': ['condition_type', 'kschl', 'cond_type'],
        'condition_value': ['condition_value', 'kwert', 'value'],
    }

    # Required fields for schema validation (using normalized names)
    # These are checked after field normalization
    REQUIRED_FIELDS = {
        'sales_orders': ['document_number', 'created_date'],
        'deliveries': ['document_number', 'created_date'],
        'invoices': ['document_number', 'billing_date'],
        'doc_flow': ['preceding_doc', 'subsequent_doc'],
        'customers': ['customer_id'],
        'materials': ['material_id'],
    }

    # Text fields to extract from each document type
    TEXT_FIELDS = {
        'sales_orders': [
            'texts', 'header_texts', 'notes', 'reason_for_rejection',
            'customer_po_text', 'internal_notes', 'shipping_instructions',
        ],
        'deliveries': [
            'texts', 'delivery_text', 'shipping_notes', 'picking_notes',
            'goods_issue_notes', 'transport_notes',
        ],
        'invoices': [
            'texts', 'invoice_text', 'billing_notes', 'payment_terms_text',
        ],
    }

    def __init__(self):
        """Initialize the data loader."""
        self.loaded_files: Dict[str, str] = {}
        self.load_warnings: List[str] = []
        self.validation_results: Dict[str, ValidationResult] = {}

    def _normalize_field_name(self, doc: Dict[str, Any], normalized_name: str) -> Any:
        """Get a field value by trying multiple possible field names."""
        possible_names = self.FIELD_MAPPINGS.get(normalized_name, [normalized_name])
        for name in possible_names:
            if name in doc:
                return doc[name]
        return None

    def _normalize_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize field names in a document to standard names."""
        normalized = {}

        # Keep all original fields
        normalized.update(doc)

        # Add normalized versions for known fields
        for norm_name, possible_names in self.FIELD_MAPPINGS.items():
            for name in possible_names:
                if name in doc and norm_name not in normalized:
                    normalized[norm_name] = doc[name]
                    break

        return normalized

    def load_all(self, data_dir: Path) -> List[Dict[str, Any]]:
        """
        Load all available data files and build unified document records.

        Args:
            data_dir: Directory containing JSON data files

        Returns:
            List of unified document records with consolidated text
        """
        data_dir = Path(data_dir)

        if not data_dir.exists():
            logger.error(f"Data directory not found: {data_dir}")
            return []

        # Load each data type and normalize field names
        sales_orders = [self._normalize_document(d) for d in self._load_data_type(data_dir, 'sales_orders')]
        deliveries = [self._normalize_document(d) for d in self._load_data_type(data_dir, 'deliveries')]
        invoices = [self._normalize_document(d) for d in self._load_data_type(data_dir, 'invoices')]
        doc_flow = [self._normalize_document(d) for d in self._load_data_type(data_dir, 'doc_flow')]
        customers = [self._normalize_document(d) for d in self._load_data_type(data_dir, 'customers')]
        materials = [self._normalize_document(d) for d in self._load_data_type(data_dir, 'materials')]

        # Validate schemas (now using normalized field names)
        self.validation_results['sales_orders'] = self._validate_schema(sales_orders, 'sales_orders')
        self.validation_results['deliveries'] = self._validate_schema(deliveries, 'deliveries')
        self.validation_results['invoices'] = self._validate_schema(invoices, 'invoices')
        self.validation_results['doc_flow'] = self._validate_schema(doc_flow, 'doc_flow')
        self.validation_results['customers'] = self._validate_schema(customers, 'customers')
        self.validation_results['materials'] = self._validate_schema(materials, 'materials')

        # Log validation results
        for data_type, result in self.validation_results.items():
            if not result.valid:
                logger.warning(f"Validation issues in {data_type}: {result.errors}")
            if result.missing_fields:
                logger.info(f"Missing optional fields in {data_type}: {result.missing_fields}")

        # Build indexes for efficient lookups
        customer_index = {c.get('customer_id') or c.get('kunnr'): c for c in customers}
        material_index = {m.get('material_id') or m.get('matnr') or m.get('material'): m for m in materials}

        # Build delivery and invoice indexes by reference doc
        delivery_by_order = self._build_delivery_index(deliveries, doc_flow)
        invoice_by_delivery = self._build_invoice_index(invoices, doc_flow)

        # Build unified records
        unified_records = self._build_unified_records(
            sales_orders=sales_orders,
            deliveries=deliveries,
            invoices=invoices,
            doc_flow=doc_flow,
            customer_index=customer_index,
            material_index=material_index,
            delivery_by_order=delivery_by_order,
            invoice_by_delivery=invoice_by_delivery,
        )

        logger.info(f"Built {len(unified_records)} unified document records")
        return unified_records

    def _load_data_type(self, data_dir: Path, data_type: str) -> List[Dict[str, Any]]:
        """Load data for a specific type, trying multiple possible file names."""
        for filename in self.FILE_NAMES.get(data_type, []):
            file_path = data_dir / filename
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Handle both direct list and dict with nested data
                    if isinstance(data, dict):
                        # Check for common wrapper keys
                        for key in ['sales_orders', 'deliveries', 'invoices',
                                   'document_flows', 'customers', 'materials',
                                   'results', 'data', 'items']:
                            if key in data:
                                data = data[key]
                                break
                        else:
                            # Single record, wrap in list
                            if 'metadata' not in data:
                                data = [data]
                            else:
                                # Has metadata but no known key, try to extract
                                data = []

                    if not isinstance(data, list):
                        data = [data] if data else []

                    self.loaded_files[data_type] = str(file_path)
                    logger.info(f"Loaded {len(data)} {data_type} records from {filename}")
                    return data

                except json.JSONDecodeError as e:
                    self.load_warnings.append(f"Failed to parse {filename}: {e}")
                    logger.warning(f"Failed to parse {filename}: {e}")
                except Exception as e:
                    self.load_warnings.append(f"Error loading {filename}: {e}")
                    logger.warning(f"Error loading {filename}: {e}")

        logger.debug(f"No {data_type} file found in {data_dir}")
        return []

    def _validate_schema(self, docs: List[Dict], data_type: str) -> ValidationResult:
        """Validate documents against expected schema.

        EDGE CASE FIX: Uses random sampling instead of first-N to catch schema
        variations that might appear later in the data.
        """
        result = ValidationResult(valid=True)
        required = self.REQUIRED_FIELDS.get(data_type, [])

        if not docs:
            result.warnings.append(f"No {data_type} documents loaded")
            return result

        # EDGE CASE FIX: Use random sample instead of first N documents
        # This catches schema variations that might appear later in the file
        sample_size = min(20, len(docs))  # Increased from 10 to 20
        if len(docs) > sample_size:
            # Use deterministic random for reproducibility
            rng = random.Random(42)
            sample_indices = rng.sample(range(len(docs)), sample_size)
            sample_docs = [docs[i] for i in sample_indices]
        else:
            sample_docs = docs

        missing_counts: Dict[str, int] = {}

        for doc in sample_docs:
            for field_name in required:
                if field_name not in doc or doc[field_name] is None:
                    missing_counts[field_name] = missing_counts.get(field_name, 0) + 1

        # Report fields missing in majority of sample
        for field_name, count in missing_counts.items():
            if count == len(sample_docs):
                result.errors.append(f"Required field '{field_name}' missing in all sampled documents")
                result.valid = False
            elif count > len(sample_docs) // 2:
                result.missing_fields.append(field_name)
                result.warnings.append(
                    f"Field '{field_name}' missing in {count}/{len(sample_docs)} "
                    f"randomly sampled documents (sample from {len(docs)} total)"
                )

        return result

    def _build_delivery_index(
        self,
        deliveries: List[Dict],
        doc_flow: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """Build index of deliveries by sales order number."""
        index: Dict[str, List[Dict]] = {}

        # Direct reference from delivery items
        for delivery in deliveries:
            for item in delivery.get('items', []):
                # Try multiple field names for reference document
                ref_doc = item.get('reference_doc') or item.get('vbeln_ref')
                if ref_doc:
                    if ref_doc not in index:
                        index[ref_doc] = []
                    if delivery not in index[ref_doc]:
                        index[ref_doc].append(delivery)

        # Also check doc_flow for order->delivery links
        # Category C = Sales Order, J = Delivery
        for flow in doc_flow:
            if flow.get('preceding_category') == 'C' and flow.get('subsequent_category') == 'J':
                order_num = flow.get('preceding_doc')
                delivery_num = flow.get('subsequent_doc')
                if order_num and delivery_num:
                    # Find the delivery
                    for delivery in deliveries:
                        if delivery.get('document_number') == delivery_num:
                            if order_num not in index:
                                index[order_num] = []
                            if delivery not in index[order_num]:
                                index[order_num].append(delivery)
                            break

        return index

    def _build_invoice_index(
        self,
        invoices: List[Dict],
        doc_flow: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """Build index of invoices by delivery number."""
        index: Dict[str, List[Dict]] = {}

        # Direct reference from invoice items
        for invoice in invoices:
            for item in invoice.get('items', []):
                # Try multiple field names for reference document
                ref_doc = item.get('reference_doc') or item.get('vbeln_ref')
                if ref_doc:
                    if ref_doc not in index:
                        index[ref_doc] = []
                    if invoice not in index[ref_doc]:
                        index[ref_doc].append(invoice)

        # Also check doc_flow for delivery->invoice links
        # Category J = Delivery, M = Invoice
        for flow in doc_flow:
            if flow.get('preceding_category') == 'J' and flow.get('subsequent_category') == 'M':
                delivery_num = flow.get('preceding_doc')
                invoice_num = flow.get('subsequent_doc')
                if delivery_num and invoice_num:
                    for invoice in invoices:
                        if invoice.get('document_number') == invoice_num:
                            if delivery_num not in index:
                                index[delivery_num] = []
                            if invoice not in index[delivery_num]:
                                index[delivery_num].append(invoice)
                            break

        return index

    def _build_unified_records(
        self,
        sales_orders: List[Dict],
        deliveries: List[Dict],
        invoices: List[Dict],
        doc_flow: List[Dict],
        customer_index: Dict[str, Dict],
        material_index: Dict[str, Dict],
        delivery_by_order: Dict[str, List[Dict]],
        invoice_by_delivery: Dict[str, List[Dict]],
    ) -> List[Dict[str, Any]]:
        """Build unified document records by joining related documents."""
        unified_records = []

        for order in sales_orders:
            order_num = order.get('document_number')
            if not order_num:
                continue

            # Get related deliveries
            related_deliveries = delivery_by_order.get(order_num, [])

            # Get related invoices (through deliveries)
            related_invoices = []
            for delivery in related_deliveries:
                delivery_num = delivery.get('document_number')
                if delivery_num:
                    related_invoices.extend(invoice_by_delivery.get(delivery_num, []))

            # Remove duplicates while preserving order
            seen_invoices = set()
            unique_invoices = []
            for inv in related_invoices:
                inv_num = inv.get('document_number')
                if inv_num and inv_num not in seen_invoices:
                    seen_invoices.add(inv_num)
                    unique_invoices.append(inv)
            related_invoices = unique_invoices

            # Get customer info
            customer_id = order.get('customer')
            customer_info = customer_index.get(customer_id, {})

            # Build unified record
            unified = self._create_unified_record(
                doc_key=order_num,
                order=order,
                deliveries=related_deliveries,
                invoices=related_invoices,
                customer=customer_info,
            )

            unified_records.append(unified)

        return unified_records

    def _create_unified_record(
        self,
        doc_key: str,
        order: Dict,
        deliveries: List[Dict],
        invoices: List[Dict],
        customer: Dict,
    ) -> Dict[str, Any]:
        """Create a unified document record with consolidated text."""
        # Collect all text fields
        all_texts = []

        # Extract texts from order
        all_texts.extend(self._extract_texts(order, 'sales_orders'))

        # Extract texts from deliveries
        for delivery in deliveries:
            all_texts.extend(self._extract_texts(delivery, 'deliveries'))

        # Extract texts from invoices
        for invoice in invoices:
            all_texts.extend(self._extract_texts(invoice, 'invoices'))

        # Consolidate text
        consolidated_text = ' '.join(filter(None, all_texts))

        # Extract dates for timing analysis
        dates = self._extract_dates(order, deliveries, invoices)

        # Calculate timing metrics
        timing = self._calculate_timing(dates)

        # Get additional metadata
        sales_org = order.get('sales_org', '')
        customer_industry = customer.get('industry', '')

        return {
            'doc_key': doc_key,
            'consolidated_text': consolidated_text,
            'order': order,
            'deliveries': deliveries,
            'invoices': invoices,
            'customer': customer,
            'dates': dates,
            'timing': timing,
            'sales_org': sales_org,
            'customer_industry': customer_industry,
            'source_files': list(self.loaded_files.values()),
            'n_deliveries': len(deliveries),
            'n_invoices': len(invoices),
        }

    def _extract_texts(self, doc: Dict, doc_type: str) -> List[str]:
        """Extract text fields from a document."""
        texts = []
        text_fields = self.TEXT_FIELDS.get(doc_type, [])

        for field in text_fields:
            value = doc.get(field)
            if value:
                if isinstance(value, str):
                    texts.append(value.strip())
                elif isinstance(value, list):
                    # Handle list of text objects (common in SAP)
                    for item in value:
                        if isinstance(item, str):
                            texts.append(item.strip())
                        elif isinstance(item, dict):
                            # Extract text_content from text objects
                            text_content = item.get('text_content') or item.get('text') or item.get('content')
                            if text_content:
                                texts.append(str(text_content).strip())

        # Also check for nested texts in items
        for item in doc.get('items', []):
            if isinstance(item, dict):
                # Item-level texts
                for field in ['texts', 'item_text', 'description']:
                    value = item.get(field)
                    if value:
                        if isinstance(value, str):
                            texts.append(value.strip())
                        elif isinstance(value, list):
                            for text_item in value:
                                if isinstance(text_item, str):
                                    texts.append(text_item.strip())
                                elif isinstance(text_item, dict):
                                    text_content = text_item.get('text_content') or text_item.get('text')
                                    if text_content:
                                        texts.append(str(text_content).strip())

        return texts

    def _extract_dates(
        self,
        order: Dict,
        deliveries: List[Dict],
        invoices: List[Dict]
    ) -> Dict[str, Optional[str]]:
        """Extract relevant dates from documents."""
        dates = {
            'order_date': None,
            'requested_delivery_date': None,
            'actual_delivery_date': None,
            'invoice_date': None,
        }

        # Order dates
        dates['order_date'] = order.get('created_date')
        dates['requested_delivery_date'] = order.get('requested_delivery_date')

        # Delivery date - use actual GI date or planned
        if deliveries:
            delivery_dates = []
            for d in deliveries:
                # Prefer actual_gi_date over planned_gi_date
                dd = d.get('actual_gi_date') or d.get('planned_gi_date') or d.get('created_date')
                if dd:
                    delivery_dates.append(dd)
            if delivery_dates:
                # Use earliest delivery date
                dates['actual_delivery_date'] = min(delivery_dates)

        # Invoice date
        if invoices:
            invoice_dates = []
            for i in invoices:
                id_date = i.get('billing_date') or i.get('created_date')
                if id_date:
                    invoice_dates.append(id_date)
            if invoice_dates:
                dates['invoice_date'] = min(invoice_dates)

        return dates

    def _calculate_timing(self, dates: Dict[str, Optional[str]]) -> Dict[str, Optional[float]]:
        """Calculate timing metrics from dates."""
        timing = {
            'order_to_delivery_days': None,
            'delivery_delay_days': None,
            'invoice_lag_days': None,
            'order_to_invoice_days': None,
        }

        order_date = self._parse_date(dates.get('order_date'))
        requested_date = self._parse_date(dates.get('requested_delivery_date'))
        delivery_date = self._parse_date(dates.get('actual_delivery_date'))
        invoice_date = self._parse_date(dates.get('invoice_date'))

        if order_date and delivery_date:
            timing['order_to_delivery_days'] = (delivery_date - order_date).days

        if requested_date and delivery_date:
            timing['delivery_delay_days'] = (delivery_date - requested_date).days

        if delivery_date and invoice_date:
            timing['invoice_lag_days'] = (invoice_date - delivery_date).days

        if order_date and invoice_date:
            timing['order_to_invoice_days'] = (invoice_date - order_date).days

        return timing

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse a date string into a datetime object.

        EDGE CASE FIX: All returned datetimes are normalized to timezone-naive UTC
        to prevent TypeError when subtracting mixed timezone-aware/naive datetimes.
        """
        if not date_str:
            return None

        # Handle datetime objects passed directly
        if isinstance(date_str, datetime):
            # Normalize to timezone-naive UTC
            if date_str.tzinfo is not None:
                return date_str.astimezone(timezone.utc).replace(tzinfo=None)
            return date_str

        # Try common date formats
        # Note: Formats with Z or timezone info are handled specially below
        formats = [
            '%Y-%m-%d',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%d.%m.%Y',  # German format
            '%m/%d/%Y',  # US format
            '%d/%m/%Y',  # European format
            '%Y%m%d',    # SAP format
        ]

        date_str_clean = str(date_str).strip()

        # Handle ISO format with Z (UTC indicator) - normalize to naive UTC
        if date_str_clean.endswith('Z'):
            date_str_no_z = date_str_clean[:-1]
            for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f']:
                try:
                    # Parse as UTC, return as naive datetime
                    return datetime.strptime(date_str_no_z, fmt)
                except ValueError:
                    continue

        # Handle timezone offset format (+00:00, -05:00, etc.)
        if len(date_str_clean) > 6 and ('+' in date_str_clean[-6:] or date_str_clean[-6:-5] == '-'):
            try:
                # Python 3.7+ can parse ISO format with timezone
                dt = datetime.fromisoformat(date_str_clean)
                # Normalize to naive UTC
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            except ValueError:
                pass

        for fmt in formats:
            try:
                return datetime.strptime(date_str_clean, fmt)
            except ValueError:
                continue

        logger.debug(f"Could not parse date: {date_str}")
        return None

    def get_validation_report(self) -> Dict[str, Any]:
        """Get a summary of validation results."""
        return {
            data_type: {
                'valid': result.valid,
                'missing_fields': result.missing_fields,
                'warnings': result.warnings,
                'errors': result.errors,
            }
            for data_type, result in self.validation_results.items()
        }

    def get_load_stats(self) -> Dict[str, int]:
        """Get statistics about loaded data."""
        return {
            'files_loaded': len(self.loaded_files),
            'warnings': len(self.load_warnings),
        }


def load_json_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load a single JSON file.

    Args:
        file_path: Path to the JSON file

    Returns:
        Parsed JSON data or None if loading fails
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load {file_path}: {e}")
        return None


def load_all_data(input_dir: str) -> List[Dict[str, Any]]:
    """
    Convenience function to load all data from a directory.

    Args:
        input_dir: Path to directory containing JSON files

    Returns:
        List of unified document records
    """
    loader = DataLoader()
    return loader.load_all(Path(input_dir))
