"""Chronological model selection and untouched test scoring. No model API calls."""

import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .data import Sources, records, validate_ledger
from .domain import scenario
from .forecast import BASELINE, CANDIDATE, Forecaster, fit
from .generate import AS_OF, VERSION, generate

TRAIN_CUTOFF = "2026-04-30"
REFIT_CUTOFF = "2026-06-30"
VALID_ORIGINS = pd.date_range("2026-05-04", "2026-06-22", freq="7D")
TEST_ORIGINS = pd.date_range("2026-07-06", "2026-09-28", freq="7D")
# Predeclared validation gate; final test cannot influence the default.
SELECTION = {
    "normalized_balance_mae_ratio_max": 0.98,
    "shortfall_recall_drop_max": 0.03,
    "false_alarm_rate_increase_max": 0.05,
}


def event_metrics(truth, pred):
    t = np.asarray(truth, dtype=bool)
    p = np.asarray(pred, dtype=bool)
    tp = int((t & p).sum())
    fp = int((~t & p).sum())
    fn = int((t & ~p).sum())
    tn = int((~t & ~p).sum())
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "origins": len(t),
        "events": int(t.sum()),
        "prevalence": float(t.mean()),
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "false_alarm_rate": fp / (fp + tn) if fp + tn else 0,
    }


def score(rows):
    def summary(group):
        return {
            "account_origins": len(group),
            "shortfall": event_metrics(
                [r["actual_negative"] for r in group], [r["pred_negative"] for r in group]
            ),
            "buffer_breach": event_metrics(
                [r["actual_buffer"] for r in group], [r["pred_buffer"] for r in group]
            ),
            "normalized_balance_mae": float(np.mean([r["normalized_mae"] for r in group])),
        }

    result = summary(rows)
    result["by_currency"] = {
        currency: {
            **summary(group := [r for r in rows if r["currency"] == currency]),
            "by_horizon": [
                {
                    "horizon": h + 1,
                    **{
                        name: float(np.mean([r[name][h] for r in group])) / 100
                        for name in ["inflow_abs_error", "outflow_abs_error", "closing_abs_error"]
                    },
                }
                for h in range(7)
            ],
        }
        for currency in sorted({r["currency"] for r in rows})
    }
    result["by_sector"] = {
        sector: {
            **summary(group := [r for r in rows if r["industry"] == sector]),
            "money_by_currency": {
                currency: {
                    "closing_mae": float(
                        np.mean(
                            [
                                np.mean(r["closing_abs_error"])
                                for r in group
                                if r["currency"] == currency
                            ]
                        )
                    )
                    / 100
                }
                for currency in sorted({r["currency"] for r in group})
            },
        }
        for sector in sorted({r["industry"] for r in rows})
    }
    return result


def evaluate(sources, accounts, origins, forecasters):
    results = {f.method: [] for f in forecasters}
    tick = time.perf_counter()
    for aid in accounts:
        for origin in origins:
            view = sources.snapshot(aid, origin)
            actual = sources.outcome(aid, origin)
            ai = actual.inflow_minor.to_numpy()
            ao = actual.outflow_minor.to_numpy()
            ac = actual.closing_minor.to_numpy()
            for f in forecasters:
                record = f.predict(view)
                pred = record["days"]
                pi = np.array([r["scheduled_in_minor"] + r["remaining_in_minor"] for r in pred])
                po = np.array([r["scheduled_out_minor"] + r["remaining_out_minor"] for r in pred])
                pc = np.array([r["closing_minor"] for r in pred])
                results[f.method].append(
                    {
                        "account_id": aid,
                        "origin": str(pd.Timestamp(origin).date()),
                        "currency": view.account["currency"],
                        "industry": view.account["industry"],
                        "actual_negative": bool(ac.min() < 0),
                        "pred_negative": bool(pc.min() < 0),
                        "actual_buffer": bool(ac.min() < view.account["buffer_minor"]),
                        "pred_buffer": bool(pc.min() < view.account["buffer_minor"]),
                        "inflow_abs_error": abs(pi - ai).astype(int).tolist(),
                        "outflow_abs_error": abs(po - ao).astype(int).tolist(),
                        "closing_abs_error": abs(pc - ac).astype(int).tolist(),
                        "normalized_mae": float(abs(pc - ac).mean() / record["scale_minor"]),
                        "actual_min_minor": int(ac.min()),
                        "pred_min_minor": int(pc.min()),
                    }
                )
    return {
        name: {"metrics": score(rows), "rows": rows} for name, rows in results.items()
    }, time.perf_counter() - tick


