"""The UI only reads this prepared serving artifact, never training data or model weights."""

import hashlib
import json
from functools import lru_cache

from .config import ROOT


@lru_cache(maxsize=1)
def bundle():
    path = ROOT / "data/prepared.json"
    expected = json.loads((ROOT / "data/manifest.json").read_text())
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected["sha256"]:
        raise ValueError("Prepared forecast bundle failed its integrity check")
    value = json.loads(content)
    ids = {record["id"] for records in value["forecasts"].values() for record in records}
    if len(ids) != sum(map(len, value["forecasts"].values())):
        raise ValueError("Forecast identifiers are not unique")
    return value


def forecast_index(data):
    return {r["id"]: r for records in data["forecasts"].values() for r in records}


def immutable_body(record):
    # Later outcome observations are separate from the original predictive path.
    return {k: v for k, v in record.items() if k != "later_actuals"}
