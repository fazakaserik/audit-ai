# Backup Restore Test — Q1 FY2025

**Document ID:** AW-RESTORE-2025-Q1  
**Date executed:** 28 March 2025  
**System:** E-commerce production database (restore to isolated DR subnet)

## Procedure

1. Selected daily full backup from 27 March 2025 02:00 PT plus log chain.
2. Restored to `aw-ecom-dr-test` instance.
3. Validated row counts on orders / customers tables vs prod snapshot checksum job.
4. Application smoke test against DR instance (read-only storefront).

## Results

| Check | Result |
|-------|--------|
| Restore completed | Yes — 1h 52m |
| Checksums matched | Yes |
| Smoke test | Pass |
| Within RTO 4h | Yes |

Signed by IT Operations Lead and observed by IT Security representative.
