"""Point-in-time input boundary, exact ledger validation, and origin-relative labels."""

import hashlib
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd


def records(frame):
    """JSON-safe business records; missing values remain null rather than NaN/NA."""
    return frame.astype(object).where(pd.notna(frame), None).to_dict("records")


@dataclass(frozen=True)
class OriginView:
    account: dict
    origin: pd.Timestamp
    history: pd.DataFrame
    transactions: pd.DataFrame
    movements: pd.DataFrame
    fingerprint: str


def asof_schedule(versions, cutoff):
    cutoff = pd.Timestamp(cutoff).normalize()
    visible = versions[versions["known_day"] <= cutoff]
    return (
        visible.sort_values(["item_id", "version"]).drop_duplicates("item_id", keep="last").copy()
    )


def validate_ledger(accounts, txs, balances, versions):
    if accounts["id"].duplicated().any() or txs["id"].duplicated().any():
        raise ValueError("Duplicate account or transaction identifier")
    if (accounts["buffer_minor"] <= 0).any():
        raise ValueError("Buffers must be positive")
    registry = accounts.set_index("id")["currency"].to_dict()
    for table in [txs, balances, versions]:
        if not table["account_id"].isin(registry).all():
            raise ValueError("Unknown account reference")
        if any(
            registry[a] != c for a, c in zip(table["account_id"], table["currency"], strict=True)
        ):
            raise ValueError("Currency does not match the account")
    if txs[txs.item_id.notna()].item_id.duplicated().any():
        raise ValueError("This data model supports one booked settlement per schedule item")
    if not versions.status.isin(["Expected", "Cancelled", "Settled"]).all():
        raise ValueError("Unknown movement state")
    if versions.duplicated(["item_id", "version"]).any():
        raise ValueError("Duplicate movement version")
    if not txs[txs["item_id"].notna()]["item_id"].isin(versions["item_id"]).all():
        raise ValueError("Booked reference does not identify a schedule item")
    if not (txs["amount_minor"].map(type).isin([int, np.int64])).all():
        raise ValueError("Transactions require integer minor units")
    grouped = (
        txs.assign(
            inflow_minor=txs.amount_minor.clip(lower=0),
            outflow_minor=(-txs.amount_minor).clip(lower=0),
        )
        .groupby(["account_id", "available_date"])[["inflow_minor", "outflow_minor"]]
        .sum()
    )
    for account in accounts.to_dict("records"):
        ledger = balances[balances.account_id == account["id"]].sort_values("date")
        dates = pd.to_datetime(ledger.date)
        if dates.duplicated().any() or len(dates) != len(pd.date_range(dates.min(), dates.max())):
            raise ValueError("Daily balances must include zero-transaction days")
        previous = account["opening_minor"]
        for row in ledger.to_dict("records"):
            flow = (
                grouped.loc[(account["id"], row["date"])]
                if (account["id"], row["date"]) in grouped.index
                else {"inflow_minor": 0, "outflow_minor": 0}
            )
            if (
                row["opening_minor"] != previous
                or row["inflow_minor"] != flow["inflow_minor"]
                or row["outflow_minor"] != flow["outflow_minor"]
                or row["closing_minor"] != previous + row["inflow_minor"] - row["outflow_minor"]
            ):
                raise ValueError("Ledger does not reconcile exactly")
            previous = row["closing_minor"]
    if (
        pd.to_datetime(txs["known_at"], utc=True).dt.date
        < pd.to_datetime(txs["available_date"]).dt.date
    ).any():
        raise ValueError("Booked cash must not be visible before availability")
    for _, group in versions.groupby("item_id", sort=False):
        if not group.sort_values("version")["known_at"].is_monotonic_increasing:
            raise ValueError("Movement versions have inconsistent visibility order")
    return {
        "accounts": len(accounts),
        "transactions": len(txs),
        "daily_balances": len(balances),
        "movement_versions": len(versions),
        "ledger": "integer-exact",
    }


