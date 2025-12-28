# SAP Adapter Implementation Guide

> **Critical**: This tool should ONLY connect to SAP with read-only access. If you find yourself needing write access, stop and reconsider.

This guide covers implementing adapters to connect the MCP server to real SAP systems (ECC 6.0+ or S/4HANA). The synthetic adapter serves as the reference implementation.

## Prerequisites

### System Access Requirements

1. **SAP System**: ECC 6.0 EhP5+ or S/4HANA 1709+
2. **Network Access**: Connectivity from MCP server to SAP (RFC or HTTP/S)
3. **SAP User**: Technical user with limited, read-only authorizations
4. **Development System First**: Never start with production

### Required Authorizations

The SAP user needs authorizations for specific objects. Request the minimum needed:

**For RFC Access (ECC)**:
| Authorization Object | Field | Value | Purpose |
|---------------------|-------|-------|---------|
| S_RFC | RFC_TYPE | FUGR | Function group access |
| S_RFC | RFC_NAME | SDIF, CKML_* | Specific function groups |
| S_RFC | ACTVT | 16 | Execute only |
| S_TABU_DIS | DICBERCLS | &NC& | Table access (limited) |
| S_TABU_DIS | ACTVT | 03 | Display only |

**Table-specific (S_TABU_LIN or S_TABU_NAM)**:
| Tables | Purpose |
|--------|---------|
| VBAK, VBAP | Sales orders |
| LIKP, LIPS | Deliveries |
| VBRK, VBRP | Invoices |
| VBFA | Document flow |
| VBPA | Partners |
| STXH | Text headers (via READ_TEXT) |

**For OData Access (S/4HANA)**:
| Authorization Object | Field | Value |
|---------------------|-------|-------|
| S_SERVICE | SRV_NAME | API_SALES_ORDER*, etc. |
| S_SERVICE | SRV_TYPE | HT | HTTP service |

### What NOT to Authorize

**Never grant these**:
- S_DEVELOP (ABAP development)
- S_ADMI_FCD (system administration)
- S_BTCH_ADM (batch administration)
- S_RFC with RFC_NAME = * (all RFCs)
- Any update activity (ACTVT = 02)
- FI tables (BKPF, BSEG, etc.)
- HR tables (PA0001, etc.)
- User tables (USR*)
- Password tables

---

## Architecture: Adapter Interface

Each adapter must implement the interface expected by the MCP tools. The synthetic adapter (`adapters/synthetic/`) is the reference.

```typescript
// Adapter interface (conceptual - actual implementation may vary)
interface SAPAdapter {
  // Search for documents by text pattern
  searchDocText(pattern: string, options: SearchOptions): Promise<SearchResult[]>;

  // Get text for a specific document
  getDocText(docNumber: string, docType: DocType): Promise<DocText>;

  // Get document flow (order -> delivery -> invoice chain)
  getDocFlow(docNumber: string): Promise<DocFlow>;

  // Get sales document header
  getSalesDocHeader(docNumber: string): Promise<SalesHeader>;

  // Get sales document items
  getSalesDocItems(docNumber: string): Promise<SalesItem[]>;

  // Get delivery timing
  getDeliveryTiming(docNumber: string): Promise<DeliveryTiming>;

  // Get invoice timing
  getInvoiceTiming(docNumber: string): Promise<InvoiceTiming>;

  // Get master data stub (safe fields only)
  getMasterStub(id: string, type: MasterType): Promise<MasterStub>;
}
```

---

## ECC RFC Adapter Implementation

### Connection Setup

