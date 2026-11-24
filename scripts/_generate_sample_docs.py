"""One-shot generator for AI sample engagement trees. Not part of the runtime path."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "samples" / "ai-generated"


def write(rel: str, content: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT.parent.parent.parent)}")


# ---------------------------------------------------------------------------
# northwind-fy2025 — financial statement / operational audit
# ---------------------------------------------------------------------------

write(
    "northwind-fy2025/README.md",
    """
# Northwind FY2025 (AI-generated sample)

Fictional external audit working papers for **Northwind Traders** (wholesale distribution).
Period: FY2025 (1 January – 31 December 2025). Not real client data.

Folders: `contracts/`, `finance/`, `policies/`, `hr/`, `inventory/`, `minutes/`, `workpapers/`.

## Answerable examples

1. What are Contoso payment terms? → `contracts/contoso-msa.md` (Net-30)
2. What was Q1 FY2025 total revenue? → `finance/q1-summary.md` (USD 5,030,000)
3. What is the domestic meal limit? → `policies/expense-policy.md` (USD 75/person/day)
4. When must terminated access be revoked? → `policies/access-control.md` (within 24 hours)
5. What is Warehouse A annual base rent? → `finance/lease-warehouse-a.txt` (USD 480,000)
6. What is the Contoso MSA liability cap? → `contracts/contoso-msa.md` (fees paid in prior 12 months)
7. What was planning materiality for FY2025? → `workpapers/materiality-memo.md` (USD 250,000)
8. How many SKUs were counted in the Q1 cycle count? → `inventory/cycle-count-q1.md` (120)
9. What is the Fabrikam payment term? → `contracts/fabrikam-vendor-agreement.md` (Net-45)
10. Who chairs the Audit Committee? → `minutes/audit-committee-2025-02.md` (Elena Vargas)

## Insufficient-evidence examples

Ask these on the seeded engagement; expect `insufficient_evidence` with suggestions:

1. What is the SOC 2 Type II opinion date for Contoso?
2. Did Northwind renew the Azure OpenAI enterprise agreement in FY2025?
3. What was the board-approved bonus pool for the CEO in Q4?
4. What is the FY2026 budgeted capital expenditure for Warehouse C?
5. Was the Contoso MSA amended after 15 March 2025?
""",
)

write(
    "northwind-fy2025/contracts/contoso-msa.md",
    """
# Master Services Agreement

**Document ID:** NW-CTR-2025-001  
**Parties:** Contoso Ltd ("Supplier") and Northwind Traders, Inc. ("Customer")  
**Effective date:** 1 January 2025  
**Governing law:** State of Washington, United States  
**Prepared for engagement:** northwind-fy2025 (fictional sample)

---

## 1. Parties and definitions

### 1.1 Parties

This Master Services Agreement ("Agreement") is entered into as of 1 January 2025 between:

- **Contoso Ltd**, a Delaware corporation with principal place of business at 1 Contoso Way, Redmond, WA 98052 ("Supplier"); and
- **Northwind Traders, Inc.**, a Washington corporation with principal place of business at 100 Market Street, Seattle, WA 98101 ("Customer").

### 1.2 Key definitions

| Term | Meaning |
|------|---------|
| Services | Professional services, software licences, and support described in Statements of Work (SOWs) |
| Confidential Information | Non-public business, technical, or financial information of either party |
| Fees | Amounts payable under an SOW, exclusive of taxes |
| Deliverable | Work product identified in an SOW as deliverable to Customer |

---

## 2. Scope of services

### 2.1 Statements of Work

Supplier shall perform Services only pursuant to mutually executed SOWs referencing this Agreement. Each SOW shall specify scope, fees, milestones, acceptance criteria, and named Supplier personnel.

### 2.2 Change control

Material changes to scope or fees require a written change order signed by both parties' authorised representatives. Verbal instructions do not amend an SOW.

### 2.3 Subcontracting

Supplier may subcontract routine support tasks with prior written notice. Supplier remains fully responsible for subcontractor performance and confidentiality obligations.

---

## 3. Payment terms

### 3.1 Invoices

Supplier shall invoice Customer monthly in arrears for Fees earned in the prior calendar month. Each invoice shall reference the applicable SOW number and include a breakdown of time (where T&M) or milestone status (where fixed fee).

### 3.2 Payment due date

Payment is due within **30 days** of the invoice date ("**Net-30**"). Customer shall pay by ACH or wire to the account designated on the invoice.

### 3.3 Disputed amounts

Customer may withhold only the disputed portion of an invoice and must notify Supplier in writing within fifteen (15) days of receipt, stating the basis for dispute in reasonable detail. Undisputed amounts remain due on the original due date.

### 3.4 Late payment

Overdue undisputed amounts accrue interest at **1.5% per month**, or the maximum rate permitted by applicable law, whichever is lower. Supplier may suspend Services after thirty (30) days' written notice if overdue balances exceed USD 50,000.

### 3.5 Taxes

Fees are exclusive of sales, use, and similar taxes. Customer is responsible for taxes imposed on the purchase of Services, excluding taxes based on Supplier's net income.

---

## 4. Term and termination

### 4.1 Initial term

The initial term is twelve (12) months from the effective date, automatically renewing for successive twelve-month periods unless either party gives written notice of non-renewal at least ninety (90) days before the then-current term ends.

### 4.2 Termination for convenience

Either party may terminate this Agreement or any SOW for convenience with **sixty (60) days** prior written notice. Customer shall pay for Services performed through the effective termination date and for non-cancellable third-party commitments reasonably incurred.

### 4.3 Termination for cause

Either party may terminate immediately upon written notice if the other party materially breaches and fails to cure within thirty (30) days after notice describing the breach.

### 4.4 Effect of termination

Upon termination, Supplier shall deliver work-in-progress and return or securely destroy Customer Confidential Information within thirty (30) days, except one archival copy retained under legal hold.

---

## 5. Intellectual property and confidentiality

### 5.1 Customer data

Customer retains all right, title, and interest in Customer data and Confidential Information. Supplier receives a limited licence to use Customer data solely to perform the Services.

### 5.2 Pre-existing IP

Each party retains its pre-existing intellectual property. Supplier grants Customer a non-exclusive, perpetual, royalty-free licence to use Deliverables for Customer's internal business purposes.

### 5.3 Confidentiality period

Confidentiality obligations survive for **five (5) years** after termination, and indefinitely for trade secrets for so long as they remain trade secrets under applicable law.

---

## 6. Liability and indemnities

### 6.1 Liability cap

Except for wilful misconduct, fraud, or breaches of confidentiality or data protection obligations, each party's aggregate liability under this Agreement shall not exceed the **fees paid in the twelve months preceding the claim**.

### 6.2 Exclusion of consequential damages

Neither party is liable for indirect, incidental, special, or consequential damages, including lost profits or business interruption, even if advised of the possibility.

### 6.3 Indemnity — IP

Supplier shall defend and indemnify Customer against third-party claims that Deliverables infringe a US patent, copyright, or trade secret, subject to prompt notice and control of defence.

### 6.4 Insurance

During the term, Supplier shall maintain commercial general liability of not less than USD 2,000,000 per occurrence and professional liability (E&O) of not less than USD 5,000,000 per claim.

---

## 7. Data protection and security

### 7.1 Security baseline

Supplier shall implement administrative, technical, and physical safeguards consistent with SOC 2 Type II control objectives for systems processing Customer data.

### 7.2 Breach notification

Supplier shall notify Customer within **seventy-two (72) hours** of confirming a Security Incident affecting Customer data, and cooperate with Customer's incident response.

### 7.3 Audit rights

Customer (or its independent auditor) may audit Supplier's relevant controls once per calendar year upon thirty (30) days' notice, during business hours, subject to reasonable confidentiality undertakings.

---

## 8. General

### 8.1 Assignment

Neither party may assign this Agreement without prior written consent, except to an affiliate or successor in connection with a merger or sale of substantially all assets.

### 8.2 Notices

Notices under this Agreement shall be in writing and delivered by overnight courier or confirmed email to the addresses in Section 1.1 (or as updated in writing).

### 8.3 Entire agreement

This Agreement, together with executed SOWs and any Data Processing Addendum, constitutes the entire agreement and supersedes prior proposals relating to its subject matter.

### 8.4 Signatures

| Role | Name | Title | Date |
|------|------|-------|------|
| Supplier | Jordan Hale | VP, Enterprise Sales | 15 Dec 2024 |
| Customer | Priya Nair | CFO, Northwind Traders | 18 Dec 2024 |

---

*End of MSA NW-CTR-2025-001. Related SOW-001 (managed cloud support) filed under contracts/contoso-sow-001.md.*
""",
)

write(
    "northwind-fy2025/contracts/contoso-sow-001.md",
    """
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
""",
)

write(
    "northwind-fy2025/contracts/fabrikam-vendor-agreement.md",
    """
# Vendor Supply Agreement — Fabrikam Components

**Document ID:** NW-CTR-2025-014  
**Buyer:** Northwind Traders, Inc.  
**Seller:** Fabrikam Components LLC  
**Effective date:** 1 February 2025  
**Initial term:** 24 months

## 1. Goods

Seller supplies industrial fasteners, packaging inserts, and private-label hardware kits per Northwind SKU catalogue NW-CAT-2025 (revision C).

## 2. Pricing and payment

- Unit prices are fixed for calendar year 2025 per Schedule A (filed separately).
- Price adjustments for 2026 require sixty (60) days' written notice and mutual agreement.
- Payment terms: **Net-45** from invoice date.
- Early-pay discount: 1.0% if paid within 10 days (optional).

## 3. Delivery and risk of loss

FOB Seller's dock, Portland, OR. Title and risk pass upon loading onto carrier. Target on-time delivery: **95%** of confirmed purchase orders.

## 4. Quality and inspection

Northwind may reject non-conforming goods within fifteen (15) days of receipt. Seller shall replace or credit rejected lots within twenty (20) business days.

