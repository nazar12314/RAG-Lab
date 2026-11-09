# Identity and authentication architecture

_Owner: Identity Team._

The Auth Service (our IdP) is run by the Identity Team, which also owns the Accounts Service.

## Sessions and tokens

The Auth Service issues a short-lived JWT and a refresh token at login. Session state is stored in the session shards of Shared Redis; if Redis loses keys, users are logged out. Tokens are signed with a key that is rotated manually every quarter.

## Who calls auth

- The API Gateway validates tokens with the Auth Service for every authenticated request.
- The Checkout API re-validates the session on each checkout step.

## Profile data

At login the Auth Service reads profile flags from the Accounts Service; this call is soft and login continues with defaults if Accounts is slow. The Accounts Service stores profiles, saved addresses and privacy export requests in its own database.

## Operational notes

Token validation is on the hot path of every request, so any latency added there is multiplied across the platform.
