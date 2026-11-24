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