## 5. Insurance and indemnity

Seller maintains product liability insurance of not less than **USD 5,000,000** per occurrence and names Northwind as additional insured.

## 6. Audit clause

Northwind Internal Audit (or external auditors) may inspect Seller's quality records related to Northwind orders once per year upon ten (10) business days' notice.

## 7. Termination

Either party may terminate for convenience with ninety (90) days' notice after the first twelve months. Outstanding firm POs remain binding unless cancelled for cause.
""",
)

write(
    "northwind-fy2025/finance/q1-summary.md",
    """
# Northwind Traders — FY2025 Q1 Finance Summary

**Engagement:** External audit FY2025  
**Period:** 1 January 2025 – 31 March 2025  
**Prepared by:** Finance (A. Okonkwo)  
**Reviewed by:** Controller (M. Sato)  
**Document ID:** NW-FIN-Q1-2025  
**Status:** Management representation draft for auditors

Fictional sample data for demo / offline tests.

---

## 1. Executive overview

Q1 FY2025 total revenue was **USD 5,030,000**, up **8%** versus Q1 FY2024 (USD 4,657,000). Gross margin improved 40 bps to 41.2% on favourable product mix in the Pacific Northwest region. Operating expenses were contained relative to plan; EBITDA margin was 18.4%.

Cash and cash equivalents at 31 March 2025: **USD 2,150,000**.

---

## 2. Revenue by stream

| Stream | Amount (USD) | % of total | vs Q1 FY2024 |
|--------|--------------|------------|--------------|
| Product sales | 4,250,000 | 84.5% | +7.1% |
| Services (logistics & white-glove) | 780,000 | 15.5% | +13.0% |
| **Total** | **5,030,000** | **100%** | **+8.0%** |

### 2.1 Geographic mix (product sales)

| Region | Amount (USD) | Notes |
|--------|--------------|-------|
| Pacific Northwest | 1,870,000 | Strong grocery wholesale channel |
| California | 1,210,000 | Soft January; rebound in March |
| Midwest | 720,000 | New distributor onboarded Feb |
| Other US | 450,000 | |
| **Product sales total** | **4,250,000** | |

### 2.2 Top customers (revenue concentration)

| Customer | Q1 revenue (USD) | % of total revenue |
|----------|------------------|--------------------|
| Contoso Retail Group | 612,000 | 12.2% |
| Blue Yonder Markets | 401,000 | 8.0% |
| Harborline Grocers | 288,000 | 5.7% |
| All other | 3,729,000 | 74.1% |

No single customer exceeded 15% of total revenue in Q1.

---

## 3. Cost of goods sold and gross margin

| Metric | Amount (USD) |
|--------|--------------|
| Product COGS | 2,510,000 |
| Services direct cost | 255,000 |
| **Total COGS** | **2,765,000** |
| Gross profit | 2,265,000 |
| Gross margin % | 45.0% product / 67.3% services / **41.2% blended** wait — see note |

**Correction note (reviewed):** Blended gross margin on total revenue is **(5,030,000 − 2,765,000) / 5,030,000 = 45.0%**. The 41.2% figure in the executive overview was an earlier draft error against product-only margin assumptions; auditors should use **45.0% blended** from this table. Product-only gross margin is (4,250,000 − 2,510,000) / 4,250,000 = **40.9%**.

---

## 4. Operating expenses

Total operating expenses: **USD 3,410,000**.

| Line item | Amount (USD) | Commentary |
|-----------|--------------|------------|
| Payroll and benefits | 1,900,000 | Includes Q1 merit cycle effective 1 Mar |
| Logistics and freight | 620,000 | Diesel surcharge elevated |
| Facilities and leases | 285,000 | See lease abstracts |
| IT and cloud (incl. Contoso SOW) | 210,000 | Contoso base + overages |
| Marketing | 145,000 | Trade show Q1 |
| Professional fees | 95,000 | Interim audit kickoff |
| Other OpEx | 155,000 | |
| **Total OpEx** | **3,410,000** | |

---

## 5. Selected balance sheet items at 31 March 2025

| Account | Amount (USD) |
|---------|--------------|
| Cash and cash equivalents | 2,150,000 |
| Trade receivables (gross) | 3,420,000 |
| Allowance for credit losses | (86,000) |
| Inventory (net) | 4,875,000 |
| Trade payables | 2,010,000 |
| Accrued expenses | 640,000 |
| Deferred revenue (services) | 120,000 |

Days sales outstanding (DSO): **61 days** (target ≤ 55). Collection plan documented in workpapers/ar-confirmations-q1.md.

---

## 6. Subsequent events (through 15 April 2025)

- Warehouse B lease amendment signed 8 April 2025 (rent step-up deferred to FY2026).
- No adjusting subsequent events identified for Q1 close.

---

## 7. Management representation (excerpt)

Management confirms that the amounts above are derived from the Q1 trial balance (NW-FIN-TB-2025-03-31) and that known cut-off issues have been adjusted in journal entries JE-2025-031 through JE-2025-044.
""",
)

write(
    "northwind-fy2025/finance/q2-summary.md",
    """
# Northwind Traders — FY2025 Q2 Finance Summary

**Period:** 1 April 2025 – 30 June 2025  
**Document ID:** NW-FIN-Q2-2025  
**Prepared by:** Finance (A. Okonkwo) · **Reviewed by:** Controller (M. Sato)

## Revenue

| Stream | Amount (USD) |
|--------|--------------|
| Product sales | 4,610,000 |
| Services | 805,000 |
| **Total** | **5,415,000** |

Q2 total revenue **USD 5,415,000** (+7.7% vs Q1; +6.2% vs Q2 FY2024).

## Gross profit and OpEx

- COGS: USD 2,980,000 → gross profit USD 2,435,000 (45.0% margin).
- Operating expenses: USD 3,520,000 (payroll USD 1,945,000; logistics USD 655,000).
- Cash at 30 June 2025: **USD 1,980,000** (seasonal inventory build).

## Notable items

1. Contoso Retail Group Q2 revenue USD 640,000 (still <15% concentration).
2. Inventory write-down of USD 42,000 recorded for slow-moving SKU class H (see inventory/obsolescence-memo.md).
3. One-time professional fees USD 75,000 related to ERP access review remediation.
""",
)

write(
    "northwind-fy2025/finance/q3-summary.md",
    """
# Northwind Traders — FY2025 Q3 Finance Summary

**Period:** 1 July 2025 – 30 September 2025  
**Document ID:** NW-FIN-Q3-2025

## Revenue

| Stream | Amount (USD) |
|--------|--------------|
| Product sales | 4,880,000 |
| Services | 860,000 |
| **Total** | **5,740,000** |

Q3 total revenue **USD 5,740,000**. YTD revenue through Q3: **USD 16,185,000**.

## Working capital

| Metric | 30 Sep 2025 |
|--------|-------------|
| Cash | USD 2,420,000 |
| Trade receivables (net) | USD 3,610,000 |
| Inventory (net) | USD 5,120,000 |
| DSO | 58 days |

## Management commentary

Peak season pre-buys drove inventory higher; Warehouse A utilisation averaged 91%. No new customer exceeded 10% of quarterly revenue.
""",
)

write(
    "northwind-fy2025/finance/q4-summary.md",
    """
# Northwind Traders — FY2025 Q4 Finance Summary (draft)

**Period:** 1 October 2025 – 31 December 2025  
**Document ID:** NW-FIN-Q4-2025-DRAFT  
**Status:** Draft pending year-end adjustments

## Revenue (draft)

| Stream | Amount (USD) |
|--------|--------------|
| Product sales | 5,150,000 |
| Services | 920,000 |
| **Total** | **6,070,000** |

Draft FY2025 full-year revenue: **USD 22,255,000** (Q1–Q4 sum).

## Year-end focus areas for audit

1. Cut-off testing around 31 December shipments (bill-and-hold assertions — none asserted).
2. Bonus accrual completeness (employee bonus pool accrued USD 310,000; CEO pool not separately disclosed in these samples).
3. Lease liability remeasurement for Warehouse B amendment.
4. Contingent liability assessment for open vendor claim with Fabrikam (asserted USD 28,000; management records none as probable).
""",
)

write(
    "northwind-fy2025/finance/lease-warehouse-a.txt",
    """
NORTHWIND TRADERS — WAREHOUSE A LEASE ABSTRACT (FY2025)
Document ID: NW-FIN-LEASE-A-2025
Engagement: northwind-fy2025 (fictional)

Landlord: Contoso Properties LLC
Tenant: Northwind Traders, Inc.
Premises: 400 Industrial Way, Unit A, Kent, WA 98032
Use: Dry goods wholesale distribution; no hazardous materials beyond ordinary cleaning supplies
Rentable area: 85,000 sq ft

COMMERCIAL TERMS
Annual base rent: USD 480,000 payable monthly in advance (USD 40,000 per month)
Additional rent (CAM / taxes / insurance estimate FY2025): USD 96,000 (reconciled annually)
Security deposit: USD 80,000 (held by landlord; no interest)
Lease commencement: 1 January 2023
Lease expiry: 31 December 2027
Renewal option: one (1) 3-year renewal at then-market rent; notice due 9 months prior to expiry
Early termination: none for convenience; casualty/condemnation per lease §14

MAINTENANCE AND INSURANCE
Maintenance: Tenant responsible for interior, HVAC filters, and dock equipment;
             Landlord responsible for structure, roof, and exterior envelope
Required insurance: Tenant CGL USD 2,000,000; property insurance on tenant FF&E;
                    Landlord named as additional insured / loss payee as applicable

AUDIT NOTES (prepared 12 Feb 2025)
- Rent expense Q1 FY2025: USD 120,000 base + USD 24,000 estimated CAM = USD 144,000
- No rent concessions or free-rent periods in FY2025
- Related-party disclosure: Contoso Properties LLC is an affiliate of Contoso Ltd (MSA counterparty);
  arm's-length memo on file with Corporate Counsel (not included in this sample tree)
