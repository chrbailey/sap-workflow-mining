"""
Comprehensive tests for the PII redaction module.

Tests cover:
- Email pattern detection and masking
- Phone number detection (various formats)
- Person name detection
- Address patterns
- SAP document number hashing
- Mode switching (raw_local vs shareable)
"""

import pytest
from src.redaction.redactor import (
    Redactor,
    RedactionMode,
    redact_email,
    redact_phone,
    hash_document_number,
)


class TestEmailRedaction:
    """Tests for email address redaction."""

    def test_simple_email(self):
        """Test redaction of simple email addresses."""
        redactor = Redactor(mode="shareable")
        text = "Contact john.doe@example.com for details"
        result = redactor.redact_text(text)
        assert "[EMAIL]" in result
        assert "john.doe@example.com" not in result

    def test_email_with_subdomain(self):
        """Test email with subdomain."""
        redactor = Redactor(mode="shareable")
        text = "Send to user@mail.company.co.uk"
        result = redactor.redact_text(text)
        assert "[EMAIL]" in result
        assert "user@mail.company.co.uk" not in result

    def test_email_with_plus(self):
        """Test email with plus sign."""
        redactor = Redactor(mode="shareable")
        text = "Email: user+tag@gmail.com"
        result = redactor.redact_text(text)
        assert "[EMAIL]" in result
        assert "user+tag@gmail.com" not in result

    def test_email_with_numbers(self):
        """Test email with numbers."""
        redactor = Redactor(mode="shareable")
        text = "Contact user123@company456.com"
        result = redactor.redact_text(text)
        assert "[EMAIL]" in result
        assert "user123@company456.com" not in result

    def test_multiple_emails(self):
        """Test multiple emails in text."""
        redactor = Redactor(mode="shareable")
        text = "From: alice@test.com To: bob@example.org CC: charlie@mail.net"
        result = redactor.redact_text(text)
        assert result.count("[EMAIL]") == 3
        assert "alice@test.com" not in result
        assert "bob@example.org" not in result
        assert "charlie@mail.net" not in result

    def test_email_convenience_function(self):
        """Test the convenience function."""
        result = redact_email("Send to user@domain.com")
        assert "[EMAIL]" in result
        assert "user@domain.com" not in result


class TestPhoneRedaction:
    """Tests for phone number redaction."""

    def test_us_phone_dashes(self):
        """Test US phone with dashes."""
        redactor = Redactor(mode="shareable")
        text = "Call 123-456-7890 for help"
        result = redactor.redact_text(text)
        assert "[PHONE]" in result
        assert "123-456-7890" not in result

    def test_us_phone_dots(self):
        """Test US phone with dots."""
        redactor = Redactor(mode="shareable")
        text = "Phone: 123.456.7890"
        result = redactor.redact_text(text)
        assert "[PHONE]" in result
        assert "123.456.7890" not in result

    def test_us_phone_parens(self):
        """Test US phone with parentheses."""
        redactor = Redactor(mode="shareable")
        text = "Tel: (123) 456-7890"
        result = redactor.redact_text(text)
        assert "[PHONE]" in result
        assert "(123) 456-7890" not in result

    def test_international_phone(self):
        """Test international phone format."""
        redactor = Redactor(mode="shareable")
        text = "International: +1-234-567-8900"
        result = redactor.redact_text(text)
        assert "[PHONE]" in result
        assert "+1-234-567-8900" not in result

    def test_german_phone(self):
        """Test German phone format."""
        redactor = Redactor(mode="shareable")
        text = "Kontakt: +49 (0) 123 456789"
        result = redactor.redact_text(text)
        assert "[PHONE]" in result
        assert "+49 (0) 123 456789" not in result

    def test_multiple_phones(self):
        """Test multiple phone numbers."""
        redactor = Redactor(mode="shareable")
        text = "Office: 111-222-3333, Mobile: 444-555-6666"
        result = redactor.redact_text(text)
        assert result.count("[PHONE]") >= 2

    def test_phone_convenience_function(self):
        """Test the convenience function."""
        result = redact_phone("Call 123-456-7890")
        assert "[PHONE]" in result


