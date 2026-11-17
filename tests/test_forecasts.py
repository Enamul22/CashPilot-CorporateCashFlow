import copy

import numpy as np
import pandas as pd
import pytest

from cashpilot.data import asof_schedule, residual_daily, scheduled
from cashpilot.domain import alert, balance_path, scenario
from cashpilot.forecast import Forecaster, fit, inputs
from cashpilot.generate import AS_OF


@pytest.mark.parametrize(
    "values,expected",
    [
        ([100] * 7, "Within buffer"),
        ([0] * 7, "Below buffer"),
        ([-1] + [100] * 6, "Projected shortfall"),
        ([99] + [100] * 6, "Below buffer"),
    ],
)
def test_alert_strict_boundaries(values, expected):
    assert alert(values, 100) == expected


@pytest.mark.parametrize(
    "values,buffer", [([1] * 6, 100), ([1.0] * 7, 100), ([1] * 7, 0), ([1] * 7, -1)]
)
def test_invalid_alert_input(values, buffer):
    with pytest.raises(ValueError):
        alert(values, buffer)


def test_arithmetic_does_not_count_current_day():
    path = balance_path(-100, [200] + [0] * 6, [0] * 7, [0] * 7, [0] * 7)
    assert path == [100] * 7 and alert(path, 50) == "Within buffer"
    with pytest.raises(ValueError):
        balance_path(0, [-1] * 7, [0] * 7, [0] * 7, [0] * 7)


@pytest.mark.parametrize("delay", [1, 3, 7, 14])
def test_scenario_conserves_components_and_does_not_mutate(record, delay):
    original = copy.deepcopy(record)
    item = next(
        i
        for i in record["scheduled_items"]
        if i["category"] == "Customer receipt" and not i["overdue"]
    )
    result = scenario(record, item["item_id"], delay)
    d = result["days"]
    path = balance_path(
        record["starting_minor"],
        *[
            [r[k] for r in d]
            for k in [
                "scheduled_in_minor",
                "scheduled_out_minor",
                "remaining_in_minor",
                "remaining_out_minor",
            ]
        ],
    )
    assert path == [r["closing_minor"] for r in d]
    assert all(
        a["remaining_in_minor"] == b["remaining_in_minor"]
        and a["remaining_out_minor"] == b["remaining_out_minor"]
        for a, b in zip(record["days"], d, strict=True)
    )
    assert record == original
    if result["revised_date"] > record["days"][-1]["date"]:
        assert d[-1]["closing_minor"] == record["days"][-1]["closing_minor"] - item["amount_minor"]


@pytest.mark.parametrize("delay", [0, 15, 1.5])
def test_scenario_bad_delay(record, delay):
    with pytest.raises(ValueError):
        scenario(record, record["scheduled_items"][0]["item_id"], delay)


def test_scenario_rejects_other_origin_item(record):
    with pytest.raises(ValueError):
        scenario(record, "CP-OTHER-ITEM", 3)
    outgoing = next(i for i in record["scheduled_items"] if i["amount_minor"] < 0)
    with pytest.raises(ValueError):
        scenario(record, outgoing["item_id"], 3)


def test_all_four_examples_are_computed(data):
    records = {k: data["forecasts"][v["account_id"]][-1] for k, v in data["examples"].items()}
    assert len({r["account_id"] for r in records.values()}) == 4
    assert records["within"]["alert"] == "Within buffer"
    assert (
        records["buffer"]["alert"] == "Below buffer"
        and min(d["closing_minor"] for d in records["buffer"]["days"]) >= 0
    )
    assert records["shortfall"]["alert"] == "Projected shortfall"
    e = data["examples"]["delayed_receipt"]
    r = records["delayed_receipt"]
    assert min(d["closing_minor"] for d in r["days"]) >= 0
    assert scenario(r, e["item_id"], e["delay_days"])["minimum_minor"] < 0


def test_prepared_arithmetic_and_asof(data):
    for account in data["accounts"]:
        for record in data["forecasts"][account["id"]]:
            if not record["available"]:
                continue
            rows = record["days"]
            assert len(rows) == 7 and rows[0]["date"] > record["origin"]
            assert balance_path(
                record["starting_minor"],
                *[
                    [r[k] for r in rows]
                    for k in [
                        "scheduled_in_minor",
                        "scheduled_out_minor",
                        "remaining_in_minor",
                        "remaining_out_minor",
                    ]
                ],
            ) == [r["closing_minor"] for r in rows]
            assert record["alert"] == alert(
                [r["closing_minor"] for r in rows], account["buffer_minor"]
            )
            assert all(t["known_at"] <= record["cutoff"] for t in record["transactions"])
            assert all(t["known_at"] <= record["cutoff"] for t in record["schedule_view"])
            assert all(d["date"] <= AS_OF for d in record["later_actuals"])
    assert data["forecasts"]["CP-099"][-1]["alert"] == "Forecast unavailable"
    assert data["forecasts"]["CP-100"][-1]["alert"] == "Forecast unavailable"


