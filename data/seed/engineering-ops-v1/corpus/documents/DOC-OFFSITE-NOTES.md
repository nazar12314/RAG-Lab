# Engineering offsite notes - September 2026

## Logistics

The hotel pool was closed for maintenance, so the Thursday social moved to the rooftop. Shuttle buses left from the main entrance at 08:15. Thanks to everyone who joined the carpool from the office.

## Themes from the retro session

- "Too many incidents start with a release on a busy morning." Proposal: no releases of tier 1 services between 08:00 and 11:00 UTC on weekdays. Not agreed; Payments and Checkout will trial it.
- Shared database ownership is unclear. Platform SRE owns the cluster, but nobody owns query review.
- People want a single place to see which deployments happened around an incident.

## Hack day ideas

- A bot that posts the last five deployments into every new incident channel.
- Dependency map generated from tracing data.
- Talent pool for internal mobility - HR to follow up.

## Action items

- Hannah to draft a proposal for statement timeouts on the shared database.
- Kenji to present event bus capacity numbers at the next ops review.
