"""One overview and one account detail screen; all predictions are prepared offline."""

import hashlib
import json
import uuid
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .artifacts import bundle, forecast_index
from .config import settings
from .domain import ALERTS, REVIEW_STATUSES, explain, first_negative, scenario
from .repository import Repository, review_status

STYLE = """<style>
.block-container {max-width:1320px;padding-top:4rem;padding-bottom:3rem}
[data-testid="stSidebar"] {background:#EAF0F6}
h1 {letter-spacing:-.045em;font-size:2.5rem!important}
h2,h3 {letter-spacing:-.025em}
.cp-kicker {font-size:.8rem;letter-spacing:.16em;font-weight:750;color:#0C766B;margin-bottom:.7rem}
.cp-lead {color:#54697E;max-width:800px;font-size:1.05rem;margin-bottom:1rem}
[data-testid="stMetricValue"] {font-size:1.5rem}
[data-testid="stDataFrame"] {border-radius:10px}
@media(max-width:640px){.block-container{padding:4rem .8rem 2rem}h1{font-size:1.9rem!important}[data-testid="stMetricValue"]{font-size:1.25rem}.cp-lead{font-size:.96rem}}
</style>"""


def money(value, currency):
    return "—" if value is None else f"{currency} {int(value) / 100:,.2f}"


def time_label(value):
    return datetime.fromisoformat(value).strftime("%d %b %Y · %H:%M UTC")


@st.cache_resource
def repository(url, manifest):
    repo = Repository(url)
    if repo.sqlite:
        repo.migrate()
        repo.register(forecast_index(bundle()).values())
    return repo


def save(repo, token, account, record, kind, payload, generation):
    key = f"intent:{hashlib.sha256(token.encode()).hexdigest()[:12]}:{record['id']}:{kind}"
    nonce = st.session_state.setdefault(key, str(uuid.uuid4()))
    intent = hashlib.sha256((nonce + json.dumps(payload, sort_keys=True)).encode()).hexdigest()
    try:
        repo.save(token, account["id"], record["id"], kind, payload, intent, generation)
        st.session_state.pop(key, None)
        st.rerun()
    except ValueError as exc:
        st.error(str(exc))
    except Exception:
        st.error("The save could not be confirmed. Refresh and check history before retrying.")


def chart(record, buffer_minor, scenario_result=None):
    fig = go.Figure()
    currency = record["currency"]
    origin = record["origin"]
    if scenario_result is None:
        h = record["actual_history"]
        fig.add_trace(
            go.Scatter(
                x=[r["date"] for r in h],
                y=[r["closing_minor"] / 100 for r in h],
                name="Actual",
                mode="lines",
                line={"color": "#324D71", "width": 2},
            )
        )
    days = record["days"]
    x = [origin] + [d["date"] for d in days]
    y = [record["starting_minor"] / 100] + [d["closing_minor"] / 100 for d in days]
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            name="Original forecast" if scenario_result else "Forecast",
            mode="lines+markers",
            line={
                "color": "#0C766B",
                "width": 3,
                "dash": "dash" if not scenario_result else "solid",
            },
            marker={"size": 5},
        )
    )
    if scenario_result:
        fig.add_trace(
            go.Scatter(
                x=x,
                y=[record["starting_minor"] / 100]
                + [d["closing_minor"] / 100 for d in scenario_result["days"]],
                name="Delayed receipt",
                mode="lines+markers",
                line={"color": "#BC622C", "width": 3, "dash": "dash"},
            )
        )
    elif record.get("later_actuals"):
        fig.add_trace(
            go.Scatter(
                x=[origin] + [d["date"] for d in record["later_actuals"]],
                y=[record["starting_minor"] / 100]
                + [d["closing_minor"] / 100 for d in record["later_actuals"]],
                name="Later actual",
                mode="lines+markers",
                line={"color": "#888BA3", "width": 2, "dash": "dot"},
            )
        )
    fig.add_hline(y=0, line_color="#B44C50", line_width=1)
    fig.add_hline(
        y=buffer_minor / 100,
        line_color="#AC8C45",
        line_dash="dot",
        annotation_text="Operating buffer",
        annotation_position="top left",
    )
    fig.add_shape(
        type="line",
        x0=origin,
        x1=origin,
        y0=0,
        y1=1,
        yref="paper",
        line={"color": "#9EABBC", "dash": "dot"},
    )
    fig.update_layout(
        height=385,
        margin={"l": 15, "r": 15, "t": 30, "b": 35},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Arial", "color": "#182F45"},
        legend={"orientation": "h", "y": 1.15, "x": 0},
        yaxis_title=f"Closing cash ({currency})",
        xaxis={"type": "date", "tickformat": "%d %b", "nticks": 6},
        hovermode="x unified",
    )
    st.plotly_chart(
        fig,
        width="stretch",
        config={"displayModeBar": False},
        key="path:" + record["id"] + ("scenario" if scenario_result else ""),
    )


