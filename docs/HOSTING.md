# Hosting CashPilot

CashPilot is prepared for Streamlit Community Cloud and a dedicated Neon Free database. The repository is public; the application has not been deployed by this implementation.

## Prepared database

Owner organization: Enamul FDE (Free). Dedicated project **CashPilot**, project ID `restless-dew-06838632`, AWS Frankfurt `aws-eu-central-1`, PostgreSQL 17, database `cashpilot`, role `cashpilot_owner`. Production branch `br-solitary-firefly-b9gx7v3t`; isolated `migration-verification` branch `br-rough-boat-b9hr8glb`. Both were initialized using the v1 migration; visitor isolation and separate-process history recovery passed on the isolated branch before production initialization.

No other app shares this database. Free-managed scale-to-zero is enabled; do not run keepalive polling. The provisioned compute is 0.25 CU. Pricing checked 17 November 2026: Neon Free is $0, advertises 100 CU-hours/month/project, 1 GB storage/project and 5 GB public transfer/project, with scale-to-zero after five inactive minutes. Free allowances and availability can change: inspect the project's current Usage/Billing page before deploying or increasing use. Free resources have cold starts and finite compute/storage/transfer; exceeding free allowances may pause service. Do not enable paid upgrades automatically. Streamlit Community Cloud may sleep idle apps and has shared resource limits; restart-safe writes belong in Neon, not the app filesystem. This demo has no paid model calls.

## Deploy manually

1. Sign into Streamlit Community Cloud with Enamul's GitHub account. Create an app from `Enamul22/CashPilot-CorporateCashFlow`, branch `main`, entry file `app.py`, Python 3.12.
2. Open Advanced settings → Secrets. Copy the **entire private local `.streamlit/secrets.toml`** into that editor. `config.toml` is appearance configuration; `secrets.toml.example` is only a placeholder template. Do not paste a direct migration URL into browser assets or Git.
3. The required shape is:

```toml
[cashpilot]
mode = "hosted"
database_url = "YOUR_PRIVATE_NEON_POOLED_POSTGRESQL_URL"
```

4. Deploy, then create a workspace, save a review and scenario, bookmark its complete private URL, refresh, and restart the app. Verify history returns from the same bookmark. Test a second independent workspace. Never publish a capability URL in screenshots.

The private `.env` and `.streamlit/secrets.toml` were configured locally and are ignored by Git. The `.env` includes the direct URL for owner-run migrations; the hosted app needs only its pooled URL. Preserve TLS verification. With absent configuration the app remains read-only; an unreachable configured database displays an error rather than saving into ephemeral storage.

## Safe data updates

Reproduce artifacts into a separate output directory; review model selection, tests and fingerprints. Create or reuse an isolated Neon development branch. Apply `cashpilot migrate --env .env.neon-dev` there and run the PostgreSQL integration test with `CASHPILOT_TEST_DATABASE_URL` pointing only to that branch. After successful verification, initialize/register on production using `cashpilot migrate --env .env`. Publish the matching artifact bundle and restart Streamlit. Existing forecast IDs must never be overwritten with changed predictions. Review events retain original IDs and stored scenario paths.

The supported PostgreSQL integration command is `pytest tests/test_postgres.py -q` with the isolated test URL supplied privately through the environment. Default CI has no database credentials and skips that single integration test; all remaining tests and the smoke pipeline run offline.

A local developer may explicitly choose `CASHPILOT_MODE=local`; this creates SQLite for development only. Never select local mode in Community Cloud if persistent history is expected. Workspace capability recovery is bookmark-based; there is no email/password recovery or cross-browser identity service.

Official deployment guide: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app
Neon plans: https://neon.com/pricing
