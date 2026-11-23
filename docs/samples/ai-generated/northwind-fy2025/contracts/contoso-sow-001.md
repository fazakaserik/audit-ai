# Statement of Work No. 001 — Managed Cloud Support

**Parent agreement:** Master Services Agreement NW-CTR-2025-001  
**SOW ID:** NW-SOW-2025-001  
**Customer:** Northwind Traders, Inc.  
**Supplier:** Contoso Ltd  
**SOW effective date:** 1 January 2025  
**SOW end date:** 31 December 2025

## 1. Services

Contoso provides 24×5 managed support for Northwind's Azure landing zone, including:

1. Monitoring of production subscriptions `nw-prod-eastus` and `nw-prod-westus`.
2. Patch orchestration for Windows and Linux jump hosts (monthly cadence).
3. Incident triage for Sev-1 and Sev-2 tickets with response SLAs in Section 3.
4. Quarterly architecture review with Northwind IT (max 16 hours per quarter).

Out of scope: application code changes, database schema redesign, and on-premises warehouse WMS customisation.

## 2. Fees

| Component | Amount | Billing |
|-----------|--------|---------|
| Base managed support | USD 18,500 / month | Monthly in arrears |
| Sev-1 after-hours surcharge | USD 250 / hour | As incurred |
| Quarterly architecture review | Included in base | N/A |

Annual contract value at base rates: **USD 222,000**.

## 3. Service levels

| Severity | Definition | Response | Restore target |
|----------|------------|----------|----------------|
| Sev-1 | Production outage or data loss risk | 30 minutes | 4 hours |
| Sev-2 | Major feature degraded | 2 hours | 1 business day |
| Sev-3 | Minor defect / request | 1 business day | Agreed in ticket |

Credits: if Contoso fails Sev-1 restore target more than twice in a calendar quarter, Customer receives a **10% credit** on that quarter's base fees.

## 4. Named contacts

| Party | Primary | Backup |
|-------|---------|--------|
| Contoso CSM | Avery Kim | Sam Ortiz |
| Northwind IT | Marcus Chen | Leah Brooks |

## 5. Acceptance

Services are deemed accepted month-to-month unless Customer notifies Contoso of material non-performance within ten (10) business days after month-end.
