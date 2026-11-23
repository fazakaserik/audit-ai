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
