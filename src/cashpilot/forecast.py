"""Nonnegative scheduled-plus-remaining flow forecasts. Fitting is an offline operation."""

import hashlib
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from .data import residual_daily, scheduled
from .domain import alert, balance_path
from .generate import SECTORS

BASELINE = "Seasonal naive"
CANDIDATE = "Pooled gradient boosting"
MODEL_VERSION = "flows-1.0"


def inputs(view):
    history_days = pd.DatetimeIndex(view.history["day"])
    remaining = residual_daily(view.transactions, view.movements, history_days)
    # Native-currency minor-unit scale; no conversion or mixed-currency money average.
    scale = max(100, int(round((view.history.inflow_minor + view.history.outflow_minor).mean())))
    schedule, items = scheduled(view)
    rows, base = [], []
    start = int(view.history.iloc[-1].closing_minor)
    for h in range(1, 8):
        future = view.origin + pd.Timedelta(days=h)
        seasonal = []
        for component in (0, 1):
            prior = [
                remaining[history_days.get_loc(future - pd.Timedelta(days=7 * k)), component]
                for k in range(1, 5)
                if future - pd.Timedelta(days=7 * k) in history_days
            ]
            seasonal.append(
                float(np.median(prior)) if prior else float(remaining[:, component].mean())
            )
        base.append(seasonal)
        rows.append(
            [
                h,
                future.weekday(),
                future.day,
                float(future.day >= 25),
                float(future.day == 1),
                np.sin(future.month * 2 * np.pi / 12),
                np.cos(future.month * 2 * np.pi / 12),
                start / scale,
                len(history_days) / 56,
                *[float(s == view.account["industry"]) for s in SECTORS],
                *[int(n) / scale for n in schedule[h - 1]],
                *[v / scale for v in seasonal],
                *[float(n) / scale for n in remaining[-1]],
                *[float(n) / scale for n in remaining[-7:].mean(axis=0)],
                *[float(n) / scale for n in remaining[-28:].mean(axis=0)],
            ]
        )
    return np.asarray(rows, dtype=float), np.asarray(base, dtype=float), scale, schedule, items


def labels(view, future_transactions):
    days = pd.date_range(view.origin + pd.Timedelta(days=1), periods=7)
    return residual_daily(future_transactions, view.movements, days)


class Forecaster:
    def __init__(self, method=BASELINE, models=None, fit_cutoff=None):
        self.method, self.models, self.fit_cutoff = method, models, fit_cutoff

    def predict(self, view):
        x, base, scale, schedule, items = inputs(view)
        residual = (
            base
            if self.method == BASELINE
            else np.column_stack([model.predict(x) * scale for model in self.models])
        )
        residual = np.maximum(0, np.rint(residual)).astype(np.int64)
        start = int(view.history.iloc[-1].closing_minor)
        closing = balance_path(
            start,
            *[schedule[:, i].astype(int).tolist() for i in (0, 1)],
            *[residual[:, i].astype(int).tolist() for i in (0, 1)],
        )
        rows = [
            {
                "date": str((view.origin + pd.Timedelta(days=h + 1)).date()),
                "scheduled_in_minor": int(schedule[h, 0]),
                "scheduled_out_minor": int(schedule[h, 1]),
                "remaining_in_minor": int(residual[h, 0]),
                "remaining_out_minor": int(residual[h, 1]),
                "closing_minor": closing[h],
            }
            for h in range(7)
        ]
        identity = {
            "account": view.account["id"],
            "origin": str(view.origin.date()),
            "snapshot": view.fingerprint,
            "method": self.method,
            "model_version": MODEL_VERSION,
            "fit_cutoff": self.fit_cutoff,
            "days": rows,
        }
        return {
            "id": hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:32],
            "account_id": view.account["id"],
            "currency": view.account["currency"],
            "origin": str(view.origin.date()),
            "cutoff": str(view.origin.date()) + "T23:59:59+00:00",
            "source_timestamp": view.history.iloc[-1].known_at,
            "snapshot": view.fingerprint,
            "model": self.method,
            "model_version": MODEL_VERSION,
            "fit_cutoff": self.fit_cutoff,
            "available": True,
            "reason": "",
            "starting_minor": start,
            "scale_minor": scale,
            "days": rows,
            "scheduled_items": items,
            "alert": alert(closing, view.account["buffer_minor"]),
        }


def fit(sources, accounts, origins, label_cutoff, iterations=120):
    xs, ys = [], []
    for aid in accounts:
        for origin in origins:
            if pd.Timestamp(origin) + pd.Timedelta(days=7) > pd.Timestamp(label_cutoff):
                raise ValueError("A training label is not observable before the fitting cutoff")
            view = sources.snapshot(aid, origin)
            x, _, scale, _, _ = inputs(view)
            future = sources.future_transactions(aid, origin)
            outcome = sources.outcome(aid, origin)
            if (future.known_day > pd.Timestamp(label_cutoff)).any() or (
                outcome.known_day > pd.Timestamp(label_cutoff)
            ).any():
                raise ValueError("Training labels are not fully observable by the fitting cutoff")
            target = labels(view, future) / scale
            xs.append(x)
            ys.append(target)
    x = np.vstack(xs)
    y = np.vstack(ys)
    models = []
    for component in (0, 1):
        model = HistGradientBoostingRegressor(
            loss="poisson",
            learning_rate=0.08,
            max_iter=iterations,
            max_leaf_nodes=15,
            l2_regularization=2,
            early_stopping=False,
            random_state=420,
        )
        model.fit(x, y[:, component])
        models.append(model)
    return Forecaster(CANDIDATE, models, label_cutoff), {
        "training_accounts": len(accounts),
        "origins_per_account": len(origins),
        "rows": len(x),
        "last_label_date": str((pd.Timestamp(max(origins)) + pd.Timedelta(days=7)).date()),
        "fit_cutoff": label_cutoff,
        "features": x.shape[1],
        "parameters": models[0].get_params(),
    }
