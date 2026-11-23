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
