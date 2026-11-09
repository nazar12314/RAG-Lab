# INC-116: Event consumers lagging after broker upgrade

Severity: SEV3 | Status: Resolved | Primary service: Event Bus
Opened: 2026-07-08 07:00 UTC (impact started 06:30 UTC)
Affected services: Event Bus (primary), Warehouse Loader (downstream)

## Description
Consumers of the event bus fell hours behind after the Kafka upgrade.

## Impact
Analytics data was delayed by up to five hours. Order notification webhooks were not affected because notifications still used the Order Service webhook at that time.

## Detection
Consumer lag alert for the warehouse-loader group.

## Initial notes from the incident channel
Broker disk performance.

## Resolution note
Cause: The switch to cooperative rebalancing in the event-bus kafka-3.7.1 upgrade combined with a too-short session timeout caused a rebalance storm; consumers kept losing partition assignments before committing offsets.
Consumer session timeouts were raised from 10 to 45 seconds and lag recovered.
Resolved: 2026-07-08 12:00 UTC
