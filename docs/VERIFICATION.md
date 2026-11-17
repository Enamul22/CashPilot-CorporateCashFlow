# Verification evidence

Verified locally on 17 November 2026 against the committed full synthetic artifacts.

- **36 offline tests passed**, one explicitly configured PostgreSQL test skipped in the default run. Tests cover full integer ledger reconciliation and zero-cash days; currency corruption; point-in-time future perturbations; schedule revisions/cancellations/overdue items; residual matching and amount/timing differences; alert boundaries; scenario arithmetic and immutability; idempotent concurrent saves; workspace isolation/reset fencing; forecast-origin review status; read-only preview and invalid data.
- **One additional real PostgreSQL test passed** on the dedicated Neon `migration-verification` branch. It saves both review and scenario, recovers both in a separate Python interpreter, verifies a second workspace sees neither, and resets the first workspace only. The production migration ran after this test passed.
- Ruff and Python bytecode compilation passed. The bounded offline smoke pipeline generated, validated, fitted, selected and evaluated ten businesses successfully. Its smaller sample selected the baseline; it does not overwrite the full 100-business model selection.
- The full pipeline completed in approximately 308 seconds; source counts, model parameters, all evaluation rows and fingerprints are recorded in `evaluation/`.
- Browser: desktop overview and account outlook inspected. Private Neon workspace created; Monitoring review and named 14-day delayed-receipt scenario saved; browser refresh recovered both. The original minimum remains SEK 925.43; delaying the selected receipt beyond the horizon produces SEK −34,464.27 with first negative close 2 November 2026. Review does not remove the Below buffer alert.
- All four distinct demonstration accounts are asserted from computed paths in automated tests, rather than screenshot-only checks. Saved-history recovery also passes the Streamlit app test after constructing a new app session.

Phone browser inspection, a second independent browser workspace and final GitHub CI inspection are recorded below when completed. Docker configuration is supplied; a Docker engine is not installed on the development machine, so an image build has not been claimed. A clean dependency installation verifies the pinned environment separately.

No public Streamlit deployment was performed. Public hosting, its browser-specific behavior and a production-host restart must be verified after the owner deploys using `docs/HOSTING.md`.
