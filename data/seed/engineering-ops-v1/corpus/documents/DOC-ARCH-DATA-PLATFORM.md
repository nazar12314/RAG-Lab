# Data platform overview

_Owner: Data Platform Team._

The Event Bus (our Kafka cluster) is operated by the Data Platform Team, which also owns the Warehouse Loader.

## Event Bus

Three brokers, replication factor 3, seven-day retention on all topics. The Order Service publishes order lifecycle events to the topic order-events. More producers are expected after the planned migration of notifications and inventory.

## Warehouse Loader

The Warehouse Loader (dw loader / nightly ETL) feeds the analytics data warehouse - not to be confused with Warehouse Sync, which handles physical warehouse stock.

- It consumes events from the Event Bus for near-real-time tables.
- A nightly export reads order tables from the Orders DB; this export must always use the read replica.

## Ownership boundaries

Schema changes in the Orders DB must be announced to Data Platform at least one week in advance because the export queries depend on column names.
