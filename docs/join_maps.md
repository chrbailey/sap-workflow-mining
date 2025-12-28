# SAP Document Relationships - Join Maps

> **Warning**: SAP table structures vary by version, industry solution, and customization. This document describes standard ECC 6.0 / S/4HANA structures. Your system may differ. Verify with SE11/SE16 or your DBA.

## Overview

SAP SD (Sales & Distribution) documents are interconnected through a web of header/item tables and linking tables. Understanding these relationships is essential for tracing document flows and correlating text patterns to outcomes.

```
                        SAP SD Document Flow Overview
                        =============================

    +-------------+           +-------------+           +-------------+
    | Sales Order |           |  Delivery   |           |   Invoice   |
    |   (VA01)    |---------->|   (VL01N)   |---------->|   (VF01)    |
    +-------------+           +-------------+           +-------------+
          |                         |                         |
          |  VBAK/VBAP              |  LIKP/LIPS              |  VBRK/VBRP
          |  (Header/Item)          |  (Header/Item)          |  (Header/Item)
          |                         |                         |
          +-----------+-------------+-----------+-------------+
                      |                         |
                      v                         v
                 +----------+             +----------+
                 |   VBFA   |             |   VBFA   |
                 | Doc Flow |             | Doc Flow |
                 +----------+             +----------+

    VBFA: The central linking table that connects all document types
```

## The VBFA Table (Document Flow)

VBFA (Verkaufsbeleg-Fluss-Analyse) is the central table that links SD documents together. It records the predecessor-successor relationships between documents.

### Key Fields in VBFA

| Field | Description | Example |
|-------|-------------|---------|
| VBELV | Preceding document number | 0000012345 (Order) |
| POSNV | Preceding item number | 000010 |
| VBELN | Subsequent document number | 0080012345 (Delivery) |
| POSNN | Subsequent item number | 000010 |
| VBTYP_N | Subsequent document category | 'J' = Delivery |
| VBTYP_V | Preceding document category | 'C' = Order |
| RFMNG | Reference quantity | 100.000 |
| RFWRT | Reference value | 5000.00 |
| ERDAT | Creation date | 2024-01-15 |
| ERZET | Creation time | 10:30:45 |

### VBTYP Values (Document Categories)

| VBTYP | Category | Description |
|-------|----------|-------------|
| A | Inquiry | VA11 |
| B | Quotation | VA21 |
| C | Order | VA01 (Standard Order) |
| D | Item Proposal | |
| E | Scheduling Agreement | VA31 |
| F | Scheduling Agreement Schedule | |
| G | Contract | VA41 |
| H | Returns | VA01 (Returns Order) |
| I | Free-of-charge delivery (subsequent) | |
| J | Delivery | VL01N |
| K | Credit Memo Request | VA01 |
| L | Debit Memo Request | VA01 |
| M | Invoice | VF01 |
| N | Invoice Cancellation | VF11 |
| O | Credit Memo | VF01 |
| P | Debit Memo | VF01 |
| Q | WMS Transfer Order | |
| R | Goods Movement | MIGO |
| S | Credit Memo Cancellation | |
| T | Returns Delivery | VL01N |
| U | Pro Forma Invoice | |
| V | Cash Sale | VA01 |
| W | Independent Requirements | |
| X | Handling Unit | |

## Sales Order Tables (VBAK/VBAP)

### VBAK - Sales Document Header

| Field | Description | Relevant For |
|-------|-------------|--------------|
| VBELN | Document number (10 chars) | Primary key |
| AUDAT | Document date | Timing analysis |
| VBTYP | SD document category | Doc type classification |
| AUART | Document type (OR, SO, RE, etc.) | Process variant |
| VKORG | Sales organization | Org analysis |
| VTWEG | Distribution channel | Channel analysis |
| SPART | Division | Product line |
| KUNNR | Sold-to party | Customer link |
| BSTNK | Customer PO number | External reference |
| ERDAT | Created on | Timing analysis |
| ERZET | Created at (time) | Timing analysis |
| ERNAM | Created by | User analysis |
| AEDAT | Changed on | Change tracking |
| VDATU | Requested delivery date | Lead time analysis |
| NETWR | Net value | Value analysis |
| WAERK | Currency | Value normalization |

