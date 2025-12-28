# SAP Workflow Mining Pattern Report

**Generated**: 2025-12-28T12:59:16.507553Z
**Version**: 0.1.0
**Random Seed**: 42

## Summary

- **Total Patterns**: 6
- **Notable Patterns**: 0
- **Total Documents**: 3018
- **Average Confidence**: 40%

## Other Patterns

## Customer Request / Request / Customer

**ID**: PAT-83AF9F88
**Confidence**: 40%
**Sample Size**: 412 documents

### Description
Documents in this cluster frequently contain "customer request", "request", "customer". No statistically significant timing differences from baseline. Based on analysis of 412 documents.

### Characteristic Phrases
- customer request
- request
- customer
- expedite customer request
- expedite customer

### Caveats
- Observational analysis only; correlation does not imply causation.
- Patterns based on text similarity; may not capture all relevant factors.
- No statistically significant effects detected.

### Evidence Summary

- **Documents**: 412
- **Source Files**: 6

**Row Counts:**
- total_documents: 10,000
- cluster_documents: 412

**Reproducibility:**
- Seed: 42
- Algorithm: kmeans
- Embedding: tfidf
- Timestamp: 2025-12-28T12:59:16.445872Z

---

## Hold / Credit / Credit Hold

**ID**: PAT-EBE92C4E
**Confidence**: 40%
**Sample Size**: 211 documents

### Description
Documents in this cluster frequently contain "hold", "credit", "credit hold". No statistically significant timing differences from baseline. Based on analysis of 211 documents.

### Characteristic Phrases
- hold
- credit
- credit hold
- hold expedite
- hold credit

### Caveats
- Observational analysis only; correlation does not imply causation.
- Patterns based on text similarity; may not capture all relevant factors.
- No statistically significant effects detected.

### Evidence Summary

- **Documents**: 211
- **Source Files**: 6

**Row Counts:**
- total_documents: 10,000
- cluster_documents: 211

**Reproducibility:**
- Seed: 42
- Algorithm: kmeans
- Embedding: tfidf
- Timestamp: 2025-12-28T12:59:16.452729Z

---

## Needs Friday / Friday / Needs

**ID**: PAT-60E4E555
**Confidence**: 40%
**Sample Size**: 370 documents

### Description
Documents in this cluster frequently contain "needs friday", "friday", "needs". No statistically significant timing differences from baseline. Based on analysis of 370 documents.

### Characteristic Phrases
- needs friday
- friday
- needs
- customer needs friday
- customer needs

### Caveats
- Observational analysis only; correlation does not imply causation.
- Patterns based on text similarity; may not capture all relevant factors.
- No statistically significant effects detected.

### Evidence Summary

- **Documents**: 370
- **Source Files**: 6

**Row Counts:**
- total_documents: 10,000
- cluster_documents: 370

**Reproducibility:**
- Seed: 42
- Algorithm: kmeans
- Embedding: tfidf
- Timestamp: 2025-12-28T12:59:16.459473Z

---

## Ref / Partial / Ship

**ID**: PAT-67AFBFAC
**Confidence**: 40%
**Sample Size**: 1302 documents

### Description
Documents in this cluster frequently contain "ref", "partial", "ship". No statistically significant timing differences from baseline. Based on analysis of 1302 documents.

### Characteristic Phrases
- ref
- partial
- ship
- stock
- order

### Caveats
- Observational analysis only; correlation does not imply causation.
- Patterns based on text similarity; may not capture all relevant factors.
- No statistically significant effects detected.

### Evidence Summary

- **Documents**: 1302
- **Source Files**: 6

**Row Counts:**
- total_documents: 10,000
- cluster_documents: 1,302

**Reproducibility:**
- Seed: 42
- Algorithm: kmeans
- Embedding: tfidf
- Timestamp: 2025-12-28T12:59:16.492388Z

---

## Expedite / Expedite Expedite / Expedite Ref

**ID**: PAT-61AF9396
**Confidence**: 40%
**Sample Size**: 354 documents

### Description
Documents in this cluster frequently contain "expedite", "expedite expedite", "expedite ref". No statistically significant timing differences from baseline. Based on analysis of 354 documents.

### Characteristic Phrases
- expedite
- expedite expedite
- expedite ref
- rush expedite
- ref

### Caveats
- Observational analysis only; correlation does not imply causation.
- Patterns based on text similarity; may not capture all relevant factors.
- No statistically significant effects detected.

### Evidence Summary

- **Documents**: 354
- **Source Files**: 6

**Row Counts:**
- total_documents: 10,000
- cluster_documents: 354

**Reproducibility:**
- Seed: 42
- Algorithm: kmeans
- Embedding: tfidf
- Timestamp: 2025-12-28T12:59:16.498804Z

---

## Mgmt / Mgmt Approved / Approved

**ID**: PAT-2688648C
**Confidence**: 40%
**Sample Size**: 369 documents

### Description
Documents in this cluster frequently contain "mgmt", "mgmt approved", "approved". No statistically significant timing differences from baseline. Based on analysis of 369 documents.

### Characteristic Phrases
- mgmt
- mgmt approved
- approved
- expedite mgmt
- expedite mgmt approved

### Caveats
- Observational analysis only; correlation does not imply causation.
- Patterns based on text similarity; may not capture all relevant factors.
- No statistically significant effects detected.

### Evidence Summary

- **Documents**: 369
- **Source Files**: 6

**Row Counts:**
- total_documents: 10,000
- cluster_documents: 369

**Reproducibility:**
- Seed: 42
- Algorithm: kmeans
- Embedding: tfidf
- Timestamp: 2025-12-28T12:59:16.504367Z

---

## Appendix: Reproducibility

To reproduce this analysis:

```bash
python -m pattern_engine run --seed 42 \
    --input-dir ./data --output-dir ./output
```

### Parameters Used

- Clustering Algorithm: kmeans
- Embedding Model: tfidf
- Number of Clusters: 6
- Minimum Cluster Size: 5
- Delay Threshold: 7 days