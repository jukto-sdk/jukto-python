# Security policy

## Private reporting

Use GitHub's private vulnerability reporting control if enabled for this repository.
If it is unavailable, contact the maintainer at mahdibuilds.hq@gmail.com. Do not
file a public issue with working exploit credentials, tokens or personal data.
Include the affected version/commit, a minimal offline reproduction, impact and
sanitized evidence. Send secrets only through an agreed secure channel if they are
actually necessary; rotate exposed credentials rather than sharing them further.

## Scope and support

Report credential leakage, unsafe defaults, logging exposure, resource ownership
or unsafe replay in Jukto. Include the provider and operation without identifying
customers. Third-party account breaches and provider outages also need escalation
to that provider. Security fixes target the current maintained code/release; older
versions are not promised a backport. Coordinate disclosure with the maintainer.

HTTPS with verified TLS and no redirects is the default. Legacy HTTP opt-in sends
credentials/content unencrypted. Raw response access is intentionally sensitive;
application logging and third-party HTTP loggers are outside the SDK's metadata-only
logging boundary. A timeout after a side effect may require reconciliation.

Tests must remain offline and use synthetic data. Live probing, real transactions
and production credentials are not part of a routine security reproduction.