- Right-of-use asset / lease liability measured under ASC 842; discount rate 5.25% (incremental borrowing rate)
""",
)

write(
    "northwind-fy2025/finance/lease-warehouse-b.md",
    """
# Lease Abstract — Warehouse B

**Document ID:** NW-FIN-LEASE-B-2025  
**Landlord:** Cascade Shell Holdings  
**Premises:** 880 River Road, Building B, Tacoma, WA 98421  
**Rentable area:** 42,000 sq ft

## Commercial terms

| Term | Detail |
|------|--------|
| Annual base rent (FY2025) | USD 252,000 (USD 21,000 / month) |
| Security deposit | USD 42,000 |
| Lease expiry | 30 June 2028 |
| Renewal | Two 2-year options at 103% of prior year rent |
| Amendment 8 Apr 2025 | Defers scheduled 3% step-up from 1 Jul 2025 to 1 Jan 2026 |

## Audit implications

- Modification accounting under ASC 842 assessed; remeasurement recorded in Q2 (JE-2025-088).
- No related-party indicators identified for Cascade Shell Holdings.
""",
)

write(
    "northwind-fy2025/finance/ap-aging-2025-03-31.md",
    """
# Accounts Payable Aging — 31 March 2025

**Document ID:** NW-FIN-AP-AGE-2025-03-31  
**Source system:** Northwind ERP AP module export  
**Prepared by:** AP Supervisor (R. Delgado)

## Summary by aging bucket

| Bucket | Amount (USD) | % |
|--------|--------------|---|
| Current (0–30) | 1,420,000 | 70.6% |
| 31–60 | 380,000 | 18.9% |
| 61–90 | 145,000 | 7.2% |
| >90 | 65,000 | 3.2% |
| **Total trade payables** | **2,010,000** | **100%** |

## Top 10 vendors

| Vendor | Total due (USD) | Terms | Oldest open invoice |
|--------|-----------------|-------|---------------------|
| Contoso Ltd | 55,500 | Net-30 | 12 Mar 2025 |
| Fabrikam Components LLC | 128,400 | Net-45 | 5 Feb 2025 |
| Pacific Freight Co. | 86,200 | Net-15 | 22 Mar 2025 |
| Cascade Shell Holdings | 21,000 | Net-30 | 1 Mar 2025 (rent) |
| Contoso Properties LLC | 40,000 | Net-30 | 1 Mar 2025 (rent) |
| Office supply & other (aggregated) | 1,678,900 | Various | — |

## Audit selections

Auditors selected vouchers AP-2025-1187, AP-2025-1201, and AP-2025-1244 for three-way match testing (PO / receiving / invoice). Results documented in workpapers/ap-three-way-match.md.
""",
)

write(
    "northwind-fy2025/finance/bank-reconciliation-operating.md",
    """
# Bank Reconciliation — Operating Account

**Document ID:** NW-FIN-BANK-OP-2025-03-31  
**Account:** First Cascade Bank ****4821 (Operating)  
**Statement date:** 31 March 2025  
**GL cash balance:** USD 1,862,440  
**Bank statement balance:** USD 1,941,105

## Reconciliation

| Description | Amount (USD) |
|-------------|--------------|
| Balance per bank statement | 1,941,105 |
| Add: Deposits in transit | 48,220 |
| Less: Outstanding cheques | (126,885) |
| **Reconciled bank balance** | **1,862,440** |
| Balance per GL | 1,862,440 |
| Difference | **0** |

## Outstanding cheques > USD 10,000

| Cheque # | Payee | Amount (USD) | Date |
|----------|-------|--------------|------|
| 104482 | Pacific Freight Co. | 42,100 | 28 Mar 2025 |
| 104491 | Fabrikam Components LLC | 38,750 | 29 Mar 2025 |
| 104502 | Cascade Shell Holdings | 21,000 | 31 Mar 2025 |

## Controls note

Reconciliation prepared by Staff Accountant (L. Ng) and reviewed by Assistant Controller (K. Berg) on 4 April 2025. Reviewer signature on PDF archive (not in sample tree). No unreconciled items > USD 1,000.
""",
)

write(
    "northwind-fy2025/finance/trial-balance-q1.md",
    """
# Trial Balance Extract — 31 March 2025

**Document ID:** NW-FIN-TB-2025-03-31  
**Currency:** USD  
**Source:** ERP general ledger (unaudited)

| Account | Debit | Credit |
|---------|------:|-------:|
| 1000 Cash — operating | 1,862,440 | |
| 1010 Cash — payroll | 287,560 | |
| 1100 Trade receivables | 3,420,000 | |
| 1110 Allowance for credit losses | | 86,000 |
| 1200 Inventory | 4,875,000 | |
| 1500 Prepaid expenses | 210,000 | |
| 1600 ROU assets — leases | 3,150,000 | |
| 2000 Trade payables | | 2,010,000 |
| 2100 Accrued expenses | | 640,000 |
| 2200 Deferred revenue | | 120,000 |
| 2500 Lease liabilities | | 3,280,000 |
| 3000 Common stock | | 500,000 |
| 3100 Retained earnings | | 5,138,000 |
| 4000 Product revenue | | 4,250,000 |
| 4100 Services revenue | | 780,000 |
| 5000 COGS — product | 2,510,000 | |
| 5100 COGS — services | 255,000 | |
| 6000 Payroll expense | 1,900,000 | |
| 6100 Logistics expense | 620,000 | |
| 6200 Facilities expense | 285,000 | |
| 6300 IT & cloud expense | 210,000 | |
| 6400 Other OpEx | 395,000 | |
| **Totals** | **20,000,000** | **20,000,000** |

Note: Rounded presentation for sample readability; production TB includes sub-accounts.
""",
)

write(
    "northwind-fy2025/policies/expense-policy.md",
    """
# Employee Expense Policy — Northwind Traders

**Policy ID:** NW-POL-EXP-2025.1  
**Version:** 2025.1  
**Effective date:** 1 January 2025  
**Owner:** Controllership  
**Approver:** CFO (Priya Nair)  
**Applies to:** All employees and contingent workers submitting expenses for reimbursement

---

## 1. Purpose and principles

This policy sets rules for reimbursable business expenses. Expenses must be:

1. Necessary for Northwind business;
2. Reasonable in amount;
3. Properly documented; and
4. Approved per Section 5.

Personal expenses are not reimbursable. Split receipts (business vs personal) must clearly isolate the business portion.

---

## 2. Meal limits

| Category | Limit |
|----------|-------|
| Domestic travel meals | Maximum **USD 75 per person per day** |
| International travel meals | Maximum **USD 120 per person per day** |
| Client entertainment (meals) | USD 150 per person per event, with business purpose documented |
| Internal team meals (non-travel) | USD 40 per person; requires director pre-approval above 8 attendees |

Alcohol is not reimbursable unless pre-approved in writing for a client entertainment event. Tips up to 20% are included within the meal limit (not additive).

---

## 3. Lodging and airfare

- Lodging: standard business hotel; nightly rate should not exceed GSA-equivalent + 20% for the city without VP approval.
- Airfare: economy class for flights under 6 hours; premium economy allowed for 6+ hour segments with director approval. First class prohibited.
- Advance purchase: tickets should be booked at least 14 days before departure when practicable.

---

## 4. Receipts and documentation

Original itemised receipts are required for any expense of **USD 25 or more**. Soft copies uploaded to the expense system are acceptable if legible.

Each expense line must include:

- Date and merchant;
- Business purpose (who / what / why);
- Attendee names for meals; and
- Project or cost centre code.

Missing receipts above USD 25 require a Missing Receipt Affidavit and controller approval.

---

## 5. Approval matrix

| Report total | Approver |
|--------------|----------|
| Up to USD 2,000 | Direct manager |
| Above USD 2,000 up to USD 10,000 | Director |
| Above USD 10,000 | VP Finance or CFO |

Managers must approve expense reports within **ten business days**. Finance may reject reports that violate this policy; resubmission restarts the approval clock.

---

## 6. Corporate card and cash advances

Corporate cards are issued to eligible travellers. Personal use is prohibited. Cash advances require VP approval and must be settled within ten business days of trip end.

---

## 7. Exceptions and violations

Policy exceptions require documented CFO approval before the expense is incurred when foreseeable. Repeated violations may result in card suspension and HR escalation.

---

## 8. Related policies

- NW-POL-TRV-2025 Travel Policy (companion)
- NW-POL-GFT-2025 Gifts & Entertainment (anti-bribery)
- NW-POL-AC-2025 Logical Access Control Policy
""",
)

write(
    "northwind-fy2025/policies/access-control.md",
    """
# Logical Access Control Policy

**Policy ID:** NW-POL-AC-2025  
**Version:** 3.2  
**Effective date:** 1 January 2025  
**Owner:** IT Security  
**Approver:** CIO  
**Classification:** Internal

---

## 1. Purpose

This policy establishes requirements for authenticating users, authorising access to systems and data, and reviewing access on a recurring basis. It supports SOX-relevant ITGCs and customer contractual security commitments.

---

## 2. Privileged access

Privileged (admin) accounts must use multi-factor authentication. Shared admin passwords are prohibited. Privileged access must be:

- Requested via the IAM ticket workflow;
- Approved by the system owner and the requester's manager;
- Time-bound where practicable (e.g., break-glass valid ≤ 8 hours); and
- Logged and retained for at least 12 months.

Domain and cloud administrator groups are reviewed monthly by IT Security.

---

## 3. Joiner–mover–leaver

| Event | Requirement |
|-------|-------------|
| Joiner | Access provisioned only after HR start confirmation and manager approval |
| Mover | Access adjusted within **3 business days** of role change effective date |
| Leaver | Access for terminated employees must be revoked within **24 hours** of the HR termination effective time |

Contractors follow the same leaver timeline based on contract end date in the vendor management system.

Emergency terminations (security or legal) require immediate revocation; IT Security on-call must be paged.

---

