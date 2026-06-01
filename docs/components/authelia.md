# Authelia

OpenID Connect identity provider for Open WebUI SSO and optional MFA. Uses Valkey for session storage and either SQLite (lab) or PostgreSQL (prod) as the persistent backend.

- **Tier**: T0 (safety / integrity)
- **Boundary**: `authentication`
- **Control refs**: [CTL-002](../governance/CONTROLS.md#controls-ctl), [POL-001](../governance/CONTROLS.md#policies-pol)
- **Default**: opt-in (`authelia.enabled=false`)
- **Upstream**: <https://www.authelia.com/> · [docs](https://www.authelia.com/configuration/)
- **Default image**: `ghcr.io/authelia/authelia` (see `values.yaml` for pinned tag)
- **Chart path**: [`templates/authelia/`](../../templates/authelia/)

## Key `values.yaml` keys

| Key | Purpose |
|-----|---------|
| `authelia.enabled` | Toggle the component |
| `authelia.domain` | Session cookie domain (must cover both Authelia and Open WebUI hosts) |
| `authelia.defaultPolicy` | `one_factor` or `two_factor` (MFA) |
| `authelia.storage` | `sqlite` (lab) or `postgres` (prod — reuses the shared `postgres` component) |
| `authelia.oidc.{clientId,issuerUrl}` | OIDC integration with Open WebUI |
| `authelia.ingress.*` | Ingress / Gateway API configuration |
| `authelia.users` | Optional inline file-based user list |

## Secrets

All sensitive Authelia values (JWT secret, session secret, storage encryption key, OIDC client secret) are auto-generated into `authelia-secret` on first install with `helm.sh/resource-policy: keep`.

## Production guidance

- Set `authelia.defaultPolicy: two_factor` and configure WebAuthn or TOTP
- Use PostgreSQL storage (`authelia.storage: postgres`) so registrations survive pod restarts
- Front with an ingress controller that supports OAuth forward-auth if you want to gate other UIs

## Related HOWTO sections

- [§12 Authentication with Authelia (SSO/OIDC)](../../HOWTO.md#12-authentication-with-authelia-sso--oidc)
