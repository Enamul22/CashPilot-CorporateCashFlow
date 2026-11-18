# Sources and licences

All companies, transactions, expected movements and screenshots are generated for this demonstration. No real bank or customer data is used, and forecasting requires no model API. Source code and generated data are MIT licensed in this repository. Third-party dependencies retain their own licences.

Implementation references:

- scikit-learn HistGradientBoostingRegressor API: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html — Poisson loss, parameters and disabling internal random early stopping. BSD-3-Clause package.
- Streamlit deployment: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app — repository, entry point and secrets setup. Apache-2.0 package.
- Plotly Python charts: https://plotly.com/python/line-charts/ — actual and forecast traces. MIT package.
- SQLAlchemy transaction/metadata APIs: https://docs.sqlalchemy.org/en/20/core/connections.html — persistence. MIT package.
- Psycopg connection parameters: https://www.psycopg.org/psycopg3/docs/api/connections.html — verified TLS connections. LGPL-3.0 package.
- Neon pricing and plan limits: https://neon.com/pricing — free account scope; current usage is authoritative in the owner dashboard.

Direct and transitive versions are frozen in `requirements.lock`. Python 3.12 is used for CI and Docker. Screenshot files are actual browser captures of the application, not design mockups.