## 4. Quarterly access review

Application owners must review user access listings at least once per quarter and certify results to Internal Audit within fifteen (15) business days after quarter-end. Reviews cover:

- ERP (finance, AP, AR, inventory);
- CRM;
- Identity provider admin roles; and
- Data warehouse analyst roles with PII access.

Exceptions (users retaining access without business need) are logged and remediated within thirty (30) days.

---

## 5. Password and MFA baseline

- Minimum password length: 14 characters (or passphrase ≥ 4 words).
- MFA required for all remote access and all privileged roles.
- Service accounts: unique credentials in the secrets vault; password rotation at least every 90 days unless certificate-based auth is used.

---

## 6. Enforcement

Non-compliance may result in access suspension. Material control failures are reported to the Audit Committee via the quarterly ITGC summary.
""",
)

write(
    "northwind-fy2025/policies/procurement-policy.md",
    """
# Procurement and Purchasing Policy

**Policy ID:** NW-POL-PROC-2025  
**Effective:** 1 January 2025 · **Owner:** VP Operations

## Purchase authorisation

| Amount (USD) | Required approval |
|--------------|-------------------|
| Up to 5,000 | Cost centre manager |
| 5,001 – 25,000 | Director |
| 25,001 – 100,000 | VP |
| Above 100,000 | CFO (and Legal review for contracts) |

Purchase orders are mandatory above **USD 1,000** except utilities, rent, and payroll.

## Competitive bidding

Purchases above USD 50,000 require three written quotes unless a preferred-vendor agreement exists (e.g., Contoso MSA, Fabrikam Vendor Supply Agreement) or a sole-source justification is approved by a VP.

## Segregation of duties

The same individual may not create a vendor, approve a PO, and process payment. ERP enforces SOD rulesets SOD-AP-01 through SOD-AP-06; quarterly SOD reports go to Internal Audit.
""",
)

write(
    "northwind-fy2025/policies/revenue-recognition.md",
    """
# Revenue Recognition Policy (ASC 606 summary)

**Policy ID:** NW-POL-REV-2025  
**Owner:** Controller · **Effective:** 1 January 2025

## Product sales

Revenue from product sales is recognised when control transfers to the customer, typically upon shipment FOB shipping point, or upon delivery for FOB destination terms. Bill-and-hold arrangements require documented business purpose, segregation of inventory, and customer written request — Northwind did not assert bill-and-hold in FY2025 Q1–Q3.

## Services

Logistics and white-glove services revenue is recognised over time as services are rendered, using output methods (shipments completed) where representative of transfer of control. Fixed monthly retainers are recognised ratably.

## Variable consideration

Volume rebates and early-pay discounts are estimated using the expected-value method and constrained such that a significant reversal is not probable. Rebate accruals are reviewed monthly by the Revenue Accountant.

## Contract costs

Incremental costs to obtain a contract (e.g., sales commissions on multi-year service deals) are capitalised when recoverable and amortised over the expected contract period.
""",
)

write(
    "northwind-fy2025/hr/joiner-mover-leaver-log.md",
    """
# Joiner–Mover–Leaver Log (IT access) — Q1 FY2025

**Document ID:** NW-HR-JML-2025-Q1  
**Prepared by:** HRIS + IT Security joint extract  
**Period:** 1 Jan 2025 – 31 Mar 2025

## Summary

| Category | Count |
|----------|------:|
| Joiners | 14 |
| Movers | 6 |
| Leavers | 9 |

## Leavers — access revocation timing

| Employee ID | Effective termination | Access revoked | Hours to revoke | Within 24h? |
|-------------|----------------------|----------------|-----------------|-------------|
| E-1042 | 2025-01-10 17:00 | 2025-01-10 18:40 | 1.7 | Yes |
| E-1108 | 2025-01-24 12:00 | 2025-01-24 15:10 | 3.2 | Yes |
| E-0988 | 2025-02-07 17:00 | 2025-02-08 09:05 | 16.1 | Yes |
| E-1211 | 2025-02-14 17:00 | 2025-02-14 17:55 | 0.9 | Yes |
| E-0877 | 2025-02-28 17:00 | 2025-03-01 10:20 | 17.3 | Yes |
| E-1302 | 2025-03-07 12:00 | 2025-03-07 14:00 | 2.0 | Yes |
| E-1155 | 2025-03-14 17:00 | 2025-03-15 11:45 | 18.8 | Yes |
| E-1020 | 2025-03-21 17:00 | 2025-03-22 08:30 | 15.5 | Yes |
| E-1199 | 2025-03-28 17:00 | 2025-03-29 16:50 | 23.8 | Yes |

All nine Q1 leavers met the **24-hour** revocation requirement in NW-POL-AC-2025. No exceptions logged.

## Sample joiners (excerpt)

New warehouse associates E-1401 through E-1406 received ERP inventory-clerk roles only; no AP payment authority granted (SOD check passed).
""",
)

write(
    "northwind-fy2025/hr/org-chart-finance.md",
    """
# Finance Organisation Chart (FY2025)

**Document ID:** NW-HR-ORG-FIN-2025

- **CFO** — Priya Nair
  - **Controller** — Mina Sato
    - Assistant Controller — Kai Berg
    - Revenue Accountant — Softa Ren
    - AP Supervisor — Rosa Delgado
    - Staff Accountants — Linh Ng, Omar Haddad
  - **FP&A Director** — Chris Vale
  - **Treasury Manager** — Dana Cho
- **Internal Audit Director** (dotted to Audit Committee) — Elena Vargas (committee chair is also Elena Vargas — see minutes; IA day-to-day led by Acting IA Manager Samir Patel while chair role is board-level)

Clarification for auditors: **Elena Vargas** chairs the Board Audit Committee and is an independent director. Day-to-day Internal Audit is led by **Samir Patel** (Acting IA Manager).
""",
)

write(
    "northwind-fy2025/inventory/cycle-count-q1.md",
    """
# Inventory Cycle Count Results — Q1 FY2025

**Document ID:** NW-INV-CC-2025-Q1  
**Locations:** Warehouse A (Kent) and Warehouse B (Tacoma)  
**Count window:** 18–20 March 2025  
**Method:** ABC stratified sample; blind counts with independent recount of variances > 2% or USD 500

## Scope

| Location | SKUs in population | SKUs counted | Coverage of extended value |
|----------|-------------------|--------------|----------------------------|
| Warehouse A | 1,840 | 80 | 62% |
| Warehouse B | 920 | 40 | 55% |
| **Total** | **2,760** | **120** | **59%** |

**120 SKUs** were counted in the Q1 cycle count programme.

## Results

| Metric | Result |
|--------|--------|
| Exact matches | 101 SKUs |
| Variances within tolerance | 14 SKUs |
| Variances requiring adjustment | 5 SKUs |
| Net book-to-physical adjustment | USD (18,400) write-down |

## Root causes (adjusted SKUs)

1. Receiving cut-off error (2 SKUs) — goods received 19 Mar booked 21 Mar; corrected via JE-2025-041.
2. Pick-face mis-slot (2 SKUs) — quantities found in adjacent bins.
3. Damaged goods not moved to quarantine (1 SKU) — written off.

## Conclusion

No pervasive inventory control deficiency indicated for Q1. Absolute variance rate 4.2% of counted SKUs; extended-value accuracy 99.6% after adjustments. Full physical observation planned for year-end at Warehouse A.
""",
)

write(
    "northwind-fy2025/inventory/obsolescence-memo.md",
    """
# Inventory Obsolescence Assessment Memo

**Document ID:** NW-INV-OBS-2025-Q2  
**Date:** 15 July 2025  
**From:** Controller (M. Sato)  
**To:** External Audit File

## Policy

Inventory is stated at lower of cost or net realisable value. Slow-moving thresholds: no movement in 180 days (Class H) or 270 days (Class M) triggers NRV review.

## Q2 FY2025 action

SKU class H (seasonal packaging inserts) showed 210 days without movement and declining replacement demand after a customer redesign. NRV test supported a write-down of **USD 42,000**, recorded in JE-2025-102 (Dr COGS / Cr Inventory).

Remaining Class H inventory after write-down: USD 61,000, supported by expected Q4 promotional use with Contoso Retail Group (non-binding forecast).
""",
)

write(
    "northwind-fy2025/minutes/audit-committee-2025-02.md",
    """
# Audit Committee Meeting Minutes — 12 February 2025

**Document ID:** NW-MIN-AC-2025-02  
**Entity:** Northwind Traders, Inc.  
**Meeting date:** 12 February 2025, 09:00–11:10 PT  
**Location:** Hybrid — Seattle HQ Boardroom / video

## Attendance

| Role | Name | Present |
|------|------|---------|
| Chair, Audit Committee | **Elena Vargas** | Yes |
| Committee member | Robert Lang | Yes |
| Committee member | Naomi Brooks | Yes (video) |
| CFO | Priya Nair | Yes |
| Controller | Mina Sato | Yes |
| Acting IA Manager | Samir Patel | Yes |
| External audit engagement partner | (firm redacted in sample) | Yes |

Quorum present. Meeting called to order by Chair **Elena Vargas** at 09:03.

## 1. Prior minutes

Minutes of 10 November 2024 approved without amendment.

## 2. External audit planning

Engagement partner presented FY2025 audit plan. Planning materiality of **USD 250,000** and performance materiality of USD 187,500 discussed (see workpapers/materiality-memo.md). Committee approved the plan subject to refinement after interim procedures.

Key risk areas agreed:

- Revenue cut-off and rebate accruals;
- Inventory existence and valuation at Warehouse A;
- Related-party lease with Contoso Properties LLC;
- ITGC reliance for ERP automated controls.

## 3. Internal audit update

Samir Patel reported Q4 FY2024 IA findings: two medium-rated issues (AP SOD exception; late access review certification). Both remediated as of 31 January 2025. Q1 FY2025 IA plan includes expense report analytics and vendor master changes.

## 4. Whistleblower / ethics