def select(validation):
    b = validation[BASELINE]["metrics"]
    c = validation[CANDIDATE]["metrics"]
    useful = (
        c["normalized_balance_mae"]
        <= b["normalized_balance_mae"] * SELECTION["normalized_balance_mae_ratio_max"]
        and (c["shortfall"]["recall"] or 0)
        >= (b["shortfall"]["recall"] or 0) - SELECTION["shortfall_recall_drop_max"]
        and c["shortfall"]["false_alarm_rate"]
        <= b["shortfall"]["false_alarm_rate"] + SELECTION["false_alarm_rate_increase_max"]
    )
    return CANDIDATE if useful else BASELINE


def prepare(sources, forecaster, destination):
    accounts = sources.accounts.to_dict("records")
    forecasts = {}
    origins = pd.date_range("2026-10-03", AS_OF, freq="7D")
    for account in accounts:
        account_records = []
        for origin in origins:
            invalid = (
                "missing_balance"
                if account["id"] == "CP-099" and origin == origins[-1]
                else "currency_mismatch"
                if account["id"] == "CP-100" and origin == origins[-1]
                else None
            )
            try:
                view = sources.snapshot(account["id"], origin, invalid=invalid)
                record = forecaster.predict(view)
                record["actual_history"] = (
                    view.history[["date", "closing_minor"]].tail(30).to_dict("records")
                )
                record["transactions"] = records(
                    view.transactions.drop(columns=["day", "known_day"]).tail(90)
                )
                shown = view.movements[
                    (pd.to_datetime(view.movements.expected_date) >= origin - pd.Timedelta(days=30))
                    | (view.movements.status == "Expected")
                ]
                record["schedule_view"] = records(shown.drop(columns="known_day"))
                # Later outcomes are separately served only up to the simulation as-of date.
                later = sources.outcome(account["id"], origin)
                record["later_actuals"] = later[later.day <= pd.Timestamp(AS_OF)][
                    ["date", "closing_minor"]
                ].to_dict("records")
            except ValueError as exc:
                record = {
                    "id": hashlib.sha256(
                        f"{account['id']}|{origin}|unavailable".encode()
                    ).hexdigest()[:32],
                    "account_id": account["id"],
                    "currency": account["currency"],
                    "origin": str(origin.date()),
                    "cutoff": str(origin.date()) + "T23:59:59+00:00",
                    "source_timestamp": None,
                    "available": False,
                    "reason": str(exc),
                    "alert": "Forecast unavailable",
                    "days": [],
                    "scheduled_items": [],
                    "model": forecaster.method,
                }
            account_records.append(record)
        forecasts[account["id"]] = account_records
    latest = [(a, forecasts[a["id"]][-1]) for a in accounts if forecasts[a["id"]][-1]["available"]]
    examples = {}
    for wanted, key in [
        ("Within buffer", "within"),
        ("Below buffer", "buffer"),
        ("Projected shortfall", "shortfall"),
    ]:
        found = next(((a, r) for a, r in latest if r["alert"] == wanted), None)
        if found:
            examples[key] = {"account_id": found[0]["id"], "forecast_id": found[1]["id"]}
    used = {e["account_id"] for e in examples.values()}
    for a, r in latest:
        if a["id"] in used:
            continue
        if min(d["closing_minor"] for d in r["days"]) >= 0:
            item = next(
                (
                    i
                    for i in r["scheduled_items"]
                    if i["category"] == "Customer receipt"
                    and i["amount_minor"] > 0
                    and not i.get("overdue", False)
                    and scenario(r, i["item_id"], 14)["minimum_minor"] < 0
                ),
                None,
            )
            if item:
                examples["delayed_receipt"] = {
                    "account_id": a["id"],
                    "forecast_id": r["id"],
                    "item_id": item["item_id"],
                    "delay_days": 14,
                }
                break
    if len(examples) != 4:
        raise ValueError(f"Computed examples not all present: {list(examples)}")
    artifact = {
        "schema_version": 1,
        "dataset_version": VERSION,
        "as_of": AS_OF,
        "method": forecaster.method,
        "model_version": "flows-1.0",
        "accounts": accounts,
        "forecasts": forecasts,
        "examples": examples,
    }
    text = json.dumps(artifact, separators=(",", ":"), default=str, allow_nan=False)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "prepared.json").write_text(text + "\n")
    (destination / "manifest.json").write_text(
        json.dumps(
            {
                "sha256": hashlib.sha256((text + "\n").encode()).hexdigest(),
                "as_of": AS_OF,
                "examples": examples,
                "accounts": len(accounts),
            },
            indent=2,
        )
        + "\n"
    )
    return examples


