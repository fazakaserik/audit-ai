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