### VBAP - Sales Document Items

| Field | Description | Relevant For |
|-------|-------------|--------------|
| VBELN | Document number | Header link |
| POSNR | Item number (6 chars) | Item key |
| MATNR | Material number | Product analysis |
| ARKTX | Short text | Text mining |
| KWMENG | Order quantity | Volume analysis |
| VRKME | Sales unit | Unit normalization |
| NETWR | Net value | Value analysis |
| WERKS | Plant | Fulfillment analysis |
| LGORT | Storage location | Inventory analysis |
| ROUTE | Route | Logistics analysis |
| ABGRU | Rejection reason | Issue analysis |
| PSTYV | Item category | Process variant |

## Delivery Tables (LIKP/LIPS)

### LIKP - Delivery Header

| Field | Description | Relevant For |
|-------|-------------|--------------|
| VBELN | Delivery number (10 chars) | Primary key |
| LFART | Delivery type (LF, LO, etc.) | Process variant |
| ERDAT | Created on | Timing analysis |
| ERZET | Created at | Timing analysis |
| ERNAM | Created by | User analysis |
| LFDAT | Delivery date | Timing analysis |
| WADAT | Goods issue date (planned) | Lead time |
| WADAT_IST | Goods issue date (actual) | Actual vs plan |
| KUNNR | Ship-to party | Customer link |
| KUNAG | Sold-to party | Customer link |
| VSTEL | Shipping point | Logistics |
| ROUTE | Route | Logistics |
| BTGEW | Total weight | Shipping analysis |
| NTGEW | Net weight | Shipping analysis |
| GEWEI | Weight unit | Normalization |

### LIPS - Delivery Items

| Field | Description | Relevant For |
|-------|-------------|--------------|
| VBELN | Delivery number | Header link |
| POSNR | Item number | Item key |
| MATNR | Material | Product link |
| ARKTX | Short text | Text mining |
| LFIMG | Delivery quantity | Volume analysis |
| VRKME | Sales unit | Normalization |
| VGBEL | Reference document (order) | Order link |
| VGPOS | Reference item | Order item link |
| WERKS | Plant | Fulfillment |
| LGORT | Storage location | Inventory |
| CHARG | Batch number | Traceability |

## Invoice Tables (VBRK/VBRP)

### VBRK - Billing Document Header

| Field | Description | Relevant For |
|-------|-------------|--------------|
| VBELN | Billing document number | Primary key |
| FKART | Billing type (F2, RE, etc.) | Process variant |
| FKDAT | Billing date | Timing analysis |
| ERDAT | Created on | Timing analysis |
| ERZET | Created at | Timing analysis |
| ERNAM | Created by | User analysis |
| KUNRG | Payer | Customer link |
| KUNAG | Sold-to party | Customer link |
| NETWR | Net value | Value analysis |
| WAERK | Currency | Normalization |
| FKSTO | Cancelled | Status filtering |
| SFAKN | Cancellation document | Link to cancellation |

### VBRP - Billing Document Items

| Field | Description | Relevant For |
|-------|-------------|--------------|
| VBELN | Billing number | Header link |
| POSNR | Item number | Item key |
| MATNR | Material | Product link |
| ARKTX | Short text | Text mining |
| FKIMG | Billing quantity | Volume analysis |
| VRKME | Sales unit | Normalization |
| NETWR | Net value | Value analysis |
| AUBEL | Sales document (order) | Order link |
| AUPOS | Sales item | Order item link |
| VGBEL | Reference document | Delivery link |
| VGPOS | Reference item | Delivery item link |

## Document Flow Relationships