def overview(data, events):
    st.markdown(
        '<div class="cp-kicker">CASHPILOT / CORPORATE CASH VISIBILITY</div>', unsafe_allow_html=True
    )
    st.title("See the next seven days clearly.")
    st.markdown(
        '<div class="cp-lead">Compare expected cash movements with daily closing-balance forecasts, then record a review or explore a delayed customer receipt.</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"Fictional businesses · Simulation as of {data['as_of']} · Point forecasts exclude credit facilities and intraday liquidity."
    )
    latest = [(a, data["forecasts"][a["id"]][-1]) for a in data["accounts"]]
    c1, c2, c3 = st.columns(3)
    c1.metric("Business accounts", len(latest))
    c2.metric("Projected shortfalls", sum(r["alert"] == "Projected shortfall" for _, r in latest))
    c3.metric("Forecasts unavailable", sum(not r["available"] for _, r in latest))
    with st.container(border=True):
        st.write("**Explore four computed examples**")
        cols = st.columns(4)
        for col, (key, label) in zip(
            cols,
            [
                ("within", "Within buffer"),
                ("buffer", "Below buffer"),
                ("shortfall", "Projected shortfall"),
                ("delayed_receipt", "Delay a receipt"),
            ],
            strict=True,
        ):
            if col.button(label, width="stretch"):
                st.query_params["account"] = data["examples"][key]["account_id"]
                st.rerun()
        st.caption(
            "Examples are selected from prepared forecast results. Monetary balances are never added across currencies."
        )
    search = st.text_input("Search company or account", placeholder="Try Birch or CP-001")
    c1, c2, c3 = st.columns(3)
    country = c1.multiselect("Country", sorted({a["country"] for a in data["accounts"]}))
    industry = c2.multiselect("Industry", sorted({a["industry"] for a in data["accounts"]}))
    currency = c3.multiselect("Currency", sorted({a["currency"] for a in data["accounts"]}))
    c1, c2 = st.columns(2)
    forecast_alert = c1.multiselect("Forecast alert", ALERTS)
    status = c2.multiselect("Review status", REVIEW_STATUSES)
    rows = []
    for account, record in latest:
        review = review_status(events, record["id"])
        if (
            search.lower() not in (account["company"] + account["id"]).lower()
            or (country and account["country"] not in country)
            or (industry and account["industry"] not in industry)
            or (currency and account["currency"] not in currency)
            or (forecast_alert and record["alert"] not in forecast_alert)
            or (status and review not in status)
        ):
            continue
        out = sorted(
            (i for i in record["scheduled_items"] if i["amount_minor"] < 0),
            key=lambda i: i["amount_minor"],
        )
        payment = out[0] if out else None
        rows.append(
            {
                "Account": account["id"],
                "Company": account["company"],
                "Country": account["country"],
                "Industry": account["industry"],
                "Currency": account["currency"],
                "Current available cash": money(record.get("starting_minor"), account["currency"]),
                "Lowest forecast close": money(
                    min(d["closing_minor"] for d in record["days"])
                    if record["available"]
                    else None,
                    account["currency"],
                ),
                "First negative date": first_negative(record) or "—"
                if record["available"]
                else "—",
                "Days below buffer": str(
                    sum(d["closing_minor"] < account["buffer_minor"] for d in record["days"])
                )
                if record["available"]
                else "—",
                "Largest scheduled payment": money(
                    abs(payment["amount_minor"]), account["currency"]
                )
                + f" · {payment['forecast_date']} · {payment['category']}"
                if payment
                else "—",
                "Forecast alert": record["alert"],
                "Review status": review,
                "Data quality": "Complete at cutoff" if record["available"] else record["reason"],
            }
        )
    st.caption(f"{len(rows)} matching accounts · Select a row or use the account selector below")
    selection = st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
        height=440,
        on_select="rerun",
        selection_mode="single-row",
        key="accounts-table",
    )
    if selection.selection.rows and selection.selection.rows[0] < len(rows):
        st.query_params["account"] = rows[selection.selection.rows[0]]["Account"]
        st.rerun()
    chosen = st.selectbox(
        "Open account by name",
        ["Choose an account…"] + [f"{r['Account']} · {r['Company']}" for r in rows],
    )
    if chosen != "Choose an account…":
        st.query_params["account"] = chosen.split(" · ")[0]
        st.rerun()


