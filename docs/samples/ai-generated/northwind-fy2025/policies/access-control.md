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