### Order to Delivery

```
    VBAK (Order Header)
       |
       | VBELN = '0000012345'
       v
    VBAP (Order Items)
       |
       | VBELN = '0000012345', POSNR = '000010'
       v
    VBFA (Document Flow)
       |
       | VBELV = '0000012345', POSNV = '000010'
       | VBTYP_V = 'C' (Order)
       | VBTYP_N = 'J' (Delivery)
       | VBELN = '0080012345', POSNN = '000010'
       v
    LIPS (Delivery Items)
       |
       | VBELN = '0080012345', POSNR = '000010'
       v
    LIKP (Delivery Header)
       |
       | VBELN = '0080012345'
```

**Query pattern (pseudo-SQL)**:
```sql
-- Find all deliveries for an order
SELECT likp.*, lips.*
FROM vbfa
JOIN likp ON vbfa.vbeln = likp.vbeln
JOIN lips ON vbfa.vbeln = lips.vbeln AND vbfa.posnn = lips.posnr
WHERE vbfa.vbelv = :order_number
  AND vbfa.vbtyp_n = 'J'  -- Delivery
```

### Delivery to Invoice

```
    LIKP (Delivery Header)
       |
       | VBELN = '0080012345'
       v
    LIPS (Delivery Items)
       |
       | VBELN = '0080012345', POSNR = '000010'
       v
    VBFA (Document Flow)
       |
       | VBELV = '0080012345', POSNV = '000010'
       | VBTYP_V = 'J' (Delivery)
       | VBTYP_N = 'M' (Invoice)
       | VBELN = '0090012345', POSNN = '000010'
       v
    VBRP (Invoice Items)
       |
       | VBELN = '0090012345', POSNR = '000010'
       v
    VBRK (Invoice Header)
       |
       | VBELN = '0090012345'
```

**Query pattern**:
```sql
-- Find all invoices for a delivery
SELECT vbrk.*, vbrp.*
FROM vbfa
JOIN vbrk ON vbfa.vbeln = vbrk.vbeln
JOIN vbrp ON vbfa.vbeln = vbrp.vbeln AND vbfa.posnn = vbrp.posnr
WHERE vbfa.vbelv = :delivery_number
  AND vbfa.vbtyp_n = 'M'  -- Invoice
```

### Complete Flow (Order to Invoice)

```
    +-------------------+
    |   VBAK (Order)    |
    | VBELN: 0000012345 |
    | AUDAT: 2024-01-01 |
    +-------------------+
            |
            | (1:n - order may split to multiple deliveries)
            v
    +-----------------------+     +-----------------------+
    | VBFA                  |     | VBFA                  |
    | VBELV: 0000012345     |     | VBELV: 0000012345     |
    | VBELN: 0080000001     |     | VBELN: 0080000002     |
    | VBTYP_N: J (Delivery) |     | VBTYP_N: J (Delivery) |
    +-----------------------+     +-----------------------+
            |                             |
            v                             v
    +-------------------+         +-------------------+
    |  LIKP (Delivery)  |         |  LIKP (Delivery)  |
    | VBELN: 0080000001 |         | VBELN: 0080000002 |
    | LFDAT: 2024-01-03 |         | LFDAT: 2024-01-10 |
    +-------------------+         +-------------------+
            |                             |
            v                             v
    +-----------------------+     +-----------------------+
    | VBFA                  |     | VBFA                  |
    | VBELV: 0080000001     |     | VBELV: 0080000002     |
    | VBELN: 0090000001     |     | VBELN: 0090000002     |
    | VBTYP_N: M (Invoice)  |     | VBTYP_N: M (Invoice)  |
    +-----------------------+     +-----------------------+
            |                             |
            v                             v
    +-------------------+         +-------------------+
    |  VBRK (Invoice)   |         |  VBRK (Invoice)   |
    | VBELN: 0090000001 |         | VBELN: 0090000002 |
    | FKDAT: 2024-01-05 |         | FKDAT: 2024-01-12 |
    +-------------------+         +-------------------+
```