Use a Node.js RFC connector library. Options:
- `node-rfc` (SAP's official connector)
- Custom HTTP wrapper around SAP Gateway

**Example connection configuration** (do NOT commit credentials):
```typescript
// config loaded from environment variables
const rfcConfig = {
  ashost: process.env.SAP_ASHOST,       // Application server host
  sysnr: process.env.SAP_SYSNR,         // System number (00, 01, etc.)
  client: process.env.SAP_CLIENT,       // Client (100, 200, etc.)
  user: process.env.SAP_USER,
  passwd: process.env.SAP_PASSWD,       // Or use SNC
  lang: 'EN',
  pool: { min: 1, max: 5 }
};
```

### RFC_READ_TABLE: The Workhorse

Most table reads use RFC_READ_TABLE (or BBP_RFC_READ_TABLE in newer systems).

**Parameters**:
| Parameter | Description |
|-----------|-------------|
| QUERY_TABLE | Table name (e.g., 'VBAK') |
| DELIMITER | Field separator ('|' recommended) |
| NO_DATA | 'X' to return structure only |
| ROWSKIPS | Rows to skip (paging) |
| ROWCOUNT | Max rows to return |
| OPTIONS | WHERE clause conditions |
| FIELDS | Fields to return |

**Example: Read Sales Orders**:
```typescript
async function readSalesOrders(fromDate: string, maxRows: number = 200): Promise<any[]> {
  const result = await client.call('RFC_READ_TABLE', {
    QUERY_TABLE: 'VBAK',
    DELIMITER: '|',
    ROWCOUNT: maxRows,  // ENFORCE LIMIT
    FIELDS: [
      { FIELDNAME: 'VBELN' },
      { FIELDNAME: 'ERDAT' },
      { FIELDNAME: 'AUART' },
      { FIELDNAME: 'VKORG' },
      { FIELDNAME: 'KUNNR' },
      { FIELDNAME: 'NETWR' },
    ],
    OPTIONS: [
      { TEXT: `ERDAT >= '${fromDate}'` },  // Sanitize this!
      { TEXT: `AND AUART IN ('OR','ZOR','RE')` },
    ]
  });

  return parseDelimitedData(result.DATA, result.FIELDS);
}
```

**Security Warning**: The OPTIONS parameter accepts SQL-like conditions. ALWAYS sanitize inputs to prevent injection:

```typescript
// BAD - SQL injection vulnerable
const options = [{ TEXT: `VBELN = '${userInput}'` }];

// GOOD - validate format
function sanitizeVbeln(input: string): string {
  const cleaned = input.replace(/[^0-9]/g, '').padStart(10, '0');
  if (cleaned.length !== 10) {
    throw new Error('Invalid document number');
  }
  return cleaned;
}
const options = [{ TEXT: `VBELN = '${sanitizeVbeln(userInput)}'` }];
```

### Reading Text: READ_TEXT Function

STXL is clustered and cannot be read with RFC_READ_TABLE. Use READ_TEXT:

```typescript
async function readDocumentText(
  docNumber: string,
  textObject: string,  // 'VBBK' for order header
  textId: string       // '0001' for header text
): Promise<string[]> {
  const result = await client.call('READ_TEXT', {
    ID: textId,
    LANGUAGE: 'E',
    NAME: sanitizeVbeln(docNumber),
    OBJECT: textObject
  });

  // LINES is a table of TLINE structures
  return result.LINES.map((line: any) => line.TDLINE);
}
```

**Common TEXT_OBJECT/TEXT_ID combinations for SD**:
| Object | ID | Description |
|--------|-----|-------------|
| VBBK | 0001 | Order header text |
| VBBK | 0002 | Order header internal note |
| VBBP | 0001 | Order item text |
| VBBK | Z001 | Custom header text (varies) |

### Recommended RFCs/BAPIs by Tool

| Tool | Recommended RFC/BAPI | Alternative |
|------|---------------------|-------------|
| search_doc_text | READ_TEXT + custom loop | Z_SEARCH_DOC_TEXT (if available) |
| get_doc_text | READ_TEXT | BAPI_DOCUMENT_GETDETAIL2 |
| get_doc_flow | RFC_READ_TABLE on VBFA | BAPI_SALESORDER_GETLIST |
| get_sales_doc_header | RFC_READ_TABLE on VBAK | BAPI_SALESORDER_GETLIST |
| get_sales_doc_items | RFC_READ_TABLE on VBAP | SD_SALESDOCUMENT_READ |
| get_delivery_timing | RFC_READ_TABLE on LIKP | BAPI_DELIVERY_GETLIST |
| get_invoice_timing | RFC_READ_TABLE on VBRK | BAPI_BILLINGDOC_GETLIST |
| get_master_stub | RFC_READ_TABLE on KNA1/MARA | BAPI_CUSTOMER_GETDETAIL |

### Row Limit Enforcement

**Critical**: Always enforce row limits at the adapter level:

```typescript
const MAX_ROWS = 200;

async function getDeliveries(orderNumber: string): Promise<Delivery[]> {
  const result = await client.call('RFC_READ_TABLE', {
    QUERY_TABLE: 'VBFA',
    ROWCOUNT: MAX_ROWS,  // ALWAYS SET THIS
    // ... other params
  });

  // Double-check and flag truncation
  const truncated = result.DATA.length >= MAX_ROWS;

  return {
    data: parseResult(result),
    truncated,
    rowCount: result.DATA.length,
    maxRows: MAX_ROWS
  };
}
```

---

## S/4HANA OData Adapter Implementation

### Connection Setup

S/4HANA exposes OData services. Use standard HTTP client with OAuth2 or Basic Auth.

```typescript
// config loaded from environment
const odataConfig = {
  baseUrl: process.env.S4_ODATA_URL,  // e.g., https://s4hana.company.com:443/sap/opu/odata/sap/
  auth: {
    type: 'oauth2',  // or 'basic'
    clientId: process.env.S4_CLIENT_ID,
    clientSecret: process.env.S4_CLIENT_SECRET,
    tokenUrl: process.env.S4_TOKEN_URL
  }
};
```

### Relevant OData Services

| Service | Purpose | Key Entities |
|---------|---------|--------------|
| API_SALES_ORDER_SRV | Sales orders | A_SalesOrder, A_SalesOrderItem |
| API_OUTBOUND_DELIVERY_SRV | Deliveries | A_OutbDeliveryHeader, A_OutbDeliveryItem |
| API_BILLING_DOCUMENT_SRV | Invoices | A_BillingDocument, A_BillingDocumentItem |
| API_BUSINESS_PARTNER | Customers | A_BusinessPartner |
| API_PRODUCT_SRV | Materials | A_Product |

### Example: Get Sales Order

```typescript
async function getSalesOrder(orderNumber: string): Promise<SalesOrder> {
  const cleanNumber = sanitizeVbeln(orderNumber);

  const response = await fetch(
    `${odataConfig.baseUrl}API_SALES_ORDER_SRV/A_SalesOrder('${cleanNumber}')?$expand=to_Item`,
    {
      headers: {
        'Authorization': `Bearer ${await getToken()}`,
        'Accept': 'application/json'
      }
    }
  );

  if (!response.ok) {
    throw new Error(`SAP returned ${response.status}`);
  }

  return transformODataResponse(await response.json());
}
```

### Enforcing Limits with OData

Use $top and $skip for paging:

```typescript
async function searchOrders(filter: string, maxRows: number = 200): Promise<SearchResult> {
  const url = new URL(`${odataConfig.baseUrl}API_SALES_ORDER_SRV/A_SalesOrder`);
  url.searchParams.set('$filter', filter);
  url.searchParams.set('$top', String(Math.min(maxRows, 200)));  // Cap at 200
  url.searchParams.set('$select', 'SalesOrder,CreationDate,SalesOrderType');
  url.searchParams.set('$count', 'true');

  const response = await fetch(url.toString(), { /* auth headers */ });
  const data = await response.json();

  return {
    results: data.value,
    totalCount: data['@odata.count'],
    truncated: data['@odata.count'] > maxRows
  };
}
```

### Text Access in S/4HANA

S/4HANA provides text via CDS views or navigation properties:

```typescript
// Using navigation property
const url = `${baseUrl}API_SALES_ORDER_SRV/A_SalesOrder('${orderNumber}')/to_Text`;

// Returns A_SalesOrderText entities with:
// - Language
// - LongTextID
// - LongText (actual content)
```

---

## Security Requirements Checklist

### Before Going Live

- [ ] SAP user is read-only (no update authorizations)
- [ ] Credentials stored in environment variables or secret manager
- [ ] Network connection uses TLS 1.2+
- [ ] Row limits enforced in adapter code
- [ ] Input sanitization implemented for all parameters
- [ ] Audit logging enabled
- [ ] Error messages do not leak SAP internals
- [ ] No FI tables accessible
- [ ] No HR tables accessible
- [ ] No user management tables accessible

### Network Segmentation Recommendations

```
    Recommended Network Architecture
    ================================

    +-------------------+         +-------------------+
    |                   |         |                   |
    |  Public Network   |         |   SAP Network     |
    |  (Internet)       |         |   (Internal)      |
    |                   |         |                   |
    +--------+----------+         +---------+---------+
             |                              |
             | HTTPS (443)                  | RFC (3300) or HTTPS (443)
             |                              |
    +--------+----------+         +---------+---------+
    |                   |         |                   |
    |  DMZ / Viewer     |<------->|   MCP Server      |
    |  (Read-only UI)   |   API   |   (On-Premise)    |
    |                   |         |                   |
    +-------------------+         +---------+---------+
                                            |
                                            | RFC/OData (Internal only)
                                            |
                                  +---------+---------+
                                  |                   |
                                  |   SAP System      |
                                  |   (ECC/S4)        |
                                  |                   |
                                  +-------------------+

    Key Points:
    - MCP Server should be inside the firewall with SAP
    - Only expose API endpoints to Viewer, not SAP directly
    - Consider VPN for remote MCP server access
    - SAP RFC ports (33XX) should never face public internet
```

---

## Testing Approach

### Phase 1: Synthetic Validation

1. Run full analysis against synthetic data
2. Verify all planted patterns are discovered
3. Verify no false patterns are reported
4. Baseline performance metrics

### Phase 2: Development System

1. Connect adapter to SAP development system
2. Run same queries against dev SAP
3. Compare structure of responses to synthetic
4. Verify row limits are enforced
5. Check SAP performance impact (ST05, SM50)

### Phase 3: Schema Validation

```typescript
// Use Zod or similar for runtime validation
const SalesOrderSchema = z.object({
  vbeln: z.string().length(10),
  erdat: z.string().regex(/^\d{8}$/),  // YYYYMMDD
  auart: z.string().max(4),
  // ... other fields
});

function validateAdapterResponse(data: unknown): SalesOrder {
  return SalesOrderSchema.parse(data);  // Throws on invalid
}
```

### Phase 4: Redaction Validation

1. Query documents known to contain PII in dev
2. Run through redaction layer
3. Verify PII is removed in output
4. Grep output for email/phone patterns as safety check

### Phase 5: Performance Testing

```typescript
// Measure and log response times
async function instrumentedQuery<T>(
  name: string,
  queryFn: () => Promise<T>
): Promise<T> {
  const start = Date.now();
  try {
    const result = await queryFn();
    const duration = Date.now() - start;
    logger.info({ query: name, duration, status: 'success' });
    return result;
  } catch (error) {
    const duration = Date.now() - start;
    logger.error({ query: name, duration, status: 'error', error });
    throw error;
  }
}
```

### Phase 6: Integration Test Suite

```typescript
describe('ECC RFC Adapter', () => {
  it('should enforce row limits', async () => {
    const result = await adapter.getDocFlow('*');  // Broad query
    expect(result.data.length).toBeLessThanOrEqual(200);
    expect(result.truncated).toBeDefined();
  });

  it('should sanitize document numbers', async () => {
    await expect(
      adapter.getSalesDocHeader("'; DROP TABLE VBAK; --")
    ).rejects.toThrow('Invalid document number');
  });

  it('should not expose FI data', async () => {
    await expect(
      adapter.rawTableRead('BKPF')  // This method should not exist
    ).rejects.toThrow();
  });
});
```

---

## Production Deployment Checklist

**Do NOT deploy to production until**:

- [ ] All Phase 1-6 tests pass
- [ ] Security review completed
- [ ] SAP Basis team approved authorizations
- [ ] Network team approved connectivity
- [ ] Legal/compliance reviewed data handling
- [ ] Incident response plan exists
- [ ] Rollback procedure documented
- [ ] Performance baseline established on dev
- [ ] Monitoring/alerting configured
- [ ] Documentation updated for ops team

**First production run**:
- [ ] Start with small date range
- [ ] Run during off-peak hours
- [ ] Monitor SAP performance continuously
- [ ] Review audit logs immediately after
- [ ] Verify no unexpected data in output

---

## Troubleshooting

### Common RFC Errors

| Error | Cause | Fix |
|-------|-------|-----|
| RFC_COMMUNICATION_FAILURE | Network issue | Check firewall, ping host |
| RFC_LOGON_FAILURE | Bad credentials | Verify user/password, check SU01 |
| NO_AUTHORITY | Missing authorization | Add auth object in PFCG |
| TABLE_NOT_AVAILABLE | Table does not exist | Check spelling, system version |
| DATA_BUFFER_EXCEEDED | Too much data | Reduce ROWCOUNT, add filters |

### Common OData Errors

| HTTP Status | Cause | Fix |
|-------------|-------|-----|
| 401 | Authentication failed | Check token, credentials |
| 403 | Authorization denied | Check ICF service activation |
| 404 | Service not found | Verify service path, activation |
| 500 | SAP internal error | Check ST22, SM21 for dumps |

### SAP Monitoring

Check these transactions during testing:
- SM50: Work process monitor (look for long-running RFC)
- ST05: SQL trace (check query performance)
- SM21: System log (errors, security events)
- ST22: ABAP dumps
- SMGW: Gateway monitor (RFC connections)

---

## What NOT to Expose

Even if technically possible, do NOT implement access to:

### Financial Data (FI)

| Table/Area | Reason |
|------------|--------|
| BKPF, BSEG | Financial documents - highly sensitive |
| BSID, BSAD | Customer open/cleared items - financial exposure |
| BSIK, BSAK | Vendor open/cleared items - financial exposure |
| ACDOCA | Universal journal - complete financial picture |
| FAGL* | New GL tables - financial data |

**Why**: Financial data has audit, compliance, and competitive sensitivity. Even read access could enable fraud detection bypass or competitive intelligence.

### HR/Payroll Data

| Table/Area | Reason |
|------------|--------|
| PA0001-PA9999 | HR master data infotypes - PII, employment law |
| PCL1, PCL2 | Payroll clusters - compensation data |
| HRP* | Organizational management - hierarchy data |

**Why**: Employment data has extreme legal protection (GDPR, CCPA, employment law). No legitimate analysis use case.

### Custom Z-Tables (Without Review)

| Table/Area | Reason |
|------------|--------|
| Z* tables | Unknown sensitivity - may contain anything |
| Y* tables | Customer-specific - undocumented |

**Why**: Custom tables may contain PII, financial data, or other sensitive information. Require explicit review before adding.

### Pricing Conditions Detail

| Table/Area | Reason |
|------------|--------|
| KONV | Pricing conditions - competitive intelligence |
| KONP | Condition item data - margin exposure |
| A* condition tables | Condition records - pricing strategy |

**Why**: Pricing data reveals margins, discounts, and customer-specific terms. Competitive risk.

### System/Security Tables

| Table/Area | Reason |
|------------|--------|
| USR01, USR02 | User data - security risk |
| AGR_* | Authorization data - security bypass potential |
| RFCDES | RFC destinations - credentials exposure |
| T000 | Client table - system architecture |
| E070, E071 | Transport logs - change management bypass |
| CDHDR, CDPOS | Change documents - audit trail exposure |

**Why**: System tables enable reconnaissance for attacks.

### Summary Rule

If you find yourself wanting access to these tables, **stop and ask why**. The tool's purpose is text pattern analysis in SD documents, not general SAP data access. If a use case requires sensitive data, it requires a separate security review and different architecture.
