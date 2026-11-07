# Data Platform release notes - April 2026

Production changes shipped by Data Platform services in April 2026.

### etl loader v1.3.0 (release)
Deployed 2026-04-02 14:00 UTC by Ravi Menon.
- Nightly order export now includes shipping address fields
- Airflow DAG split into extract and load tasks

### dw loader v1.3.1 (hotfix)
Deployed 2026-04-29 10:10 UTC by Ravi Menon.
- Column mapping updated for orders.shipping_address
- Loader now fails loudly on unknown source columns

