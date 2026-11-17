"""Reproducible fictional ledger. Latent simulator parameters never enter feature records."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 420
START = "2024-01-01"
AS_OF = "2026-10-31"
END = "2026-11-14"
VERSION = "synthetic-1.0"
SECTORS = ["Retail", "Consulting", "Manufacturing", "Wholesale", "Logistics"]
COUNTRIES = [
    ("Finland", "EUR", 1, "Oy"),
    ("Sweden", "SEK", 10, "AB"),
    ("Switzerland", "CHF", 1, "AG"),
]
NAMES = [
    "Birch Harbor",
    "Copper Meadow",
    "Lumen Works",
    "Cedar Thread",
    "Amber Atlas",
    "Juniper Lane",
    "Silver Orchard",
    "North Circuit",
    "Quiet Forge",
    "Maple Metric",
]


def timestamp(day, hour=18):
    return pd.Timestamp(day).strftime("%Y-%m-%d") + f"T{hour:02d}:00:00+00:00"


def generate(root: Path, count=100, seed=SEED):
    root.mkdir(parents=True, exist_ok=True)
    accounts, txs, versions, balances, latent = [], [], [], [], []
    dates = pd.date_range(START, END, freq="D")
    for index in range(count):
        rng = np.random.default_rng(seed + index * 101)
        aid = f"CP-{index + 1:03d}"
        country, currency, fx_scale, suffix = COUNTRIES[index % 3]
        unit = int(rng.integers(65000, 210000)) * fx_scale
        buffer = int(unit * rng.uniform(3, 6))
        target = int(buffer * rng.uniform(0.3, 4.5))
        sector = SECTORS[index % 5]
        account = {
            "id": aid,
            "company": f"{NAMES[index % 10]} Demo {index + 1} {suffix}",
            "country": country,
            "currency": currency,
            "industry": sector,
            "buffer_minor": buffer,
            "opening_minor": target,
            "dataset_version": VERSION,
        }
        accounts.append(account)
        # Private generation settings: not copied into forecasting inputs or UI artifacts.
        latent.append(
            {
                "id": aid,
                "unit": unit,
                "target": target,
                "late_rate": float(rng.uniform(0.08, 0.22)),
                "shift": float(rng.uniform(0.75, 1.3)),
            }
        )
        params = latent[-1]
        daily_events = {d: [] for d in dates}
        item_number = 0
        transaction_number = 0

        def book(day, amount, category, reference=None):
            nonlocal transaction_number
            if day in daily_events:
                transaction_number += 1
                daily_events[day].append(
                    {
                        "account_id": aid,
                        "id": f"{aid}-T{transaction_number:08d}",
                        "amount_minor": int(amount),
                        "currency": currency,
                        "category": category,
                        "booking_date": str(day.date()),
                        "available_date": str(day.date()),
                        "known_at": timestamp(day, 20),
                        "item_id": reference,
                    }
                )

        for day in dates:
            patterns = []
            season = 1 + 0.12 * np.sin(2 * np.pi * day.dayofyear / 365.25)
            change = params["shift"] if day >= pd.Timestamp("2026-02-01") else 1
            if day.weekday() in (0, 3):
                patterns.append(
                    (
                        "Customer receipt",
                        int(
                            unit
                            * (4.4 if day.weekday() == 0 else 3.7)
                            * season
                            * change
                            * rng.uniform(0.85, 1.15)
                        ),
                    )
                )
            if day.weekday() == 1:
                patterns.append(
                    ("Supplier payment", -int(unit * 2.8 * season * rng.uniform(0.85, 1.15)))
                )
            if day.day == 25:
                patterns.append(("Payroll", -int(unit * 8.2 * rng.uniform(0.97, 1.03))))
            if day.day == 1:
                patterns.append(("Rent", -int(unit * 2.1)))
            if day.day == 20 and day.month % 3 == 0:
                patterns.append(("Tax", -int(unit * 6 * rng.uniform(0.9, 1.1))))
            for category, amount in patterns:
                item_number += 1
                item = f"{aid}-M{item_number:05d}"
                events = [(day - pd.Timedelta(days=14), 12, day, amount, "Expected")]
                final_amount = amount
                if rng.random() < 0.1:
                    final_amount = int(round(amount * rng.uniform(0.94, 1.08)))
                    events.append((day - pd.Timedelta(days=4), 15, day, final_amount, "Expected"))
                cancelled = rng.random() < 0.012
                if cancelled:
                    events.append((day - pd.Timedelta(days=3), 16, day, final_amount, "Cancelled"))
                else:
                    delay = (
                        int(rng.integers(1, 6))
                        if amount > 0 and rng.random() < params["late_rate"]
                        else (-1 if rng.random() < 0.025 else 0)
                    )
                    actual_day = day + pd.Timedelta(days=delay)
                    if delay > 1:
                        events.append(
                            (
                                day + pd.Timedelta(days=1),
                                12,
                                max(
                                    day + pd.Timedelta(days=2),
                                    actual_day + pd.Timedelta(days=int(rng.integers(-1, 2))),
                                ),
                                final_amount,
                                "Expected",
                            )
                        )
                    actual_amount = (
                        int(round(final_amount * rng.uniform(0.97, 1.04)))
                        if rng.random() < 0.08
                        else final_amount
                    )
                    book(actual_day, actual_amount, category, item)
                    events.append((actual_day, 21, events[-1][2], final_amount, "Settled"))
                events.sort(key=lambda x: (x[0], x[1]))
                for version, (known, hour, expected, value, status) in enumerate(events, 1):
                    if known > dates[-1]:
                        continue
                    versions.append(
                        {
                            "account_id": aid,
                            "item_id": item,
                            "version": version,
                            "category": category,
                            "amount_minor": int(value),
                            "currency": currency,
                            "expected_date": str(expected.date()),
                            "known_at": timestamp(known, hour),
                            "status": status,
                            "settled_date": str(actual_day.date()) if status == "Settled" else None,
                            "settled_amount_minor": actual_amount if status == "Settled" else None,
                        }
                    )
        closing = target
        for day in dates:
            if day.day == 1:
                correction = int(target - closing + rng.normal(0, unit * 0.4))
                if correction:
                    book(
                        day,
                        correction,
                        "Owner contribution" if correction > 0 else "Owner distribution",
                    )
            if day.weekday() < 5:
                if rng.random() < 0.85:
                    # Sector changes the pattern; no risk label is generated.
                    multiplier = (1.2 if sector == "Retail" else 0.65) * (
                        1 + 0.1 * np.cos(day.dayofyear / 365.25 * 2 * np.pi)
                    )
                    book(
                        day,
                        int(unit * multiplier * rng.lognormal(-0.15, 0.35)),
                        "Other customer receipts",
                    )
                if rng.random() < 0.8:
                    book(day, -int(unit * 0.85 * rng.lognormal(-0.1, 0.3)), "Operating expenses")
                if rng.random() < 0.018:
                    book(day, -int(unit * rng.uniform(4, 10)), "Unexpected expense")
            events = daily_events[day]
            inflow = sum(max(0, t["amount_minor"]) for t in events)
            outflow = sum(max(0, -t["amount_minor"]) for t in events)
            opening = closing
            closing = opening + inflow - outflow
            balances.append(
                {
                    "account_id": aid,
                    "date": str(day.date()),
                    "currency": currency,
                    "opening_minor": opening,
                    "inflow_minor": inflow,
                    "outflow_minor": outflow,
                    "closing_minor": closing,
                    "known_at": timestamp(day, 23),
                }
            )
            txs.extend(events)
        print(f"Generated {aid}", flush=True) if (index + 1) % 20 == 0 else None
    pd.DataFrame(accounts).to_parquet(root / "accounts.parquet", index=False)
    pd.DataFrame(txs).to_parquet(root / "transactions.parquet", index=False)
    pd.DataFrame(versions).astype({"settled_amount_minor": "Int64"}).to_parquet(
        root / "movement_versions.parquet", index=False
    )
    pd.DataFrame(balances).to_parquet(root / "balances.parquet", index=False)
    (root / "generator_parameters.json").write_text(
        json.dumps(
            {"seed": seed, "reference": AS_OF, "version": VERSION, "parameters": latent}, indent=2
        )
        + "\n"
    )
    return accounts
