# Runbook: Fraud Scoring Service (risk-scoring)

Owner: Payments Team, ML engineers on the risk rotation.

## Callers

Since 1 June the Payments API calls fraud scoring before each authorization. The previous direct call from checkout has been removed.

## Decline rate spike

1. Split declines by reason: "high risk" vs "score unavailable".
2. "score unavailable" means the caller timed out - check fraud p95 latency against the caller's timeout.
3. "high risk" spikes after a model or threshold change: roll back the model release.

## Signals

Account age and history are fetched from the Accounts Service. If Accounts is slow, scores are computed without these signals and become less accurate.