No open hotline matters requiring committee attention.

## 5. Adjournment

Meeting adjourned at 11:10. Next meeting scheduled 8 May 2025.

**Secretary:** Naomi Brooks  
**Chair signature:** Elena Vargas (signed 14 Feb 2025)
""",
)

write(
    "northwind-fy2025/workpapers/materiality-memo.md",
    """
# Planning Materiality Memorandum — FY2025

**Document ID:** NW-WP-MAT-2025  
**Engagement:** Northwind Traders financial statement audit FY2025  
**Prepared:** 5 February 2025  
**Preparer:** Audit Senior · **Reviewer:** Audit Manager

## Benchmark

Based on forecast FY2025 pre-tax income of approximately USD 2.5 million and prior-year total revenue of USD 20.6 million, the engagement team selected **total revenue** as the primary benchmark given Northwind's growth profile and user focus on top-line performance.

## Determination

| Element | Amount (USD) |
|---------|--------------|
| Forecast FY2025 revenue | 21,500,000 |
| Percentage applied | ~1.2% |
| **Planning materiality** | **250,000** |
| Performance materiality (75%) | 187,500 |
| Clearly trivial threshold (5% of PM) | 9,375 |

## Rationale

1.2% of forecast revenue yields USD 250,000, consistent with prior-year planning materiality (USD 230,000) adjusted for growth. Audit Committee informed on 12 February 2025.

## Revision triggers

Materiality will be revisited if actual YTD revenue through Q3 varies by more than 10% from forecast or if a significant unusual transaction occurs.
""",
)

write(
    "northwind-fy2025/workpapers/revenue-testing-sample.md",
    """
# Revenue Substantive Testing — Sample Results Q1

**Document ID:** NW-WP-REV-Q1-2025  
**Population:** Product sales invoices 1 Jan – 31 Mar 2025 (USD 4,250,000)  
**Method:** Monetary unit sampling; 28 selections

## Objectives

Test occurrence, accuracy, and cut-off of product revenue.

## Results summary

| Attribute | Exceptions |
|-----------|------------|
| Invoice agrees to customer PO | 0 |
| Quantity/price agree to shipping docs | 1 (immaterial pricing typo USD 120 — corrected) |
| Revenue recorded in correct period | 0 |
| Customer exists / not related party (sample) | 0 |

## Conclusion

One trivial exception below clearly trivial threshold after correction. No projected misstatement above performance materiality. Extend testing at year-end for December cut-off.
""",
)

write(
    "northwind-fy2025/workpapers/ap-three-way-match.md",
    """
# AP Three-Way Match Testing

**Document ID:** NW-WP-AP-3WM-2025-Q1  
**Selections:** AP-2025-1187, AP-2025-1201, AP-2025-1244

| Voucher | Vendor | Amount (USD) | PO | Receipt | Invoice | Match? |
|---------|--------|--------------|----|---------|---------|--------|
| AP-2025-1187 | Fabrikam Components LLC | 38,750 | Yes | Yes | Yes | Yes |
| AP-2025-1201 | Pacific Freight Co. | 42,100 | Yes | N/A (service) | Yes | Yes* |
| AP-2025-1244 | Contoso Ltd | 18,500 | Yes (MSA/SOW) | N/A (service) | Yes | Yes |

\\* Service invoices require PO + approved receiver acknowledgement in lieu of goods receipt.

No exceptions. SOD: voucher entry by AP clerk; payment batch approved by Assistant Controller.
""",
)

write(
    "northwind-fy2025/workpapers/ar-confirmations-q1.md",
    """
# Accounts Receivable Confirmations — Q1 Interim

**Document ID:** NW-WP-AR-CONF-2025-Q1  
**Confirmation date:** 31 March 2025

## Strategy

Positive confirmations for all customers with balances ≥ USD 100,000; random sample of smaller balances.

| Metric | Count / Amount |
|--------|----------------|
| Confirmations sent | 18 |
| Balances covered | USD 2,410,000 (70% of gross AR) |
| Timely responses | 15 |
| Alternative procedures applied | 3 |
| Exceptions | 1 |

## Exception

Harborline Grocers reported USD 12,000 timing difference (payment mailed 31 Mar, cleared 2 Apr). Bank support obtained; no misstatement to Q1 revenue. DSO remains elevated at 61 days; management collection plan noted in finance/q1-summary.md.
""",
)

# ---------------------------------------------------------------------------
# fabrikam-sox-fy2025 — SOX 404 / internal controls over financial reporting
# ---------------------------------------------------------------------------

write(
    "fabrikam-sox-fy2025/README.md",
    """
# Fabrikam SOX FY2025 (AI-generated sample)

Fictional SOX 404 / ICFR engagement for **Fabrikam Manufacturing Corp.** (discrete manufacturing).
Period: FY2025. Not real client data.

Folders: `scoping/`, `controls/`, `testing/`, `itgc/`, `deficiencies/`, `finance/`.

## Answerable examples

1. What is FY2025 SOX planning materiality? → `scoping/scoping-memo.md` (USD 1,200,000)
2. What is the control ID for monthly journal entry review? → `controls/rcm-entity-level.md` (ELC-04)
3. How many samples were tested for cash disbursements? → `testing/cash-disbursement-test.md` (25)
4. What is the change management ticket SLA for production deployments? → `itgc/change-management.md` (100% CAB approval before prod)
5. Is deficiency DEF-2025-03 rated material weakness? → `deficiencies/deficiency-log.md` (No — significant deficiency)
6. Who owns control OTC-12 (credit limit approval)? → `controls/revenue-process-narrative.md` (Credit Manager)

## Insufficient-evidence examples

1. What was the external auditor's SOX opinion date for FY2024?
2. Did Fabrikam remediate DEF-2024-11 before 1 January 2025?
3. What is the FY2026 internal audit budget approved by the board?
""",
)

write(
    "fabrikam-sox-fy2025/scoping/scoping-memo.md",
    """
# SOX 404 Scoping Memorandum — FY2025

**Document ID:** FB-SOX-SCOPE-2025  
**Entity:** Fabrikam Manufacturing Corp.  
**Prepared by:** SOX PMO · **Date:** 20 January 2025  
**Distribution:** CFO, Controller, Internal Audit, External Auditors

---

## 1. Objective

Define in-scope locations, processes, and systems for management's assessment of internal control over financial reporting (ICFR) under SOX Section 404 for the year ending 31 December 2025.

## 2. Materiality and quantitative thresholds

| Metric | Amount (USD) |
|--------|--------------|
| Forecast FY2025 consolidated pre-tax income | 24,000,000 |
| **SOX planning materiality** | **1,200,000** |
| Tolerable misstatement for process scoping | 600,000 |
| Account significance threshold (qualitative override allowed) | 300,000 |

Accounts and disclosures exceeding the significance threshold, or posing qualitative fraud / complexity risk, are in scope even if below quantitative thresholds.

## 3. In-scope locations

| Location | Nature | In scope? | Rationale |
|----------|--------|-----------|-----------|
| Fabrikam HQ — Redmond, WA | Corporate, finance, IT | Yes | Consolidation and control ownership |
| Plant 1 — Spokane, WA | Manufacturing & shipping | Yes | >40% of COGS and inventory |
| Plant 2 — Boise, ID | Manufacturing | Yes | >25% of COGS |
| Sales office — Chicago | Sales only | No | No local GL; orders in HQ ERP |
| EMEA sales agent (3rd party) | Commission | No | Immaterial commissions; monitored via ELCs |

## 4. In-scope processes

1. Entity-level controls (control environment, risk assessment, monitoring)
2. Order-to-cash (OTC)
3. Procure-to-pay (PTP)
4. Inventory & costing
5. Payroll & equity
6. Period-end financial reporting (PEFR)
7. Treasury & cash
8. IT general controls for in-scope systems (ERP, payroll, consolidation tool)

## 5. In-scope systems

| System | Process support | ITGC in scope |
|--------|-----------------|---------------|
| FabrikamERP (on-prem) | OTC, PTP, inventory, PEFR | Yes |
| PayStar | Payroll | Yes |
| Consolid8 | Consolidation & reporting | Yes |
| CRM Cloud | Pipeline only | No (no GL posting) |

## 6. Out-of-scope rationale (examples)

- Facilities management system: no financial postings.
- Marketing automation: expenses captured via PTP invoices only.

## 7. Fraud risk considerations

Management identified revenue cut-off near period-end and manual journal entries as elevated fraud risks. Corresponding controls OTC-18 (shipping cut-off) and ELC-04 (JE review) are designated as key controls with higher testing extent.

## 8. Approval

| Role | Name | Date |
|------|------|------|
| CFO | Helen Cho | 22 Jan 2025 |
| Controller | Mark Ellison | 21 Jan 2025 |
| SOX PMO Lead | Rita Gomez | 20 Jan 2025 |
""",
)

write(
    "fabrikam-sox-fy2025/controls/rcm-entity-level.md",
    """
# Risk & Control Matrix — Entity-Level Controls

**Document ID:** FB-SOX-RCM-ELC-2025  
**Process:** Entity-Level Controls  
**Fiscal year:** 2025

| Control ID | Control description | Risk addressed | Frequency | Owner | Key? | Nature |
|------------|---------------------|----------------|-----------|-------|------|--------|
| ELC-01 | Board Audit Committee meets at least quarterly; minutes retained | Ineffective oversight | Quarterly | Corporate Secretary | Yes | Manual |
| ELC-02 | Code of Conduct acknowledgement by all employees annually | Tone / ethics failures | Annual | HR | Yes | Manual / IT-dependent |
| ELC-03 | Whistleblower hotline monitored; summary to Audit Committee | Fraud non-detection | Quarterly | General Counsel | Yes | Manual |
| ELC-04 | Controller reviews all manual journal entries > USD 25,000 monthly; evidence of review retained | Inappropriate JE / override | Monthly | Controller | Yes | Manual |
| ELC-05 | Annual fraud risk assessment workshop documented | Incomplete fraud risk response | Annual | SOX PMO | Yes | Manual |
| ELC-06 | Management representation letters obtained from process owners each quarter | Incomplete deficiency reporting | Quarterly | SOX PMO | Yes | Manual |
| ELC-07 | Internal Audit plan approved by Audit Committee | Monitoring gap | Annual | IA Director | No | Manual |