class Sources:
    """Owns the full simulator output. Only snapshot() crosses into feature construction."""

    def __init__(self, root):
        self.accounts = pd.read_parquet(root / "accounts.parquet")
        self.transactions = pd.read_parquet(root / "transactions.parquet")
        self.balances = pd.read_parquet(root / "balances.parquet")
        self.versions = pd.read_parquet(root / "movement_versions.parquet")
        self.transactions["day"] = pd.to_datetime(self.transactions.available_date)
        self.transactions["known_day"] = (
            pd.to_datetime(self.transactions.known_at, utc=True).dt.tz_localize(None).dt.normalize()
        )
        self.balances["day"] = pd.to_datetime(self.balances.date)
        self.balances["known_day"] = (
            pd.to_datetime(self.balances.known_at, utc=True).dt.tz_localize(None).dt.normalize()
        )
        self.versions["known_day"] = (
            pd.to_datetime(self.versions.known_at, utc=True).dt.tz_localize(None).dt.normalize()
        )
        self._accounts = self.accounts.set_index("id").to_dict("index")
        self._tx = {k: v for k, v in self.transactions.groupby("account_id", sort=False)}
        self._balance = {k: v for k, v in self.balances.groupby("account_id", sort=False)}
        self._versions = {k: v for k, v in self.versions.groupby("account_id", sort=False)}

    def snapshot(self, account_id, origin, invalid=None):
        origin = pd.Timestamp(origin).normalize()
        if account_id not in self._accounts:
            raise ValueError("Unknown account")
        account = {"id": account_id, **self._accounts[account_id]}
        history = self._balance[account_id]
        history = history[(history.day <= origin) & (history.known_day <= origin)].tail(56).copy()
        tx = self._tx[account_id]
        tx = tx[
            (tx.day <= origin)
            & (tx.known_day <= origin)
            & (tx.day >= origin - pd.Timedelta(days=55))
        ].copy()
        movements = asof_schedule(self._versions[account_id], origin)
        if invalid == "missing_balance":
            history = history[history.day != origin]
        if invalid == "currency_mismatch" and len(tx):
            tx.loc[tx.index[-1], "currency"] = "INVALID"
        if len(history) < 7 or history.iloc[-1]["day"] != origin:
            raise ValueError(
                "Closing balance at the cutoff is missing. Obtain a complete daily balance extract."
            )
        if len(history) != len(pd.date_range(history.day.min(), origin)):
            raise ValueError(
                "Daily history has gaps. Restore the missing dates, including zero-transaction days."
            )
        if any(
            table["currency"].ne(account["currency"]).any() for table in [history, tx, movements]
        ):
            raise ValueError(
                "A source currency differs from the account. Reconcile the source extract before forecasting."
            )
        expected_close = history.opening_minor + history.inflow_minor - history.outflow_minor
        if not expected_close.eq(history.closing_minor).all() or not np.array_equal(
            history.opening_minor.to_numpy()[1:], history.closing_minor.to_numpy()[:-1]
        ):
            raise ValueError(
                "Daily closing balances do not reconcile. Correct the balance extract."
            )
        cash = (
            tx.assign(
                inflow=tx.amount_minor.clip(lower=0), outflow=(-tx.amount_minor).clip(lower=0)
            )
            .groupby("day")[["inflow", "outflow"]]
            .sum()
            .reindex(history.day, fill_value=0)
        )
        if not np.array_equal(
            cash.inflow.to_numpy(), history.inflow_minor.to_numpy()
        ) or not np.array_equal(cash.outflow.to_numpy(), history.outflow_minor.to_numpy()):
            raise ValueError(
                "Visible transactions do not reconcile with daily flows. Obtain a complete extract."
            )
        if account["buffer_minor"] <= 0:
            raise ValueError("Configure a positive operating buffer")
        # Fingerprint only information visible at this origin, never future truth.
        serial = {
            "account": account,
            "origin": str(origin.date()),
            "history": records(history.drop(columns=["day", "known_day"])),
            "transactions": records(tx.drop(columns=["day", "known_day"])),
            "movements": records(movements.drop(columns=["known_day"])),
        }
        fingerprint = hashlib.sha256(
            json.dumps(serial, sort_keys=True, default=str, allow_nan=False).encode()
        ).hexdigest()
        return OriginView(account, origin, history, tx, movements, fingerprint)

    def outcome(self, account_id, origin):
        origin = pd.Timestamp(origin)
        rows = self._balance[account_id]
        result = rows[
            (rows.day > origin) & (rows.day <= origin + pd.Timedelta(days=7))
        ].sort_values("day")
        if len(result) != 7:
            raise ValueError("Seven future label days are not available")
        return result

    def future_transactions(self, account_id, origin):
        origin = pd.Timestamp(origin)
        tx = self._tx[account_id]
        return tx[(tx.day > origin) & (tx.day <= origin + pd.Timedelta(days=7))].copy()


def known_amounts(view):
    return dict(zip(view.movements.item_id, view.movements.amount_minor, strict=True))


def residual_daily(transactions, movements, days):
    """Exclude up to the known scheduled amount, using the booked reference.
    Timing differences/under-settlement remain schedule errors. Positive excess and
    cash with no known-origin item are remaining flow. No signed residual is clipped.
    """
    known = dict(zip(movements.item_id, movements.amount_minor, strict=True))
    result = np.zeros((len(days), 2), dtype=np.int64)
    positions = {pd.Timestamp(d): i for i, d in enumerate(days)}
    for t in transactions.to_dict("records"):
        if t["day"] not in positions:
            continue
        amount = int(t["amount_minor"])
        expected = int(known.get(t["item_id"], 0))
        if expected and (expected > 0) == (amount > 0):
            remainder = max(0, abs(amount) - abs(expected))
        else:
            remainder = abs(amount)
        result[positions[t["day"]], 0 if amount > 0 else 1] += remainder
    return result


def scheduled(view):
    days = pd.date_range(view.origin + pd.Timedelta(days=1), periods=7)
    rows = []
    flows = np.zeros((7, 2), dtype=np.int64)
    for row in records(view.movements[view.movements.status == "Expected"]):
        due = pd.Timestamp(row["expected_date"])
        effective = max(
            due, days[0]
        )  # Outstanding overdue items remain visible; next-day point assumption.
        if effective in days:
            position = (effective - days[0]).days
            amount = int(row["amount_minor"])
            flows[position, 0 if amount > 0 else 1] += abs(amount)
            rows.append(
                {k: v for k, v in row.items() if k != "known_day"}
                | {"forecast_date": str(effective.date()), "overdue": bool(due <= view.origin)}
            )
    return flows, rows