def test_point_in_time_ignores_future_changes(sources):
    origin = pd.Timestamp("2026-06-01")
    aid = "CP-020"
    before = sources.snapshot(aid, origin)
    features = inputs(before)[0]
    forecast = Forecaster().predict(before)
    tx = sources._tx[aid]
    versions = sources._versions[aid]
    balances = sources._balance[aid]
    try:
        sources._tx[aid] = tx.copy()
        sources._tx[aid].loc[tx.day > origin, "amount_minor"] = 999999999
        sources._versions[aid] = versions.copy()
        sources._versions[aid].loc[versions.known_day > origin, "amount_minor"] = 1
        sources._balance[aid] = balances.copy()
        sources._balance[aid].loc[balances.day > origin, "closing_minor"] = -99999999
        after = sources.snapshot(aid, origin)
        np.testing.assert_array_equal(inputs(after)[0], features)
        assert before.fingerprint == after.fingerprint and Forecaster().predict(after) == forecast
    finally:
        sources._tx[aid] = tx
        sources._versions[aid] = versions
        sources._balance[aid] = balances


def test_schedule_revision_cancellation_and_overdue(sources):
    view = sources.snapshot("CP-020", "2026-06-01")
    versions = sources._versions["CP-020"]
    assert all(view.movements.known_day <= view.origin)
    assert not view.movements.item_id.duplicated().any()
    visible = asof_schedule(versions, view.origin)
    assert set(visible.item_id) == set(view.movements.item_id)
    fake = copy.deepcopy(view)
    overdue = visible[visible.status == "Expected"].head(1).copy()
    overdue.loc[:, "expected_date"] = "2026-05-20"
    object.__setattr__(fake, "movements", overdue)
    flows, items = scheduled(fake)
    assert len(items) == 1 and items[0]["overdue"] and items[0]["forecast_date"] == "2026-06-02"
    assert int(flows[0].sum()) == abs(int(overdue.iloc[0].amount_minor))
    object.__setattr__(fake, "movements", overdue.assign(status="Cancelled"))
    assert scheduled(fake)[0].sum() == 0


def test_residual_excludes_known_settlement_without_double_count():
    day = pd.Timestamp("2026-01-03")
    movements = pd.DataFrame([{"item_id": "invoice", "amount_minor": 1000}])
    tx = pd.DataFrame(
        [
            {"day": day, "item_id": "invoice", "amount_minor": 1100},
            {"day": day, "item_id": None, "amount_minor": 300},
            {"day": day, "item_id": "not-known-at-origin", "amount_minor": 400},
        ]
    )
    assert residual_daily(tx, movements, [day]).tolist() == [[800, 0]]
    tx.loc[0, "amount_minor"] = 900
    assert residual_daily(tx, movements, [day]).tolist() == [[700, 0]]
    # A late known invoice is still matched on its actual date, not added again to residual cash.
    tx = tx.head(1)
    tx.loc[0, "amount_minor"] = 1000
    assert residual_daily(tx, movements, [day]).sum() == 0


def test_training_horizon_gap_is_enforced(sources):
    with pytest.raises(ValueError, match="not observable"):
        fit(sources, ["CP-001"], [pd.Timestamp("2026-04-28")], "2026-04-30", iterations=1)


def test_invalid_snapshot_is_unavailable(sources):
    with pytest.raises(ValueError, match="missing"):
        sources.snapshot("CP-001", AS_OF, "missing_balance")
    with pytest.raises(ValueError, match="currency"):
        sources.snapshot("CP-001", AS_OF, "currency_mismatch")
    original = sources._balance["CP-001"]
    try:
        changed = original.copy()
        changed.loc[changed.day == pd.Timestamp(AS_OF), "closing_minor"] += 1
        sources._balance["CP-001"] = changed
        with pytest.raises(ValueError, match="reconcile"):
            sources.snapshot("CP-001", AS_OF)
    finally:
        sources._balance["CP-001"] = original