## Text Tables

SAP stores document text in separate text tables. There are two major frameworks:

### SAPscript Texts (Older, Still Common)

**STXH** - Text Header
| Field | Description |
|-------|-------------|
| TDOBJECT | Text object (e.g., VBBK = SD doc header) |
| TDNAME | Text name (usually document number) |
| TDID | Text ID (e.g., 0001 = header text) |
| TDSPRAS | Language key |

**STXL** - Text Lines
| Field | Description |
|-------|-------------|
| RELID | (Key field) |
| TDOBJECT | Text object |
| TDNAME | Text name |
| TDID | Text ID |
| TDSPRAS | Language |
| CLUSTR | Text lines (cluster) |

**Common TDOBJECT/TDID combinations**:
| TDOBJECT | TDID | Description |
|----------|------|-------------|
| VBBK | 0001 | SD header text |
| VBBK | 0002 | Internal note |
| VBBP | 0001 | SD item text |
| VBBP | Z001 | Custom item text |

**Query pattern** (requires READ_TEXT function):
```abap
CALL FUNCTION 'READ_TEXT'
  EXPORTING
    id       = '0001'
    language = 'E'
    name     = lv_vbeln
    object   = 'VBBK'
  TABLES
    lines    = lt_lines.
```

### Note: STXL is Clustered

STXL stores text as compressed clusters, not as plain rows. You cannot query it directly with RFC_READ_TABLE. You must use:
- READ_TEXT function module
- Custom wrapper function
- CDS view (S/4HANA)

### Partner Functions (VBPA)

**VBPA** - Document Partner Table
| Field | Description |
|-------|-------------|
| VBELN | Document number |
| POSNR | Item number (blank for header partner) |
| PARVW | Partner function |
| KUNNR | Customer number |
| ADRNR | Address number |

**Common PARVW values**:
| PARVW | Description |
|-------|-------------|
| AG | Sold-to party |
| WE | Ship-to party |
| RG | Payer |
| RE | Bill-to party |
| SP | Contact person |

## Relationship Diagram

```
                        SAP SD Table Relationships
    ================================================================

                           +--------+
                           | STXH   |........> STXL (Text)
                           | STXL   |
                           +--------+
                               ^
                               | TDOBJECT='VBBK/VBBP'
                               |
    +--------+             +--------+             +--------+
    | KNA1   |             | VBAK   |<---+------->| VBPA   |
    |Customer|<---KUNNR----|Order Hdr|   |POSNR=''|Partners|
    +--------+             +--------+   |        +--------+
                               |        |
                               |        |
                           +--------+   |
                           | VBAP   |---+
                           |Order Itm|   POSNR
                           +--------+
                               |
                               | VBELV, POSNV
                               v
                           +--------+
                           | VBFA   |
                           |Doc Flow|
                           +--------+
                               |
                               | VBELN, POSNN, VBTYP_N
                               v
         +-------------------------------------------------+
         |                       |                         |
    VBTYP_N='J'             VBTYP_N='M'             VBTYP_N='R'
         |                       |                         |
         v                       v                         v
    +--------+             +--------+             +--------+
    | LIKP   |             | VBRK   |             | MKPF   |
    |Del Hdr |             |Inv Hdr |             |Mat Doc |
    +--------+             +--------+             +--------+
         |                       |
    +--------+             +--------+
    | LIPS   |             | VBRP   |
    |Del Item|             |Inv Item|
    +--------+             +--------+


    Legend:
    -------> Primary key relationship
    ........> Logical relationship (requires function call)
    FIELD     Field used for join
```

## Common Query Patterns

### 1. Get Complete Order Flow