def pipeline(root: Path, smoke=False):
    raw = root / "evaluation/raw"
    report_dir = root / "evaluation/results"
    report_dir.mkdir(parents=True, exist_ok=True)
    generate(raw, count=10 if smoke else 100)
    sources = Sources(raw)
    validation = validate_ledger(
        sources.accounts, sources.transactions, sources.balances, sources.versions
    )
    ids = sources.accounts.id.tolist()
    known = ids[:8] if smoke else ids[:80]
    unseen = ids[8:] if smoke else ids[80:]
    train = pd.date_range("2024-03-04", TRAIN_CUTOFF, freq="14D" if smoke else "7D")
    train = train[train + pd.Timedelta(days=7) <= pd.Timestamp(TRAIN_CUTOFF)]
    tick = time.perf_counter()
    candidate, train_meta = fit(
        sources, known, train, TRAIN_CUTOFF, iterations=20 if smoke else 120
    )
    valid, valid_seconds = evaluate(
        sources, known, VALID_ORIGINS[:2] if smoke else VALID_ORIGINS, [Forecaster(), candidate]
    )
    chosen = select(valid)
    print("Validation frozen. Default:", chosen, flush=True)
    refit = pd.date_range("2024-03-04", REFIT_CUTOFF, freq="14D" if smoke else "7D")
    refit = refit[refit + pd.Timedelta(days=7) <= pd.Timestamp(REFIT_CUTOFF)]
    final_candidate, final_meta = fit(
        sources, known, refit, REFIT_CUTOFF, iterations=20 if smoke else 120
    )
    test_origins = TEST_ORIGINS[:2] if smoke else TEST_ORIGINS
    test, test_seconds = evaluate(sources, known, test_origins, [Forecaster(), final_candidate])
    transfer, transfer_seconds = evaluate(
        sources, unseen, test_origins, [Forecaster(), final_candidate]
    )
    report = {
        "dataset": VERSION,
        "reference": AS_OF,
        "selection_rule": SELECTION,
        "chosen_method": chosen,
        "train": train_meta,
        "refit": final_meta,
        "data_validation": validation,
        "validation": valid,
        "known_account_test": test,
        "unseen_business_test": transfer,
        "timing_seconds": {
            "validation_predictions": valid_seconds,
            "known_test_predictions": test_seconds,
            "unseen_test_predictions": transfer_seconds,
            "total": time.perf_counter() - tick,
        },
        "scope": "Non-overlapping weekly seven-calendar-day origins; repeated businesses remain correlated. All money errors are within a single currency.",
    }
    (report_dir / ("smoke.json" if smoke else "metrics.json")).write_text(
        json.dumps(report, indent=2) + "\n"
    )
    if not smoke:
        import joblib

        joblib.dump(final_candidate, report_dir / "pooled-model.joblib")
        prepare(sources, final_candidate if chosen == CANDIDATE else Forecaster(), root / "data")
    print("Pipeline complete.", flush=True)
    return report
