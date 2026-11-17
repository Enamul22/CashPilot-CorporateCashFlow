import hashlib
import os
import subprocess
import sys

import pytest

from cashpilot.artifacts import forecast_index
from cashpilot.repository import Repository


@pytest.mark.postgres
def test_isolated_neon_restart_and_private_history(data, record):
    url = os.getenv("CASHPILOT_TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("An explicitly isolated Neon test branch is required")
    repo = Repository(url.replace("postgresql://", "postgresql+psycopg://", 1))
    repo.migrate()
    repo.register(forecast_index(data).values())
    a, b = repo.create_workspace(), repo.create_workspace()

    def key(x):
        return hashlib.sha256(x.encode()).hexdigest()

    repo.save(
        a,
        record["account_id"],
        record["id"],
        "Review",
        {"status": "Monitoring", "note": "Neon restart verification"},
        key("pg-review"),
        0,
    )
    item = next(
        i
        for i in record["scheduled_items"]
        if i["category"] == "Customer receipt" and not i["overdue"]
    )
    repo.save(
        a,
        record["account_id"],
        record["id"],
        "Scenario",
        {"name": "Persisted delayed receipt", "item_id": item["item_id"], "delay_days": 14},
        key("pg-scenario"),
        0,
    )
    script = 'import os; from cashpilot.repository import Repository; r=Repository(os.environ["CP_TEST_URL"]); e,g=r.history(os.environ["CP_TEST_TOKEN"]); assert len(e)==2; assert {x["kind"] for x in e}=={"Review","Scenario"}; print("restart recovered both event types")'
    result = subprocess.run(
        [sys.executable, "-c", script],
        env={
            **os.environ,
            "CP_TEST_URL": repo.engine.url.render_as_string(hide_password=False),
            "CP_TEST_TOKEN": a,
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, "Separate-process recovery failed"
    assert repo.history(b)[0] == []
    repo.reset(a, 0)
    assert repo.history(a)[0] == [] and repo.history(b)[0] == []