def detail(data, account, repo, token, events, generation):
    if st.button("← All accounts"):
        st.query_params.pop("account", None)
        st.rerun()
    st.markdown(f'<div class="cp-kicker">CASHPILOT / {account["id"]}</div>', unsafe_allow_html=True)
    st.title(account["company"])
    st.write(f"{account['country']} · {account['industry']} · **{account['currency']}**")
    records = list(reversed(data["forecasts"][account["id"]]))
    record = st.selectbox(
        "Forecast origin",
        records,
        format_func=lambda r: f"{r['origin']} · {r['model']}",
        key="origin:" + account["id"],
    )
    writable = bool(repo and token and record["available"])
    st.caption(
        f"Simulation as of {data['as_of']} · Cutoff {record['cutoff']} · Source timestamp {record['source_timestamp'] or 'incomplete'}"
    )
    st.caption(
        f"Operating buffer: {money(account['buffer_minor'], account['currency'])} · Review for this forecast: {review_status(events, record['id'])}"
    )
    if not record["available"]:
        st.warning("Forecast unavailable. " + record["reason"])
        return
    st.caption(
        "Current available balance means observed closing cash at the cutoff, excluding credit facilities."
    )
    low = min(d["closing_minor"] for d in record["days"])
    payments = [i for i in record["scheduled_items"] if i["amount_minor"] < 0]
    largest = min(payments, key=lambda i: i["amount_minor"]) if payments else None
    cols = st.columns(4)
    cols[0].metric("Current available cash", money(record["starting_minor"], account["currency"]))
    cols[1].metric("Lowest forecast close", money(low, account["currency"]))
    cols[2].metric(
        "Largest scheduled payment",
        money(abs(largest["amount_minor"]), account["currency"]) if largest else "—",
    )
    cols[3].metric("Forecast alert", record["alert"])
    tabs = st.tabs(["Cash outlook", "Cash movements", "Review & scenarios"])
    with tabs[0]:
        chart(record, account["buffer_minor"])
        st.info(explain(record, account["buffer_minor"]))
        st.caption(
            "The vertical line marks the forecast origin. Forecast values are fixed as originally prepared. Later actuals, when available by the simulation date, are shown separately. This is a point estimate; outcomes may differ."
        )
        if any(i["overdue"] for i in record["scheduled_items"]):
            st.caption(
                "Overdue, still-outstanding expectations are assumed on the next forecast day until an updated expectation is known; this is not a guarantee of settlement."
            )
        frame = pd.DataFrame(
            [
                {
                    "Date": d["date"],
                    **{
                        label: money(d[key], account["currency"])
                        for key, label in [
                            ("scheduled_in_minor", "Scheduled in"),
                            ("scheduled_out_minor", "Scheduled out"),
                            ("remaining_in_minor", "Estimated remaining in"),
                            ("remaining_out_minor", "Estimated remaining out"),
                            ("closing_minor", "Closing balance"),
                        ]
                    },
                }
                for d in record["days"]
            ]
        )
        st.dataframe(frame, hide_index=True, width="stretch")
        st.caption(
            f"Prepared method: {record['model']} · Model {record['model_version']} · Forecast reference {record['id']}"
        )
    with tabs[1]:
        st.subheader("Observed transactions")
        st.caption(
            "Booked cash visible by this forecast cutoff. Expected dates are not actual settlement dates."
        )
        tx = pd.DataFrame(
            [
                {
                    "Available date": t["available_date"],
                    "Amount": money(t["amount_minor"], account["currency"]),
                    "Currency": t["currency"],
                    "Category": t["category"],
                    "Known at": t["known_at"],
                    "Schedule reference": t["item_id"] or "—",
                }
                for t in record["transactions"]
            ]
        )
        st.dataframe(tx, hide_index=True, width="stretch", height=320)
        st.subheader("Expected movement schedule")
        st.caption(
            "Latest item versions known at this origin. Expectations may be revised, cancelled or settle at another date/amount. Settled items are not added again to the forecast."
        )
        schedule = pd.DataFrame(
            [
                {
                    "Item": i["item_id"],
                    "Version": i["version"],
                    "Category": i["category"],
                    "Amount": money(i["amount_minor"], i["currency"]),
                    "Currency": i["currency"],
                    "Expected date": i["expected_date"],
                    "Known at": i["known_at"],
                    "State": i["status"],
                    "Actual settlement date": i.get("settled_date") or "—",
                    "Actual settled amount": money(i.get("settled_amount_minor"), i["currency"])
                    if i.get("settled_amount_minor") is not None
                    else "—",
                }
                for i in record["schedule_view"]
            ]
        )
        st.dataframe(schedule, hide_index=True, width="stretch", height=360)
        with st.expander("Statistically estimated remaining cash movements"):
            st.caption(
                "These are daily flow estimates, not individual promised transactions. They are produced at the displayed forecast cutoff."
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Date": d["date"],
                            "Known at": record["cutoff"],
                            "Type": "Statistically estimated",
                            "Remaining inflow": money(d["remaining_in_minor"], account["currency"]),
                            "Remaining outflow": money(
                                d["remaining_out_minor"], account["currency"]
                            ),
                        }
                        for d in record["days"]
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
    with tabs[2]:
        st.subheader("Record a review")
        st.caption(
            "Review status is linked to this forecast origin and never changes the mathematical alert."
        )
        with st.form("review:" + hashlib.sha256((token + record["id"]).encode()).hexdigest()):
            status = st.selectbox(
                "Review status to save",
                REVIEW_STATUSES,
                index=REVIEW_STATUSES.index(review_status(events, record["id"])),
            )
            note = st.text_area(
                "Investigation note",
                max_chars=2000,
                placeholder="What needs checking, and what is the planned next step?",
            )
            if st.form_submit_button("Save review", disabled=not writable):
                save(
                    repo,
                    token,
                    account,
                    record,
                    "Review",
                    {"status": status, "note": note},
                    generation,
                )
        st.subheader("Delay a customer receipt")
        receipts = [
            i
            for i in record["scheduled_items"]
            if i["amount_minor"] > 0 and i["category"] == "Customer receipt" and not i["overdue"]
        ]
        if receipts:
            example = data["examples"]["delayed_receipt"]
            default = next(
                (n for n, i in enumerate(receipts) if i["item_id"] == example["item_id"]), 0
            )
            item = st.selectbox(
                "Expected customer receipt",
                receipts,
                index=default,
                format_func=lambda i: (
                    f"{i['forecast_date']} · {money(i['amount_minor'], account['currency'])} · {i['item_id']} v{i['version']}"
                ),
                key="receipt:" + record["id"],
            )
            delay = st.slider(
                "Postpone by calendar days",
                1,
                14,
                example["delay_days"] if account["id"] == example["account_id"] else 7,
                key="delay:" + record["id"],
            )
            preview = scenario(record, item["item_id"], delay)
            st.caption(
                f"Expected date {preview['original_date']} → {preview['revised_date']}. "
                + preview["assumption"]
            )
            chart(record, account["buffer_minor"], preview)
            a, b = st.columns(2)
            a.metric("Original minimum", money(low, account["currency"]))
            b.metric("Scenario minimum", money(preview["minimum_minor"], account["currency"]))
            a.write("**First negative close:** " + (first_negative(record) or "None"))
            b.write("**First negative close:** " + (preview["first_negative"] or "None"))
            if preview["revised_date"] > record["days"][-1]["date"]:
                st.caption(
                    "The revised receipt is outside these seven days. It is not added anywhere inside this horizon."
                )
            with st.form("scenario:" + hashlib.sha256((token + record["id"]).encode()).hexdigest()):
                name = st.text_input(
                    "Scenario name", max_chars=100, placeholder="Customer receipt delayed"
                )
                if st.form_submit_button("Save scenario", disabled=not writable):
                    save(
                        repo,
                        token,
                        account,
                        record,
                        "Scenario",
                        {"name": name, "item_id": item["item_id"], "delay_days": delay},
                        generation,
                    )
        else:
            st.info(
                "No non-overdue scheduled customer receipt is expected inside this seven-day horizon."
            )
        if not writable:
            st.caption(
                "Read-only exploration: start a saved workspace to record reviews and scenarios. Scenario preview remains available."
            )
        with st.expander("Saved review & scenario history", expanded=bool(events)):
            for event in (e for e in events if e["account_id"] == account["id"]):
                body = event["body"]
                st.write(
                    f"**{event['kind']}** · {time_label(event['created_at'])} · Forecast {event['forecast_id'][:8]}"
                )
                if event["kind"] == "Review":
                    st.write(f"{body['origin']} · {body['status']}")
                    st.write(body["note"])
                else:
                    st.write(
                        f"**{body['name']}** · {body['original_date']} → {body['revised_date']}"
                    )
                    st.write(
                        f"Saved minimum: {money(body['minimum_minor'], body['currency'])} · First negative: {body['first_negative'] or 'None'}"
                    )
                    st.caption(
                        f"Original forecast {body['forecast_id']} · Schedule item {body['item_id']} version {body['item_version']}"
                    )
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Date": d["date"],
                                    "Saved scenario close": money(
                                        d["closing_minor"], body["currency"]
                                    ),
                                }
                                for d in body["days"]
                            ]
                        ),
                        hide_index=True,
                        width="stretch",
                    )