class TestNameRedaction:
    """Tests for person name redaction."""

    def test_name_with_salutation_mr(self):
        """Test name with Mr. salutation."""
        redactor = Redactor(mode="shareable")
        text = "Approved by Mr. John Smith"
        result = redactor.redact_text(text)
        assert "[NAME]" in result
        assert "John Smith" not in result

    def test_name_with_salutation_mrs(self):
        """Test name with Mrs. salutation."""
        redactor = Redactor(mode="shareable")
        text = "Contact Mrs. Jane Doe"
        result = redactor.redact_text(text)
        assert "[NAME]" in result
        assert "Jane Doe" not in result

    def test_name_with_salutation_dr(self):
        """Test name with Dr. salutation."""
        redactor = Redactor(mode="shareable")
        text = "Signed by Dr. Robert Brown"
        result = redactor.redact_text(text)
        assert "[NAME]" in result
        assert "Robert Brown" not in result

    def test_contact_field_pattern(self):
        """Test Contact: pattern."""
        redactor = Redactor(mode="shareable")
        text = "Contact: John Smith for questions"
        result = redactor.redact_text(text)
        assert "[NAME]" in result
        assert "John Smith" not in result

    def test_attn_field_pattern(self):
        """Test Attn: pattern."""
        redactor = Redactor(mode="shareable")
        text = "Attn: Alice Johnson"
        result = redactor.redact_text(text)
        assert "[NAME]" in result
        assert "Alice Johnson" not in result

    def test_created_by_pattern(self):
        """Test Created by: pattern."""
        redactor = Redactor(mode="shareable")
        text = "Created by: Mike Wilson"
        result = redactor.redact_text(text)
        assert "[NAME]" in result
        assert "Mike Wilson" not in result


class TestAddressRedaction:
    """Tests for address redaction."""

    def test_us_address(self):
        """Test US address format."""
        redactor = Redactor(mode="shareable")
        text = "Ship to: 123 Main Street, Springfield, IL 62701"
        result = redactor.redact_text(text)
        assert "[ADDRESS]" in result

    def test_po_box(self):
        """Test PO Box address."""
        redactor = Redactor(mode="shareable")
        text = "Mail to P.O. Box 1234"
        result = redactor.redact_text(text)
        assert "[ADDRESS]" in result
        assert "P.O. Box 1234" not in result

    def test_german_address(self):
        """Test German address format."""
        redactor = Redactor(mode="shareable")
        text = "Lieferung an Hauptstrasse 42, 10115 Berlin"
        result = redactor.redact_text(text)
        assert "[ADDRESS]" in result

    def test_postfach(self):
        """Test German Postfach."""
        redactor = Redactor(mode="shareable")
        text = "Postfach 5678"
        result = redactor.redact_text(text)
        assert "[ADDRESS]" in result


class TestSAPDocNumberHashing:
    """Tests for SAP document number hashing."""

    def test_10_digit_doc_number(self):
        """Test 10-digit SAP document number."""
        redactor = Redactor(mode="shareable", hash_sap_doc_numbers=True)
        text = "Order 1234567890 created"
        result = redactor.redact_text(text)
        assert "[DOC_" in result
        assert "1234567890" not in result

    def test_prefixed_doc_number(self):
        """Test prefixed document number."""
        redactor = Redactor(mode="shareable", hash_sap_doc_numbers=True)
        text = "Sales order SO12345678"
        result = redactor.redact_text(text)
        assert "SO[DOC_" in result or "[DOC_" in result

    def test_deterministic_hashing(self):
        """Test that hashing is deterministic."""
        redactor1 = Redactor(mode="shareable", hash_salt="test")
        redactor2 = Redactor(mode="shareable", hash_salt="test")

        result1 = redactor1.redact_text("Order 1234567890")
        result2 = redactor2.redact_text("Order 1234567890")

        assert result1 == result2

    def test_different_salt_different_hash(self):
        """Test that different salts produce different hashes."""
        redactor1 = Redactor(mode="shareable", hash_salt="salt1")
        redactor2 = Redactor(mode="shareable", hash_salt="salt2")

        result1 = redactor1.redact_text("Order 1234567890")
        result2 = redactor2.redact_text("Order 1234567890")

        assert result1 != result2

    def test_keep_doc_numbers_when_disabled(self):
        """Test that doc numbers are kept when hashing is disabled."""
        redactor = Redactor(mode="shareable", hash_sap_doc_numbers=False)
        text = "Order 1234567890 created"
        result = redactor.redact_text(text)
        assert "1234567890" in result
        assert "[DOC_" not in result

    def test_hash_document_number_function(self):
        """Test the convenience function."""
        result1 = hash_document_number("1234567890", salt="test")
        result2 = hash_document_number("1234567890", salt="test")
        assert result1 == result2
        assert "[DOC_" in result1


