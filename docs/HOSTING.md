# Hosting CashPilot

CashPilot supports Streamlit Community Cloud with Neon PostgreSQL for persistent reviews and scenarios. Deployment status: ready for Streamlit Community Cloud.

## Set up Neon

1. Create a dedicated Neon Free project and a database for CashPilot. Choose a region close to the application host. PostgreSQL 17 with 0.25 CU compute is a compatible starting configuration.
2. Create a development branch to verify the schema before initializing production. Store its direct connection URL privately in `.env.neon-dev` as `CASHPILOT_DATABASE_URL_DIRECT`, with `CASHPILOT_MODE=hosted`.
3. Run `cashpilot migrate --env .env.neon-dev`. This initializes schema v1 and registers the bundled immutable forecasts.
4. Set `CASHPILOT_TEST_DATABASE_URL` privately to the development branch's direct URL and run `pytest tests/test_postgres.py -q`. This checks saved-history recovery and workspace isolation. Use an isolated test branch for this test.
5. Copy `.env.example` to `.env`. Set `CASHPILOT_MODE=hosted`, `CASHPILOT_DATABASE_URL` to the production **pooled** URL, and `CASHPILOT_DATABASE_URL_DIRECT` to the production **direct** URL. Run `cashpilot migrate --env .env` after the development-branch checks pass.

Application connections use the pooled URL; migrations use the direct URL. TLS certificate verification is enabled. Connections close after each operation, with no keepalive polling. Keep `.env`, `.env.neon-dev` and `.streamlit/secrets.toml` private; these files are ignored by Git.

## Deploy to Streamlit Community Cloud

1. Sign into Streamlit Community Cloud with an account that has access to the repository. Create an app from `Enamul22/CashPilot-CorporateCashFlow`, branch `main`, entry file `app.py`, Python 3.12.
2. Open **Advanced settings → Secrets**. Copy the structure of `.streamlit/secrets.toml.example` into the editor and replace the placeholder with the production pooled connection URL. If you have configured a private local `.streamlit/secrets.toml`, you can copy its complete contents instead. `config.toml` controls appearance; it is not the secrets file.
3. Use this configuration:

```toml
[cashpilot]
mode = "hosted"
database_url = "YOUR_PRIVATE_NEON_POOLED_POSTGRESQL_URL"
```

4. Deploy, create a workspace, save a review and scenario, and bookmark its complete private URL. Refresh and restart the app, then verify history returns from the same bookmark. Test a second independent workspace to confirm isolation.

The hosted app needs only the pooled URL; the direct migration URL remains in the private migration environment. Keep connection strings out of Git and browser assets. Workspace return URLs grant access to their history and should not appear in public screenshots.

With no database configuration, the app offers read-only browsing and scenario previews. An unreachable configured database displays an error rather than saving to temporary storage. SQLite is available only through explicit local development mode (`CASHPILOT_MODE=local`); hosted persistence requires PostgreSQL. Workspace recovery uses a bookmarked return URL, with no email/password recovery or shared cross-browser identity.

## Free-tier limits

Pricing checked 17 November 2026: Neon Free is $0 and advertises 100 CU-hours/month/project, 1 GB storage/project and 5 GB public transfer/project, with scale-to-zero after five inactive minutes. Allowances may change; check the current pricing and project Usage/Billing pages before sustained use. Cold starts and finite compute, storage and transfer allowances apply; exhausted allowances may interrupt availability.

Streamlit Community Cloud may sleep idle apps and has shared resource limits. Persistent writes belong in Neon, not the app filesystem. CashPilot requires no paid model calls.

## Safe data updates

Reproduce artifacts into a separate output directory and review model selection, tests and fingerprints. Verify migrations and forecast registration on an isolated Neon development branch before applying them to production. Use `cashpilot migrate --env .env.neon-dev` for development and `cashpilot migrate --env .env` for production, with each file pointing to the corresponding branch.

Publish the matching artifact bundle and restart Streamlit. Existing forecast IDs must not be overwritten with changed predictions. Review events retain their original forecast IDs and stored scenario paths.

Default CI runs offline tests and a bounded pipeline smoke test. It skips the PostgreSQL integration test unless `CASHPILOT_TEST_DATABASE_URL` is supplied privately for an isolated branch.

- [Streamlit deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app)
- [Neon pricing and plan limits](https://neon.com/pricing)