## Testing approach (management)

For key ELCs, management tests operating effectiveness via inquiry, observation, and inspection of evidence for a sample of occurrences (or full population when frequency ≤ 4). ELC-04 sample size follows the monthly frequency table in testing/sampling-methodology.md (generally 2–3 months interim + year-end roll-forward).
""",
)

write(
    "fabrikam-sox-fy2025/controls/revenue-process-narrative.md",
    """
# Process Narrative — Order to Cash (OTC)

**Document ID:** FB-SOX-NAR-OTC-2025  
**Last updated:** 3 March 2025  
**Walkthrough participants:** Credit Manager, AR Manager, Shipping Supervisor, Revenue Accountant

---

## 1. Overview

Fabrikam sells manufactured components to OEM and distributor customers. Orders are entered in FabrikamERP. Credit limits are enforced before order release. Goods ship from Plant 1 or Plant 2; invoices generate automatically on post-goods-issue (PGI). Cash application is centralised at HQ.

## 2. Key risks

| Risk ID | Description |
|---------|-------------|
| R-OTC-01 | Orders accepted for customers exceeding credit limit |
| R-OTC-02 | Revenue recorded before control of goods transfers |
| R-OTC-03 | Invoices priced incorrectly vs customer contract |
| R-OTC-04 | Cash receipts misapplied or diverted |
| R-OTC-05 | Period-end cut-off errors for shipments |

## 3. Key controls

### OTC-08 — Customer master changes

Changes to banking details or credit terms require dual approval (AR Manager + Credit Manager). System workflow enforces dual approval; SOD report reviewed quarterly.

### OTC-12 — Credit limit approval

New or increased credit limits above USD 50,000 require approval by the **Credit Manager**. Limits above USD 250,000 also require CFO approval. Evidence: credit application package + system approval log.

### OTC-15 — Price vs contract

Nightly automated job compares invoice prices to active contract price list; exceptions > 1% routed to Revenue Accountant for clearance before period close.

### OTC-18 — Shipping cut-off

Shipping Supervisor reviews open deliveries at period-end; Revenue Accountant inspects last-five / first-five shipments across period-end for cut-off. Evidence retained in PEFR binder.

### OTC-22 — Bank reconciliation & cash application

Treasury reconciles lockbox remittances daily; unapplied cash > USD 5,000 aged and reviewed weekly by AR Manager.

## 4. Systems and automated controls

FabrikamERP hard-blocks order release when outstanding exposure exceeds credit limit unless a documented override is approved by Credit Manager (control OTC-12a — override log reviewed monthly).

## 5. Segregation of duties

Credit limit approval (Credit Manager) is segregated from cash application (AR clerks) and from customer master bank-detail changes (requires AR Manager + Credit Manager).
""",
)

write(
    "fabrikam-sox-fy2025/controls/ptp-process-narrative.md",
    """
# Process Narrative — Procure to Pay (PTP)

**Document ID:** FB-SOX-NAR-PTP-2025

## Flow summary

1. Requisition raised in FabrikamERP by requesting department.
2. PO approved per matrix (manager / director / VP / CFO).
3. Goods receipt posted by receiving (plants) or service acknowledgement (HQ).
4. Three-way match (PO / GR / invoice) within 2% / USD 100 tolerance; exceptions to AP Supervisor.
5. Payment runs twice weekly; payment file approved by Treasury Manager before release.

## Key controls

| Control ID | Description | Owner |
|------------|-------------|-------|
| PTP-03 | PO approval per DOA matrix enforced in workflow | Procurement |
| PTP-07 | Three-way match required before invoice payment | AP Supervisor |
| PTP-11 | Vendor master bank changes dual-approved | AP Manager + Treasury |
| PTP-14 | Payment file reviewed and released by Treasury Manager | Treasury |
| PTP-18 | Monthly AP aging reviewed by Controller | Controller |
""",
)

write(
    "fabrikam-sox-fy2025/testing/sampling-methodology.md",
    """
# SOX Testing Sampling Methodology — FY2025

**Document ID:** FB-SOX-SAMP-2025

## Frequency tables (management testing)

| Control frequency | Minimum sample (no exceptions expected) |
|-------------------|-----------------------------------------|
| Annual | 1 |
| Quarterly | 2 |
| Monthly | 2 interim + 1 roll-forward |
| Weekly | 5 |
| Daily / many | 25 |

If an exception is found, expand sample per PCAOB-aligned guidance used by the SOX PMO (typically +25 for daily controls) and evaluate deficiency severity.

## Evidence standards

- Screenshots must show user ID, timestamp, and relevant document number.
- Approvals must be attributable (system workflow or wet/electronic signature).
- Inquiry alone is insufficient for operating effectiveness of key controls.
""",
)

write(
    "fabrikam-sox-fy2025/testing/cash-disbursement-test.md",
    """
# Operating Effectiveness Test — Cash Disbursements (PTP-14)

**Document ID:** FB-SOX-TEST-PTP14-2025  
**Control:** PTP-14 — Payment file reviewed and released by Treasury Manager  
**Period tested:** 1 January 2025 – 30 September 2025 (interim)  
**Tester:** SOX Analyst J. Park · **Reviewer:** SOX Manager L. Ortiz

## Population and sample

- Population: 78 payment runs in interim period.
- Frequency: ~2× weekly → daily/many table applies.
- **Sample size: 25** payment runs selected using random number generator seeded in workpaper archive.

## Procedures

For each selection, inspected:

1. Payment file export hash / control total;
2. Treasury Manager approval email or workflow timestamp before bank release;
3. Agreement of control total to bank confirmation of file acceptance.

## Results

| Attribute | Exceptions |
|-----------|------------|
| Approval before release | 0 |
| Control total agrees | 0 |
| Approver was authorised Treasury Manager (or documented delegate) | 1 |

### Exception detail

Selection #17 (14 May 2025): approval by Assistant Treasurer under standing delegation letter dated 2 May 2025 (CFO authorised). Treated as **deviation without deficiency** — delegation was valid and within policy. No sample expansion required.

## Conclusion

Control PTP-14 operated effectively for the interim period. Year-end roll-forward of 5 additional items planned for Q4.
""",
)

write(
    "fabrikam-sox-fy2025/testing/walkthrough-order-to-cash.md",
    """
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
""",
)

write(
    "fabrikam-sox-fy2025/testing/elc-04-journal-entry-test.md",
    """
# Operating Effectiveness Test — ELC-04 Manual JE Review

**Document ID:** FB-SOX-TEST-ELC04-2025  
**Control:** Controller reviews all manual journal entries > USD 25,000 monthly

## Sample

Months tested at interim: February, May, August 2025 (3 months). For each month, inspected JE register filtered > USD 25,000 and evidence of Controller review (sign-off spreadsheet + email).

## Results

All three months showed timely review (within 10 business days after month-end). One February entry (JE-2025-044, USD 31,200) was reviewed on day 11 — **minor deviation**. Root cause: Controller travel. Compensating: Assistant Controller interim review on day 8, Controller confirmatory review day 11.

## Deficiency assessment

Logged as observation only (not a significant deficiency): severity low, isolated, compensating control operated. See deficiencies/deficiency-log.md (OBS-2025-01).
""",
)

write(
    "fabrikam-sox-fy2025/itgc/change-management.md",
    """
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
""",
)

write(
    "fabrikam-sox-fy2025/itgc/access-to-programs.md",
    """
# ITGC — Access to Programs and Data

**Document ID:** FB-ITGC-AC-2025

## Privileged access

FabrikamERP `SAP_ALL`-equivalent profiles are prohibited in production. Break-glass ID `FB-BREAKGLASS` is vaulted; check-out logged and reviewed weekly by IT Security.

## User access reviews

Business application owners certify ERP role assignments quarterly. Q2 FY2025 certification completed 12 July 2025 with 4 inappropriate access removals (all within 30-day remediation SLA).

## Authentication

Domain MFA enforced for VPN and privileged ERP access. Password minimum length 14; service accounts in CyberArk with 60-day rotation.
""",
)

write(
    "fabrikam-sox-fy2025/deficiencies/deficiency-log.md",
    """
# ICFR Deficiency Log — FY2025 (YTD through Q3)

**Document ID:** FB-SOX-DEF-LOG-2025  
**Owner:** SOX PMO

| ID | Date identified | Control | Description | Severity | Status | Material weakness? |
|----|-----------------|---------|-------------|----------|--------|--------------------|
| OBS-2025-01 | 15 Jun 2025 | ELC-04 | One JE review completed on day 11 vs 10-day expectation | Observation | Closed | No |
| DEF-2025-02 | 28 Jul 2025 | PTP-11 | Vendor bank change approved by single AP Manager during system outage workaround | Significant deficiency candidate → rated **Deficiency** after evaluation | Remediated 10 Aug 2025 | No |
| DEF-2025-03 | 5 Sep 2025 | ITGC-CH-02 | Emergency change CHG-2025-0881 retrospective CAB completed in 3 days (SLA 2) | **Significant deficiency** | Remediation plan in progress (CMS alert) | **No** |

## Evaluation notes for DEF-2025-03

- Not pervasive across ITGCs (214/214 normal changes compliant).
- No misstatement identified related to the change (patch was OS hardening).
- Compensating: production deploy still required peer approval (ITGC-CH-01 operated).
- Classification: **significant deficiency**, not a material weakness.
- Disclosure: included in quarterly management ICFR update to Audit Committee (18 Sep 2025).
""",
)

write(
    "fabrikam-sox-fy2025/finance/materiality-bridge.md",
    """
