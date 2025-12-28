# SAP Latent Workflow Mining Tool

> **Read-only. Facts-first. Prove/disprove.**

## Why This Exists

ERP systems record **transactions**; humans record **intent** in text fields.

This tool extracts unstructured text from SAP documents (orders, deliveries, invoices), anchors it to structured context (timing, status, org data), and finds repeatable patterns that correlate with business outcomes.

**This is not an SAP replacement.** It's a read-only lens on how work actually gets done.

**If it finds nothing in your system, that is a valid outcome.**

## What It Does

1. **Extracts** text fields from SD/MM documents (header notes, item notes, rejection reasons)
2. **Anchors** text to document flow chains (order → delivery → invoice) with timing
3. **Clusters** text into themes using embeddings or TF-IDF
4. **Correlates** clusters to outcomes (delivery delays, invoice lags, partial shipments)
5. **Outputs** "pattern cards" with explicit evidence and caveats

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI / Viewer                             │
├─────────────────────────────────────────────────────────────────┤
│                      Pattern Engine (Python)                     │
│   ingest → normalize → cluster → correlate → report              │
├─────────────────────────────────────────────────────────────────┤
│                      MCP Server (TypeScript)                     │
│   8 tools: search_doc_text, get_doc_flow, get_delivery_timing... │
├─────────────────────────────────────────────────────────────────┤
│                         Data Adapters                            │
│   synthetic (default) │ ecc_rfc (stub) │ s4_odata (stub)         │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (for local development)
- Python 3.10+ (for local development)

### One-Command Run

```bash
# Generate synthetic data, start MCP server, run pattern engine, output reports
docker-compose up --build

# Or use the CLI directly:
./cli.sh run-all --output ./output
```

### Local Development

```bash
# 1. Generate synthetic data
cd synthetic-data
pip install -r requirements.txt
python src/generate_sd.py --count 10000 --output sample_output/

# 2. Start MCP server
cd ../mcp-server
npm install
npm run dev

# 3. Run pattern engine
cd ../pattern-engine
pip install -r requirements.txt
python -m src.main --input ../synthetic-data/sample_output --output ../output

# 4. View results
ls -la ../output/
cat ../output/pattern_cards.json
```

## MCP Tools (v0)

| Tool | Purpose | Returns |
|------|---------|---------|
| `search_doc_text` | Find documents by text pattern | doc_type, doc_key, snippet, match_score, dates |
| `get_doc_text` | Get all text fields for a document | header_texts[], item_texts[] |
| `get_doc_flow` | Get order→delivery→invoice chain | chain objects with keys, statuses, dates |
| `get_sales_doc_header` | Get order header details | sales_org, sold_to, doc_date, etc. |
| `get_sales_doc_items` | Get order line items | posnr, matnr, qty, net_value, etc. |
| `get_delivery_timing` | Get requested vs actual delivery | timestamps at doc/line level |
| `get_invoice_timing` | Get invoice creation/posting dates | invoice keys and dates |
| `get_master_stub` | Get safe master data attributes | industry, region, category (hashed IDs) |

## Safety & Privacy

- **Read-only**: No updates, no arbitrary SQL, no table scanning
- **Redaction**: Emails, phone numbers, names, addresses masked by default
- **Row limits**: All queries capped (default 200, max 1000)
- **Audit logs**: Every tool call logged with parameters and row counts
- **Evidence ledger**: Every pattern card links to supporting doc_keys

## Pattern Cards

Each pattern card includes:

```json
{
  "id": "pattern_001",
  "title": "Credit Hold Escalation",
  "description": "Orders with 'CREDIT HOLD' in notes have 3.2x longer order-to-delivery cycle",
  "top_phrases": ["credit hold", "hold for credit", "credit block"],
  "sample_snippets": ["[REDACTED] - credit hold pending approval", "..."],
  "occurrence": {
    "count": 234,
    "by_sales_org": {"1000": 150, "2000": 84},
    "by_customer_industry": {"RETAIL": 180, "INDUSTRIAL": 54}
  },
  "effect": {
    "metric": "order_to_delivery_days",
    "baseline": 5.2,
    "pattern_value": 16.8,
    "lift": 3.23,
    "p_value": 0.001
  },
  "confidence": "HIGH",
  "caveats": [
    "Correlation only - does not imply causation",
    "Based on 234 observations (4.7% of dataset)",
    "Text matching is substring-based, may include false positives"
  ],
  "evidence": {
    "doc_keys": ["0000012345", "0000012346", "..."],
    "fields_used": ["VBAK-BSTKD_E", "VBKD-BSTDK"],
    "sample_size": 234,
    "total_population": 5000
  }
}
```

## Prove Me Wrong

This tool is designed to be **falsifiable**:

1. Run it against synthetic data to understand the patterns it can find
2. Run it against your real SAP system (via RFC/OData adapters)
3. Compare results - if patterns don't replicate, that's useful information
4. Drill into evidence to verify individual cases

## Limitations

- **Correlation ≠ Causation**: Patterns indicate association, not cause
- **Text quality varies**: Garbage in, garbage out
- **Sampling bias**: Limited to documents returned by tool queries
- **Language**: v0 optimized for English text fields
- **ECC/S4 differences**: Document structures may vary by configuration

See [docs/limitations.md](docs/limitations.md) for full discussion.

## Adapter Guide

To run against your own SAP system:

1. Implement the adapter interface for your connection method:
   - `adapters/ecc_rfc/` - RFC calls to ECC
   - `adapters/s4_odata/` - OData API calls to S/4HANA

2. Map your table structures to the expected schemas (see [docs/join_maps.md](docs/join_maps.md))

3. Configure connection in `config.yaml`

4. Run with `--adapter ecc_rfc` or `--adapter s4_odata`

See [docs/adapter_guide.md](docs/adapter_guide.md) for detailed instructions.

## License

MIT License - See [LICENSE](LICENSE)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## Disclaimer

This tool is provided as-is for research and analysis purposes. It does not modify SAP data. Users are responsible for ensuring compliance with their organization's data access policies.