```
Input: Order number (VBELN)
Output: All deliveries and invoices

Steps:
1. Query VBAK for order header
2. Query VBAP for order items
3. Query VBFA where VBELV = order and VBTYP_N = 'J'
4. For each delivery VBELN from step 3:
   - Query LIKP for delivery header
   - Query LIPS for delivery items
   - Query VBFA where VBELV = delivery and VBTYP_N = 'M'
5. For each invoice VBELN from step 4:
   - Query VBRK for invoice header
   - Query VBRP for invoice items
```

### 2. Calculate Order-to-Delivery Time

```
Formula: LIKP-WADAT_IST - VBAK-ERDAT

Caveats:
- WADAT_IST may be blank (no goods issue yet)
- Multiple deliveries = multiple times
- Use earliest/latest/weighted average as needed
```

### 3. Find Orders with Text Pattern

```
Steps:
1. READ_TEXT for VBBK/0001 for candidate orders
2. Search text lines for pattern
3. Return matching VBELN values

Note: This is expensive. Consider search helps or custom indexes.
```

### 4. Get All Partners for a Document

```sql
SELECT kunnr, parvw
FROM vbpa
WHERE vbeln = :order_number
  AND posnr = '000000'  -- Header level
ORDER BY parvw
```

## Timing Fields Reference

The following fields are critical for cycle time and delay analysis:

### Creation Timestamps

| Field | Table | Description |
|-------|-------|-------------|
| ERDAT | All | Creation date (YYYYMMDD) |
| ERZET | All | Creation time (HHMMSS) |

### Delivery-Related Timing

| Field | Table | Description |
|-------|-------|-------------|
| VDATU | VBAK | Requested delivery date (from order) |
| WADAT | LIKP | Planned goods issue date |
| WADAT_IST | LIKP | Actual goods issue date |
| LFDAT | LIKP | Delivery date |
| LDDAT | LIKP | Loading date |
| TDDAT | LIKP | Transportation planning date |

### Billing-Related Timing

| Field | Table | Description |
|-------|-------|-------------|
| FKDAT | VBRK | Billing date |
| BUDAT | VBRK | Posting date (to FI) |

### Status Fields for Flow Analysis

| Field | Table | Description |
|-------|-------|-------------|
| GBSTK | VBAK/LIKP | Overall status |
| LFSTK | VBAK | Delivery status |
| FKSTK | VBAK | Billing status |
| WBSTK | LIKP | Goods movement status |
| KOSTK | LIKP | Picking status |

## Tips for Adapter Implementation

1. **Number Formatting**: SAP document numbers are typically 10 characters with leading zeros. Always pad: `'12345'.padStart(10, '0')` = `'0000012345'`

2. **Item Numbers**: 6 characters with leading zeros: `'10'.padStart(6, '0')` = `'000010'`

3. **Date Fields**: SAP dates are YYYYMMDD strings or DATS type. Convert carefully.

4. **Time Fields**: HHMMSS strings. Combine with date for timestamps.

5. **Amounts**: May have currency-specific decimal places. Check TCURX table.

6. **Text Access**: Never try to read STXL directly. Use READ_TEXT or CDS views.

7. **Deleted Records**: Check deletion flags (varies by table). Some tables soft-delete.

8. **Archiving**: Old documents may be archived. Consider archive access if needed.

## Version Differences

### ECC 6.0 vs S/4HANA

| Aspect | ECC 6.0 | S/4HANA |
|--------|---------|---------|
| Table structure | Cluster tables (KONV, STXL) | Declustered (PRCD_ELEMENTS) |
| Text access | READ_TEXT FM | CDS views available |
| Best API | RFC_READ_TABLE + BAPIs | OData / CDS |
| Field lengths | Some 10-char limits | Extended (CHAR40) |
| Material number | MATNR 18 chars | MATNR 40 chars |

### Custom Tables

Many SAP implementations add custom tables (Z*, Y*). Check with your basis team for:
- ZVBAK_EXT - Order header extensions
- ZLIPS_BATCH - Delivery batch info
- Custom text tables

These are invisible to this documentation but may be critical for your analysis.
