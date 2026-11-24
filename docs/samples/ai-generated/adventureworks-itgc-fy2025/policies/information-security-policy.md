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
