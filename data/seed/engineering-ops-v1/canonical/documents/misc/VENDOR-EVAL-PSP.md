---
id: DOC-VENDOR-EVAL-PSP
title: Secondary card processor evaluation (draft)
doc_type: report
created_at: "2026-07-14T10:00:00Z"
author: Tomasz Wierzbicki
services: [psp-adapter, payments-api]
---
# Secondary card processor evaluation (draft)

**Status:** draft - no decision yet.

## Why

The June PayNova outage showed that a single card processor is a single point of failure for checkout. This document compares options for a secondary processor that the PSP Adapter could fail over to.

## Shortlist

| Criterion | Vendor A | Vendor B | Vendor C |
| --- | --- | --- | --- |
| EU acquiring | yes | yes | partial |
| Network tokens | yes | no | yes |
| Integration effort | 6 weeks | 4 weeks | 8 weeks |

Vendor names are withheld until procurement signs NDAs.

## Next steps

- Commercial terms from all three vendors.
- Decision meeting to be scheduled; target Q4.
