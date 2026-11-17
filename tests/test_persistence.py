import concurrent.futures
import copy
import hashlib

import pytest

from cashpilot.repository import Repository, review_status


def intent(value):
    return hashlib.sha256(value.encode()).hexdigest()


def test_review_restart_origin_and_isolation(repo, record, data):
    a, b = repo.create_workspace(), repo.create_workspace()
    aid = record["account_id"]
    repo.save(
        a,
        aid,
        record["id"],
        "Review",
        {"status": "Monitoring", "note": "Check the expected receipt."},
        intent("review"),
        0,
    )
    restarted = Repository(str(repo.engine.url))
    events, generation = restarted.history(a)
    assert generation == 0 and review_status(events, record["id"]) == "Monitoring"
    other = data["forecasts"][aid][0]
    assert review_status(events, other["id"]) == "Not reviewed"
    assert restarted.history(b)[0] == []
    assert events[0]["body"]["note"] == "Check the expected receipt."


def test_idempotent_scenario_uses_original_and_is_private(repo, record):
    a, b = repo.create_workspace(), repo.create_workspace()
    item = next(
        i
        for i in record["scheduled_items"]
        if i["category"] == "Customer receipt" and not i["overdue"]
    )
    payload = {
        "name": "Delayed invoice",
        "item_id": item["item_id"],
        "delay_days": 14,
        "days": [{"closing_minor": 99999999}],
    }
    first = repo.save(
        a, record["account_id"], record["id"], "Scenario", payload, intent("scenario"), 0
    )
    assert (
        repo.save(a, record["account_id"], record["id"], "Scenario", payload, intent("scenario"), 0)
        == first
    )
    events, _ = repo.history(a)
    assert len(events) == 1
    assert events[0]["body"]["item_version"] == item["version"]
    assert events[0]["body"]["original_snapshot"] == record["snapshot"]
    assert events[0]["body"]["days"][0].get("closing_minor") != 99999999
    assert not repo.history(b)[0]


def test_atomic_duplicate_save(repo, record):
    token = repo.create_workspace()

    def write(_):
        return repo.save(
            token,
            record["account_id"],
            record["id"],
            "Review",
            {"status": "Reviewed", "note": "Confirmed expected supplier payments."},
            intent("same"),
            0,
        )

    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        ids = list(pool.map(write, range(6)))
    assert len(set(ids)) == 1 and len(repo.history(token)[0]) == 1


def test_reset_fences_and_does_not_change_other_workspace(repo, record):
    a, b = repo.create_workspace(), repo.create_workspace()
    for token in (a, b):
        repo.save(
            token,
            record["account_id"],
            record["id"],
            "Review",
            {"status": "Monitoring", "note": "Track the customer receipt."},
            intent("note"),
            0,
        )
    repo.reset(a, 0)
    assert repo.history(a) == ([], 1)
    assert len(repo.history(b)[0]) == 1
    with pytest.raises(ValueError, match="changed"):
        repo.save(
            a,
            record["account_id"],
            record["id"],
            "Review",
            {"status": "Reviewed", "note": "Late request"},
            intent("late"),
            0,
        )


def test_immutable_registry_and_scope(repo, record):
    token = repo.create_workspace()
    original = repo.get_forecast(token, record["id"], record["account_id"])
    changed = copy.deepcopy(record)
    changed["days"][0]["closing_minor"] += 1
    with pytest.raises(ValueError, match="immutable"):
        repo.register([changed])
    assert repo.get_forecast(token, record["id"], record["account_id"]) == original
    with pytest.raises(ValueError, match="outside"):
        repo.save(
            token,
            "CP-WRONG",
            record["id"],
            "Review",
            {"status": "Reviewed", "note": "wrong"},
            intent("wrong"),
            0,
        )
    with pytest.raises(ValueError):
        repo.history("invalid-token")
    with pytest.raises(ValueError):
        repo.history("a" * 43)


@pytest.mark.parametrize("status,note", [("Approved", "hello"), ("Monitoring", "")])
def test_review_validation(repo, record, status, note):
    token = repo.create_workspace()
    with pytest.raises(ValueError):
        repo.save(
            token,
            record["account_id"],
            record["id"],
            "Review",
            {"status": status, "note": note},
            intent("invalid"),
            0,
        )
