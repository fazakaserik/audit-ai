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
