# Walkthrough Memorandum — Order to Cash

**Document ID:** FB-SOX-WT-OTC-2025  
**Date of walkthrough:** 11 March 2025  
**Transaction traced:** Sales order SO-450219 → Delivery DL-88211 → Invoice INV-99102 → Cash receipt CR-33018

## Steps observed

1. Sales entered order for Contoso OEM; credit check passed (limit USD 500,000; exposure USD 312,000).
2. Warehouse picked and PGI posted 11 Mar 14:22; bill of lading signed.
3. Invoice auto-generated at contract price; OTC-15 job showed no price exception.
4. Customer paid via lockbox 28 Mar; applied by AR clerk same day.

## Controls confirmed designed effectively

OTC-12 (credit), OTC-15 (price), OTC-18 (cut-off design via period-end checklist discussion), OTC-22 (cash application).

## Points of focus for OE testing

- Credit overrides (OTC-12a) — population expected small; test full population YTD.
- Period-end cut-off evidence completeness in December.
