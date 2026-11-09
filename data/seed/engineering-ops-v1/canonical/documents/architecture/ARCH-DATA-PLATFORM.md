---
id: DOC-ARCH-DATA-PLATFORM
title: Data platform overview
doc_type: architecture
created_at: "2026-04-18T14:00:00Z"
author: Kenji Watanabe
services: [event-bus, warehouse-loader, orders-db, order-service]
---
# Data platform overview

_Owner: Data Platform Team._

[[F-OWNER-event-bus|The Event Bus (our Kafka cluster) is operated by the Data Platform Team]], [[F-OWNER-warehouse-loader|which also owns the Warehouse Loader]].

## Event Bus

Three brokers, replication factor 3, seven-day retention on all topics. [[F-LINK-18|The Order Service publishes order lifecycle events to the topic order-events.]] More producers are expected after the planned migration of notifications and inventory.

## Warehouse Loader

The Warehouse Loader (dw loader / nightly ETL) feeds the analytics data warehouse - not to be confused with Warehouse Sync, which handles physical warehouse stock.

- [[F-LINK-30|It consumes events from the Event Bus for near-real-time tables.]]
- [[F-LINK-31|A nightly export reads order tables from the Orders DB]]; this export must always use the read replica.

## Ownership boundaries

Schema changes in the Orders DB must be announced to Data Platform at least one week in advance because the export queries depend on column names.
