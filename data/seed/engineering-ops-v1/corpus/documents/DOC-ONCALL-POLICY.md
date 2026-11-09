# Incident severity and on-call policy

## Severity levels

| Level | Definition | Example |
| --- | --- | --- |
| SEV1 | Critical. Customers cannot buy, pay or log in at scale. | Checkout failing for more than 25% of attempts |
| SEV2 | Major. Significant customer impact or data correctness problem. | Wrong charges, large-scale overselling |
| SEV3 | Minor. Limited customer impact with a workaround. | Slow profile updates |
| SEV4 | Low. Cosmetic or internal-only impact. | Stale analytics dashboards |

SEV1 and SEV2 incidents are called **severe** incidents and always require a written postmortem within five working days. SEV3 and SEV4 incidents are closed with a short resolution note on the incident ticket.

## Roles

- **Incident commander** - coordinates, does not debug.
- **Communications lead** - status page and Support updates for SEV1/SEV2.
- **Subject matter experts** - the on-call engineers of the affected services.

## Change freeze

No production releases on Fridays after 15:00 UTC or during declared SEV1 incidents, except rollbacks and fixes for the incident itself.

## Postmortems

Postmortems are blameless. The root cause section must name the verified cause; early hypotheses from the incident channel belong in the timeline, not in the root cause.
