# ITGC — Change Management Policy & Control Description

**Document ID:** FB-ITGC-CHG-2025  
**System:** FabrikamERP  
**Owner:** IT Director

## Policy requirements

1. All production changes require a ticket in the Change Management System (CMS).
2. Segregation: developer cannot approve own change for production.
3. **CAB approval is required before production deployment for 100% of normal and emergency changes** (emergency changes require retrospective CAB within 2 business days).
4. Test evidence attached for normal changes; back-out plan documented.
5. Post-implementation review for Sev-1 related changes within 5 business days.

## Key controls

| Control ID | Description |
|------------|-------------|
| ITGC-CH-01 | CMS enforces peer approval before prod deploy state |
| ITGC-CH-02 | Quarterly review of emergency changes for retrospective CAB |
| ITGC-CH-03 | Access to prod deploy role limited to release engineers; quarterly UAR |

## Metrics (Q1–Q3 FY2025)

| Metric | Result |
|--------|--------|
| Normal changes with prior CAB approval | 100% (214 / 214) |
| Emergency changes with retrospective CAB ≤ 2 days | 97% (32 / 33) |
| SOD violations (dev approving self) | 0 |

One emergency change (CHG-2025-0881) missed retrospective CAB by one day — logged as DEF-2025-03.
