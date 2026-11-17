"""Currency-safe integer arithmetic and central forecast/scenario rules."""

import hashlib
import json
from datetime import date, timedelta

ALERTS = ["Within buffer", "Below buffer", "Projected shortfall", "Forecast unavailable"]
REVIEW_STATUSES = ["Not reviewed", "Monitoring", "Reviewed"]


def alert(days, buffer_minor):
    if buffer_minor <= 0:
        raise ValueError("Operating buffer must be positive")
    if len(days) != 7 or any(type(v) is not int for v in days):
        raise ValueError("Seven integer closing balances are required")
    return (
        "Projected shortfall"
        if min(days) < 0
        else "Below buffer"
        if min(days) < buffer_minor
        else "Within buffer"
    )


def balance_path(start, schedule_in, schedule_out, remaining_in, remaining_out):
    if not all(len(x) == 7 for x in [schedule_in, schedule_out, remaining_in, remaining_out]):
        raise ValueError("Seven days of cash components are required")
    closing, result = int(start), []
    for values in zip(schedule_in, schedule_out, remaining_in, remaining_out, strict=True):
        if any(type(v) is not int or v < 0 for v in values):
            raise ValueError("Flow components must be nonnegative integer minor units")
        si, so, ri, ro = values
        closing += si + ri - so - ro
        result.append(closing)
    return result


def first_negative(record):
    return next((row["date"] for row in record["days"] if row["closing_minor"] < 0), None)


def scenario(record, item_id, delay):
    if not record["available"]:
        raise ValueError("A valid original forecast is required")
    if type(delay) is not int or not 1 <= delay <= 14:
        raise ValueError("Delay must be 1–14 calendar days")
    item = next((i for i in record["scheduled_items"] if i["item_id"] == item_id), None)
    if (
        item is None
        or item["amount_minor"] <= 0
        or item["category"] != "Customer receipt"
        or item.get("overdue", False)
    ):
        raise ValueError("Select a customer receipt in this forecast horizon")
    old = date.fromisoformat(item["forecast_date"])
    new = old + timedelta(days=delay)
    days = []
    for row in record["days"]:
        d = date.fromisoformat(row["date"])
        delta = (-item["amount_minor"] if d >= old else 0) + (
            item["amount_minor"] if d >= new else 0
        )
        daily_change = (-item["amount_minor"] if d == old else 0) + (
            item["amount_minor"] if d == new else 0
        )
        days.append(
            {
                **row,
                "scheduled_in_minor": row["scheduled_in_minor"] + daily_change,
                "closing_minor": row["closing_minor"] + delta,
            }
        )
    body = {
        "original_snapshot": record["snapshot"],
        "model_version": record["model_version"],
        "forecast_id": record["id"],
        "item_id": item_id,
        "item_version": item["version"],
        "delay_days": delay,
        "original_date": str(old),
        "revised_date": str(new),
        "amount_minor": item["amount_minor"],
        "currency": record["currency"],
        "days": days,
        "minimum_minor": min(d["closing_minor"] for d in days),
        "first_negative": next((d["date"] for d in days if d["closing_minor"] < 0), None),
        "assumption": "Remaining-flow estimates are unchanged. Only this scheduled receipt is moved; no model is refitted.",
    }
    body["fingerprint"] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    return body


def explain(record, buffer_minor):
    if not record["available"]:
        return "A forecast cannot be shown: " + record["reason"]
    days = record["days"]
    low = min(days, key=lambda d: d["closing_minor"])
    currency = record["currency"]

    def money(n):
        return f"{currency} {n / 100:,.2f}"

    breach = next((d for d in days if d["closing_minor"] < buffer_minor), None)
    sentence = (
        f"Closing cash first falls below the {money(buffer_minor)} operating buffer on {date.fromisoformat(breach['date']).strftime('%A %d %b')}. "
        if breach
        else f"All seven forecast closes meet the {money(buffer_minor)} operating buffer. "
    )
    sentence += f"The lowest estimated close is {money(low['closing_minor'])} on {low['date']}. "
    largest = sorted(
        (i for i in record["scheduled_items"] if i["amount_minor"] < 0),
        key=lambda i: i["amount_minor"],
    )[:2]
    if largest:
        sentence += (
            "Known expectations include "
            + " and ".join(
                f"{money(abs(i['amount_minor']))} for {i['category'].lower()} on {i['forecast_date']}"
                for i in largest
            )
            + ". "
        )
    receipts = sum(max(0, i["amount_minor"]) for i in record["scheduled_items"])
    sentence += f"Scheduled receipts total {money(receipts)}. Remaining cash movements are statistical estimates; expected receipts may settle later or at different amounts."
    return sentence