# Bridge: Financial Statement Materiality vs SOX Planning Materiality

**Document ID:** FB-FIN-MAT-BRIDGE-2025

External audit financial statement planning materiality for FY2025 is USD 1,000,000 (based on pre-tax income). Management SOX planning materiality is **USD 1,200,000** per scoping/scoping-memo.md — intentionally slightly higher for process scoping bands, while key account thresholds remain conservative at USD 300,000.

Teams reconcile differences quarterly; no conflict identified for in-scope process determination.
""",
)

write(
    "fabrikam-sox-fy2025/finance/pefr-checklist.md",
    """
# Period-End Financial Reporting Checklist — August 2025 close

**Document ID:** FB-FIN-PEFR-2025-08  
**Close date:** 8 September 2025

| Step | Owner | Completed | Evidence ref |
|------|-------|-----------|--------------|
| Subledger to GL reconciliation — AR | AR Manager | Yes | PEFR-AR-08 |
| Subledger to GL reconciliation — AP | AP Supervisor | Yes | PEFR-AP-08 |
| Subledger to GL reconciliation — Inventory | Cost Accountant | Yes | PEFR-INV-08 |
| Manual JE register review > USD 25k (ELC-04) | Controller | Yes | JE-REV-08 |
| Flux analysis vs prior month > 10% | FP&A | Yes | FLUX-08 |
| Consolidation package uploaded to Consolid8 | Corp Accounting | Yes | CONS-08 |
| Disclosure checklist (debt, leases, related party) | Controller | Yes | DISC-08 |
| CFO review of draft management accounts | CFO | Yes | Email 8 Sep 2025 |

No late adjustments after CFO review for August close.
""",
)

# ---------------------------------------------------------------------------
# adventureworks-itgc-fy2025 — ITGC / cybersecurity controls audit
# ---------------------------------------------------------------------------

write(
    "adventureworks-itgc-fy2025/README.md",
    """
# Adventure Works ITGC FY2025 (AI-generated sample)

Fictional IT general controls and cybersecurity assurance engagement for **Adventure Works Cycles** (bicycle manufacturing & direct-to-consumer e-commerce).
Period: FY2025. Not real client data.

Folders: `policies/`, `access/`, `change/`, `operations/`, `vendors/`, `testing/`.

## Answerable examples

1. What is the MFA requirement for remote access? → `policies/password-and-mfa.md` (required for all workforce remote access)
2. How often are full backups of the e-commerce database taken? → `policies/backup-and-recovery.md` (daily full)
3. What was the privileged account count in Q1 UAR? → `access/privileged-access-inventory.md` (37)
4. What is the RTO for the online storefront? → `policies/backup-and-recovery.md` (4 hours)
5. How many Sev-1 incidents occurred in Q1–Q2? → `operations/incident-response-log.md` (2)
6. Does the cloud provider bridge letter cover period through 30 June 2025? → `vendors/cloud-provider-soc-bridge-letter.md` (Yes)

## Insufficient-evidence examples

1. What is the penetration test report date for FY2024?
2. Was the SIEM vendor contract renewed at the same price in FY2025?
3. What was the CEO's personal device MDM exception ticket number?
""",
)

write(
    "adventureworks-itgc-fy2025/policies/information-security-policy.md",
    """
# Information Security Policy

**Policy ID:** AW-ISP-2025  
**Entity:** Adventure Works Cycles  
**Version:** 5.1 · **Effective:** 1 January 2025  
**Owner:** CISO · **Approver:** CEO  
**Classification:** Internal

---

## 1. Purpose

Protect the confidentiality, integrity, and availability of Adventure Works information assets, including customer PII, payment data (scoped to PCI DSS responsibilities), intellectual property, and manufacturing OT networks (logically segmented).

## 2. Scope

Applies to all employees, contractors, and systems processing Adventure Works data — corporate IT, e-commerce platform, ERP, and plant floor interfaces to ERP (OT details in AW-OT-SEC-2025, not in this sample set).

## 3. Governance

- CISO reports to CIO with quarterly briefing to Audit Committee.
- Information Security Steering Committee meets monthly.
- Policies reviewed at least annually or upon material control failure.

## 4. Asset management

Information assets are inventoried in the CMDB with an assigned owner and classification (Public, Internal, Confidential, Restricted). Restricted data (customer payment tokens, authentication secrets) requires encryption at rest and in transit.

## 5. Access control

Access follows least privilege and need-to-know. Provisioning and deprovisioning follow AW-ACL-2025. Privileged access is MFA-protected and reviewed quarterly.

## 6. Operations security

Malware protection, vulnerability management (critical patches ≤ 15 days for internet-facing; ≤ 30 days otherwise), logging to SIEM with 12-month retention for security events.

## 7. Cryptography

TLS 1.2+ required for external connections; deprecated protocols disabled on edge. Keys managed in cloud KMS / HSM; no keys in source control.

## 8. Supplier security

Third parties with access to Confidential or Restricted data require security review and contractual flow-down. SOC 2 Type II or equivalent obtained annually for material processors.

## 9. Incident management

Security incidents follow AW-IR-2025. Confirmed breaches involving personal data notify Legal within 4 hours of confirmation for regulatory assessment.

## 10. Exceptions

Risk-accepted exceptions require CISO approval, compensating controls, and expiry ≤ 12 months.
""",
)

write(
    "adventureworks-itgc-fy2025/policies/password-and-mfa.md",
    """
# Password and Multi-Factor Authentication Standard

**Standard ID:** AW-STD-AUTH-2025  
**Parent policy:** AW-ISP-2025  
**Effective:** 1 January 2025

## Password requirements (interactive accounts)

| Requirement | Value |
|-------------|-------|
| Minimum length | 14 characters |
| Complexity | Passphrase encouraged; blocked common passwords via banned-list |
| Maximum age | 365 days (with MFA); 90 days for accounts without MFA (legacy only — none remaining) |
| History | Last 24 passwords |
| Lockout | 10 failed attempts / 15-minute soft lock |

## Multi-factor authentication

**MFA is required for all workforce remote access** (VPN, SSO web apps, email from untrusted networks). MFA is also required for:

- All privileged / administrator roles (including cloud consoles);
- All access to systems processing Restricted data;
- Contractor accounts with Corporate network access.

Accepted MFA factors: phishing-resistant hardware key (preferred), platform authenticator, or TOTP app. SMS OTP is prohibited for privileged roles and discouraged for all users (sunset by 30 June 2025).

## Service accounts

Interactive logon disabled. Credentials stored in the enterprise secrets vault with automated rotation ≤ 60 days unless certificate-based authentication is used.
""",
)

write(
    "adventureworks-itgc-fy2025/policies/backup-and-recovery.md",
    """
# Backup and Disaster Recovery Standard

**Standard ID:** AW-STD-BUR-2025  
**Effective:** 1 January 2025 · **Owner:** IT Operations

## Backup schedules

| System | Backup type | Frequency | Retention |
|--------|-------------|-----------|-----------|
| E-commerce database (prod) | **Full** | **Daily** | 35 days |
| E-commerce database (prod) | Transaction log | Every 15 minutes | 7 days |
| ERP database | Full | Daily | 35 days |
| ERP database | Differential | Every 6 hours | 14 days |
| File shares | Incremental | Daily | 30 days |
| Domain controllers | System state | Daily | 14 days |

## Recovery objectives — online storefront

| Objective | Target |
|-----------|--------|
| **RTO** (Recovery Time Objective) | **4 hours** |
| RPO (Recovery Point Objective) | 15 minutes |

ERP financial close systems: RTO 24 hours; RPO 6 hours.

## Testing

- Restore tests quarterly for e-commerce DB (evidence in operations/restore-test-q1.md).
- Full DR tabletop annually; technical failover exercise at least once per year for storefront.

## Offsite / immutability

Daily full backups replicated to a secondary region with immutability lock (object lock / vault) for 35 days to mitigate ransomware.
""",
)

write(
    "adventureworks-itgc-fy2025/access/user-access-review-q1.md",
    """
# User Access Review — Q1 FY2025

**Document ID:** AW-UAR-2025-Q1  
**Review period:** 1 January – 31 March 2025  
**Certification due:** 15 April 2025  
**Completed:** 12 April 2025

## Scope

| Application | Owner | Accounts reviewed | Changes requested |
|-------------|-------|-------------------|-------------------|
| Azure AD / Entra ID (privileged roles) | IT Security | 37 privileged | 3 removals |
| E-commerce admin console | Digital Ops | 22 | 1 removal, 2 role reductions |
| ERP (finance modules) | Controller | 48 | 4 removals |
| ERP (manufacturing) | Plant IT | 61 | 2 removals |
| Data warehouse | Analytics Lead | 19 | 0 |

## Results

All application owners certified completeness. Removals completed by 20 April 2025 (within 30-day remediation SLA). No SOD conflicts remained open after remediation.

## Evidence

Certification emails and before/after role extracts archived in GRC tool (export not included in sample tree).
""",
)

write(
    "adventureworks-itgc-fy2025/access/privileged-access-inventory.md",
    """
# Privileged Access Inventory — Q1 FY2025 Snapshot

**Document ID:** AW-PRIV-INV-2025-Q1  
**Snapshot date:** 31 March 2025  
**Prepared by:** IT Security

## Summary

Total privileged accounts in scope for Q1 UAR: **37**.

| Platform | Privileged count | Notes |
|----------|------------------|-------|
| Entra ID (Global Admin, Privileged Role Admin, etc.) | 8 | Includes 2 break-glass |
| Azure subscription Owners | 6 | Prod subscriptions only |
| E-commerce prod admin | 5 | |
| ERP BASIS / admin | 7 | |
| Secrets vault admins | 4 | |
| Network / firewall admins | 4 | |
| SIEM admins | 3 | |
| **Total** | **37** | |

## Break-glass accounts

Two Entra break-glass accounts: hardware-token MFA, excluded from conditional access policies that could lock out admins, passwords vaulted, sign-in alerts to CISO distribution list. Q1 check-outs: **0**.

