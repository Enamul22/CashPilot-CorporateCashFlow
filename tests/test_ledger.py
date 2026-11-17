import pytest

from cashpilot.config import Settings
from cashpilot.data import validate_ledger


def test_full_ledger_reconciles_exactly_and_has_zero_days(sources):
    result = validate_ledger(
        sources.accounts, sources.transactions, sources.balances, sources.versions
    )
    assert result["accounts"] == 100 and result["ledger"] == "integer-exact"
    assert ((sources.balances.inflow_minor == 0) & (sources.balances.outflow_minor == 0)).any()
    assert sources.balances.groupby("account_id").size().min() > 1000


def test_currency_corruption_is_rejected(sources):
    tx = sources.transactions.head(1).copy()
    tx.loc[:, "currency"] = "WRONG"
    with pytest.raises(ValueError, match="Currency"):
        validate_ledger(sources.accounts, tx, sources.balances, sources.versions)


def test_no_temporary_hosted_fallback():
    assert Settings().storage_url == ""
    with pytest.raises(ValueError):
        _ = Settings(database_url="sqlite:///temp.db").storage_url