def main():
    st.set_page_config(
        page_title="CashPilot · Corporate cash visibility", page_icon="◈", layout="wide"
    )
    st.markdown(STYLE, unsafe_allow_html=True)
    data = bundle()
    try:
        secret = st.secrets.get("cashpilot", {})
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        secret = {}
    config = settings(secret)
    repo = None
    token = st.query_params.get("workspace", "")
    events = []
    generation = 0
    try:
        if config.storage_url:
            repo = repository(config.storage_url, data["dataset_version"])
            if token:
                events, generation = repo.history(token)
    except ValueError as exc:
        st.warning(str(exc))
        token = ""
    except Exception:
        st.warning(
            "Saved-work storage is unavailable or not initialized. This view is read-only; no temporary database is substituted."
        )
        repo = None
        token = ""
    with st.sidebar:
        st.markdown("### ◈ CashPilot")
        st.caption("Corporate cash visibility")
        st.caption(
            f"Simulation as of **{data['as_of']}**\n\nSeven calendar days after each forecast origin."
        )
        if repo and token:
            st.success("Your saved workspace")
            st.caption(
                "Bookmark this full URL to return after refresh or restart. Its private return key grants access; do not share it. A browser without the key starts separately."
            )
            with st.expander("Reset my workspace"):
                confirmed = st.checkbox("Clear my saved reviews and scenarios")
                if st.button("Reset this workspace", disabled=not confirmed):
                    repo.reset(token, generation)
                    st.rerun()
        elif repo:
            st.info("Browsing immutable examples")
            if st.button("Start a saved workspace", type="primary", width="stretch"):
                try:
                    st.query_params["workspace"] = repo.create_workspace()
                    st.rerun()
                except Exception:
                    st.error("The workspace could not be confirmed. Saving remains disabled.")
        else:
            st.info("Read-only demonstration")
            st.caption(
                "Saved-work storage is not configured. Explore forecasts and preview scenarios; persistent saves are disabled."
            )
        st.divider()
        st.caption(
            "Daily closing-cash estimates, excluding overdrafts and available credit. A negative forecast is a planning warning."
        )
    accounts = {a["id"]: a for a in data["accounts"]}
    aid = st.query_params.get("account", "")
    if aid in accounts:
        detail(data, accounts[aid], repo, token, events, generation)
    else:
        overview(data, events)