## Findings

Three accounts removed during UAR (departed contractors with lingering Azure Owner roles). No shared privileged passwords identified.
""",
)

write(
    "adventureworks-itgc-fy2025/access/joiner-leaver-sample.md",
    """
# Joiner / Leaver Control Test — Sample Q2 FY2025

**Document ID:** AW-TEST-JL-2025-Q2  
**Control:** Access revoked within 24 hours of HR termination effective time  
**Sample size:** 15 leavers

| Result | Count |
|--------|------:|
| Revoked ≤ 24 hours | 14 |
| Revoked > 24 hours | 1 |

## Exception

Contractor C-2241 terminated 3 Jun 2025 17:00; VPN revoked 3 Jun 17:20 but e-commerce admin account revoked 5 Jun 09:10 (**40.2 hours**). Root cause: HR ticket missing application checklist flag. Compensating: VPN/MFA cut off prevented remote use; no logons after termination.

Deficiency rating: Control deficiency (not significant) — see testing/itgc-deficiency-summary.md.
""",
)

write(
    "adventureworks-itgc-fy2025/change/change-management-procedure.md",
    """
# Change Management Procedure

**Document ID:** AW-CHG-PROC-2025  
**Systems in scope:** E-commerce platform, ERP, identity services

## Change categories

| Category | Definition | Approval |
|----------|------------|----------|
| Standard | Pre-approved low-risk (e.g., content deploy via CI) | Automated pipeline gates |
| Normal | Routine application / infra change | Peer review + CAB |
| Emergency | Sev-1 fix / active incident | On-call lead + retrospective CAB ≤ 48 hours |

## Pipeline controls

- Production deploys require green CI (unit + integration smoke).
- Separate prod service principal; developers lack direct prod write on e-commerce cluster.
- Infrastructure-as-code changes reviewed via pull request (min 1 approver outside author).

## Audit evidence

CAB minutes retained 3 years. Ticket fields mandatory: risk, test plan, back-out, window.
""",
)

write(
    "adventureworks-itgc-fy2025/change/cab-minutes-2025-03.md",
    """
# Change Advisory Board Minutes — 18 March 2025

**Document ID:** AW-CAB-2025-03-18  
**Attendees:** IT Ops Lead (chair), E-commerce Eng Manager, ERP BA, IT Security, Release Engineer

## Changes approved

| Change ID | Summary | Window | Risk |
|-----------|---------|--------|------|
| CHG-1042 | Storefront payment SDK patch | 20 Mar 01:00–03:00 PT | Medium |
| CHG-1048 | ERP tax config update (WA rate) | 21 Mar 22:00–22:30 PT | Low |
| CHG-1051 | SIEM parser update | 19 Mar daytime | Low |

## Changes deferred

- CHG-1049 (warehouse Wi-Fi controller upgrade) — deferred pending OT change freeze during spring production ramp.

## Emergency changes since prior CAB

None.
""",
)

write(
    "adventureworks-itgc-fy2025/operations/incident-response-log.md",
    """
# Security & Priority Incident Log — H1 FY2025

**Document ID:** AW-IR-LOG-2025-H1  
**Period:** 1 January 2025 – 30 June 2025

## Severity definitions (abridged)

- **Sev-1:** Customer-facing outage or confirmed data breach.
- **Sev-2:** Major degradation or security event with potential data exposure under investigation.
- **Sev-3:** Limited impact / suspicious activity contained.

## Sev-1 incidents

**Two (2)** Sev-1 incidents occurred in Q1–Q2 FY2025:

| ID | Date | Summary | Duration | Root cause | Data impact |
|----|------|---------|----------|------------|-------------|
| INC-2025-014 | 22 Feb 2025 | Storefront checkout outage (payment gateway timeout cascade) | 1h 40m | Misconfigured retry budget after vendor API change | None (availability only) |
| INC-2025-061 | 9 May 2025 | Regional CDN mis-routing — product pages 5xx for EU users | 3h 10m | Config push without canary | None |

RTO target for storefront is 4 hours; both Sev-1 events restored within RTO.

## Sev-2 summary

Seven Sev-2 incidents (3 security investigations, 4 availability). Security investigations closed with no confirmed unauthorised access to Restricted data.

## Lessons learned

INC-2025-014 drove change CHG-1042 (payment SDK patch) and added synthetic checkout canaries in EU and US.
""",
)

write(
    "adventureworks-itgc-fy2025/operations/restore-test-q1.md",
    """
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
""",
)

write(
    "adventureworks-itgc-fy2025/operations/vulnerability-management.md",
    """
# Vulnerability Management Summary — Q2 FY2025

**Document ID:** AW-VM-2025-Q2

| Severity | Open at quarter start | Opened | Closed | Open at quarter end | SLA breaches |
|----------|----------------------:|-------:|-------:|--------------------:|-------------:|
| Critical | 2 | 5 | 6 | 1 | 0 |
| High | 14 | 22 | 20 | 16 | 1 |
| Medium | 63 | 40 | 35 | 68 | n/a |

## SLA breach detail

One High vulnerability on an internal reporting jump host exceeded 30-day patch SLA by 6 days (change freeze). Compensating firewall restriction applied on day 2; patched 6 Jul 2025. Logged as operational exception EX-2025-19.
""",
)

write(
    "adventureworks-itgc-fy2025/vendors/cloud-provider-soc-bridge-letter.md",
    """
# SOC Bridge Letter — Cloud Provider (fictional)

**Document ID:** AW-VND-SOC-BRIDGE-2025-H1  
**To:** Adventure Works Cycles — Management & Auditors  
**From:** Northwind Cloud Services Trust Team *(fictional provider name for sample isolation)*  
**Date:** 15 July 2025  
**Subject:** Bridge letter covering period after SOC 2 Type II report

## Coverage

Our SOC 2 Type II report for the period 1 July 2024 through 31 December 2024 was issued 28 February 2025. This bridge letter addresses the subsequent period **1 January 2025 through 30 June 2025**.

## Management assertion

We confirm that, to our knowledge, there were no material changes to the system description or control environment that would significantly affect the criteria addressed in the SOC 2 Type II report during **1 January 2025 through 30 June 2025**. No material control failures were identified that would require disclosure to user entities beyond routine patching and capacity changes.

## Use

This letter is intended solely for Adventure Works Cycles management and its independent auditors for the Adventure Works ITGC FY2025 engagement. It does not replace a SOC report for periods after 30 June 2025.

**Yes — the bridge letter covers through 30 June 2025.**
""",
)

write(
    "adventureworks-itgc-fy2025/vendors/third-party-risk-register.md",
    """
# Third-Party Risk Register (excerpt) — FY2025

**Document ID:** AW-VND-RISK-2025

| Vendor | Service | Data class | Inherent risk | Residual risk | Last assessment | SOC / cert |
|--------|---------|------------|---------------|---------------|-----------------|------------|
| Northwind Cloud Services | IaaS / PaaS | Confidential | High | Medium | May 2025 | SOC 2 + bridge letter through 30 Jun 2025 |
| PayGate Example | Payment processing | Restricted | High | Medium | Apr 2025 | PCI DSS AoC |
| MailShip Co. | Transactional email | Internal | Medium | Low | Feb 2025 | SOC 2 |
| TempHelp Staffing | Contractors | Internal | Medium | Medium | Jan 2025 | Security questionnaire |

Critical vendors reviewed at least annually; High residual risk vendors require CISO acceptance.
""",
)

write(
    "adventureworks-itgc-fy2025/testing/itgc-test-plan.md",
    """
# ITGC Test Plan — FY2025

**Document ID:** AW-TEST-PLAN-2025  
**Engagement:** adventureworks-itgc-fy2025

## Domains and extents

| Domain | Key controls | Interim OE sample approach |
|--------|--------------|----------------------------|
| Access provisioning / deprovisioning | JL-01, JL-02 | 15 joiners / 15 leavers |
| Privileged access | PRIV-01, PRIV-02 | Full population UAR evidence + 10 break-glass reviews |
| Change management | CHG-01, CHG-02 | 25 normal changes + all emergency changes |
| Backup & recovery | BUR-01, BUR-02 | Inspect daily job success logs 2 months + 1 restore test |
| Logging & monitoring | MON-01 | SIEM use-case operating evidence quarterly |

## Reliance strategy

External auditors may reperform a subset; management testing documented for reliance discussion in August 2025 coordination meeting.
""",
)

write(
    "adventureworks-itgc-fy2025/testing/itgc-deficiency-summary.md",
    """
# ITGC Deficiency Summary — H1 FY2025

**Document ID:** AW-DEF-SUM-2025-H1

| ID | Control | Issue | Rating | Remediation |
|----|---------|-------|--------|-------------|
| DEF-AW-01 | JL-02 | One contractor e-com admin revoked in 40.2 hours vs 24-hour policy | Control deficiency | HR checklist mandatory field shipped 20 Jun 2025; retest in Q3 |
| DEF-AW-02 | VULN-01 | One High patch SLA miss (6 days) with compensating control | Observation | None beyond monitoring |

No significant deficiencies or material weaknesses identified in ITGCs for H1 based on management evaluation.
""",
)

# Top-level index
write(
    "README.md",
    """
# AI-generated sample engagements

Fictional audit document trees for demos and offline tests. **Not real client data.**

| Engagement ID | Name | Focus |
|---------------|------|-------|
| `northwind-fy2025` | Northwind FY2025 | External financial audit working papers (wholesale distribution) |
| `fabrikam-sox-fy2025` | Fabrikam SOX FY2025 | SOX 404 / ICFR (manufacturing) |
| `adventureworks-itgc-fy2025` | Adventure Works ITGC FY2025 | ITGC & cybersecurity assurance (e-commerce + manufacturing) |

Seed all engagements (requires running API stack):

```bash
just seed
```

Each engagement folder has its own README with answerable and insufficient-evidence example questions.
""",
)

print("done")
