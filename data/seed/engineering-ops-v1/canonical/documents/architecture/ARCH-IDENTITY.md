---
id: DOC-ARCH-IDENTITY
title: Identity and authentication architecture
doc_type: architecture
created_at: "2026-04-05T12:00:00Z"
author: Amara Okafor
services: [auth-service, accounts-service, shared-redis, api-gateway, checkout-api]
---
# Identity and authentication architecture

_Owner: Identity Team._

[[F-OWNER-auth-service|The Auth Service (our IdP) is run by the Identity Team]], [[F-OWNER-accounts-service|which also owns the Accounts Service]].

## Sessions and tokens

The Auth Service issues a short-lived JWT and a refresh token at login. [[F-LINK-22|Session state is stored in the session shards of Shared Redis]]; if Redis loses keys, users are logged out. Tokens are signed with a key that is rotated manually every quarter.

## Who calls auth

- [[F-LINK-01|The API Gateway validates tokens with the Auth Service for every authenticated request.]]
- [[F-LINK-09|The Checkout API re-validates the session on each checkout step.]]

## Profile data

[[F-LINK-23|At login the Auth Service reads profile flags from the Accounts Service]]; this call is soft and login continues with defaults if Accounts is slow. The Accounts Service stores profiles, saved addresses and privacy export requests in its own database.

## Operational notes

Token validation is on the hot path of every request, so any latency added there is multiplied across the platform.