class TestModeSwitching:
    """Tests for redaction mode switching."""

    def test_shareable_mode_redacts(self):
        """Test that shareable mode applies redaction."""
        redactor = Redactor(mode="shareable")
        text = "Contact john@example.com at 123-456-7890"
        result = redactor.redact_text(text)

        assert "[EMAIL]" in result
        assert "[PHONE]" in result
        assert "john@example.com" not in result
        assert "123-456-7890" not in result

    def test_raw_local_mode_no_redaction(self):
        """Test that raw_local mode does not redact."""
        redactor = Redactor(mode="raw_local")
        text = "Contact john@example.com at 123-456-7890"
        result = redactor.redact_text(text)

        assert result == text
        assert "[EMAIL]" not in result
        assert "[PHONE]" not in result
        assert "john@example.com" in result

    def test_factory_shareable(self):
        """Test shareable factory method."""
        redactor = Redactor.create_shareable()
        assert redactor.config.mode == RedactionMode.SHAREABLE
        assert redactor.config.hash_sap_doc_numbers is True

    def test_factory_raw_local(self):
        """Test raw_local factory method."""
        redactor = Redactor.create_raw_local()
        assert redactor.config.mode == RedactionMode.RAW_LOCAL
        assert redactor.config.hash_sap_doc_numbers is False


class TestDocumentRedaction:
    """Tests for full document redaction."""

    def test_redact_document_dict(self):
        """Test redacting a document dictionary."""
        redactor = Redactor(mode="shareable")
        doc = {
            "order_text": "Contact john@example.com",
            "notes": "Call 123-456-7890",
            "value": 100,
        }
        result = redactor.redact_document(doc)

        assert "[EMAIL]" in result["order_text"]
        assert "[PHONE]" in result["notes"]
        assert result["value"] == 100

    def test_redact_nested_dict(self):
        """Test redacting nested dictionaries."""
        redactor = Redactor(mode="shareable")
        doc = {
            "contact": {
                "email": "test@example.com",
                "phone": "123-456-7890"
            }
        }
        result = redactor.redact_document(doc)

        assert "[EMAIL]" in result["contact"]["email"]
        assert "[PHONE]" in result["contact"]["phone"]

    def test_redact_list_in_document(self):
        """Test redacting lists in documents."""
        redactor = Redactor(mode="shareable")
        doc = {
            "emails": ["one@test.com", "two@test.com"]
        }
        result = redactor.redact_document(doc)

        assert all("[EMAIL]" in email for email in result["emails"])


class TestRedactionStats:
    """Tests for redaction statistics tracking."""

    def test_stats_tracking(self):
        """Test that stats are tracked correctly."""
        redactor = Redactor(mode="shareable")
        text = "Email: a@b.com, Phone: 123-456-7890"
        redactor.redact_text(text)

        stats = redactor.get_stats()
        assert stats['emails_redacted'] >= 1
        assert stats['phones_redacted'] >= 1
        assert stats['total_redactions'] >= 2

    def test_stats_reset(self):
        """Test stats reset."""
        redactor = Redactor(mode="shareable")
        redactor.redact_text("Email: a@b.com")

        assert redactor.get_stats()['emails_redacted'] >= 1

        redactor.reset_stats()
        assert redactor.get_stats()['emails_redacted'] == 0


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_text(self):
        """Test handling of empty text."""
        redactor = Redactor(mode="shareable")
        assert redactor.redact_text("") == ""
        assert redactor.redact_text(None) is None

    def test_no_pii(self):
        """Test text with no PII."""
        redactor = Redactor(mode="shareable")
        text = "This is a normal order with no PII"
        result = redactor.redact_text(text)
        assert result == text

    def test_mixed_pii(self):
        """Test text with various PII types."""
        redactor = Redactor(mode="shareable")
        text = (
            "Order 1234567890 for Mr. John Smith. "
            "Contact: john@company.com, Phone: 555-123-4567. "
            "Ship to 123 Main St, City, CA 90210"
        )
        result = redactor.redact_text(text)

        # Should have various redactions
        assert "[EMAIL]" in result
        assert "[PHONE]" in result
        assert "[NAME]" in result
        assert "[DOC_" in result

    def test_unicode_text(self):
        """Test handling of unicode text."""
        redactor = Redactor(mode="shareable")
        text = "Lieferung: user@example.com, Kontakt: Hans Mueller"
        result = redactor.redact_text(text)
        assert "[EMAIL]" in result

    def test_preserve_structure(self):
        """Test that text structure is preserved."""
        redactor = Redactor(mode="shareable")
        text = "Line 1\nLine 2: test@test.com\nLine 3"
        result = redactor.redact_text(text)
        assert "\n" in result
        assert result.count("\n") == 2
