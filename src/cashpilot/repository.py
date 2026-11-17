"""Capability-scoped append-only review/scenario events on Postgres or explicit SQLite."""

import hashlib
import json
import re
import secrets
from contextlib import contextmanager
from datetime import datetime, timezone

import certifi
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.pool import NullPool

from .artifacts import immutable_body
from .domain import REVIEW_STATUSES, scenario

META = MetaData()
GATE = Table(
    "cp_schema",
    META,
    Column("id", Integer, primary_key=True),
    Column("version", Integer, nullable=False),
)
WORKSPACES = Table(
    "cp_workspaces",
    META,
    Column("token_hash", String(64), primary_key=True),
    Column("generation", Integer, nullable=False),
    Column("created_at", String(40), nullable=False),
)
FORECASTS = Table(
    "cp_forecasts",
    META,
    Column("id", String(64), primary_key=True),
    Column("account_id", String(30), nullable=False),
    Column("origin", String(10), nullable=False),
    Column("fingerprint", String(64), nullable=False),
    Column("body", Text, nullable=False),
)
EVENTS = Table(
    "cp_events",
    META,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("workspace", String(64), ForeignKey("cp_workspaces.token_hash"), nullable=False),
    Column("forecast_id", String(64), ForeignKey("cp_forecasts.id"), nullable=False),
    Column("account_id", String(30), nullable=False),
    Column("kind", String(20), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("intent", String(64), nullable=False),
    Column("body", Text, nullable=False),
    UniqueConstraint("workspace", "intent"),
)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class Repository:
    def __init__(self, url):
        self.sqlite = url.startswith("sqlite")
        self.engine = create_engine(
            url,
            poolclass=NullPool,
            hide_parameters=True,
            connect_args={"timeout": 15}
            if self.sqlite
            else {"connect_timeout": 15, "sslmode": "verify-full", "sslrootcert": certifi.where()},
        )

    def migrate(self):
        META.create_all(self.engine)
        with self.engine.begin() as conn:
            if not conn.execute(select(GATE)).first():
                conn.execute(insert(GATE).values(id=1, version=1))

    @contextmanager
    def transaction(self, write=False):
        with self.engine.connect() as conn:
            if self.sqlite:
                conn.exec_driver_sql("PRAGMA foreign_keys=ON")
                conn.exec_driver_sql("PRAGMA busy_timeout=15000")
                conn.exec_driver_sql("BEGIN IMMEDIATE" if write else "BEGIN")
            else:
                conn.begin()
            try:
                query = select(GATE).where(GATE.c.id == 1)
                if write:
                    query = query.with_for_update()
                gate = conn.execute(query).first()
                if not gate or gate.version != 1:
                    raise ValueError("Database migration is required")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def register(self, records):
        with self.transaction(True) as conn:
            known = {
                r.id: r.fingerprint
                for r in conn.execute(select(FORECASTS.c.id, FORECASTS.c.fingerprint))
            }
            pending = []
            for record in records:
                body = json.dumps(immutable_body(record), sort_keys=True, separators=(",", ":"))
                fingerprint = hashlib.sha256(body.encode()).hexdigest()
                if record["id"] in known:
                    if known[record["id"]] != fingerprint:
                        raise ValueError("An immutable forecast was changed")
                else:
                    pending.append(
                        {
                            "id": record["id"],
                            "account_id": record["account_id"],
                            "origin": record["origin"],
                            "fingerprint": fingerprint,
                            "body": json.dumps(record, separators=(",", ":")),
                        }
                    )
            if pending:
                conn.execute(insert(FORECASTS), pending)

    @staticmethod
    def digest(token):
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token or ""):
            raise ValueError("Invalid workspace return key")
        return hashlib.sha256(token.encode()).hexdigest()

    def scope(self, conn, token):
        key = self.digest(token)
        generation = conn.execute(
            select(WORKSPACES.c.generation).where(WORKSPACES.c.token_hash == key)
        ).scalar_one_or_none()
        if generation is None:
            raise ValueError("Unknown workspace return key")
        return key, generation

    def create_workspace(self):
        token = secrets.token_urlsafe(32)
        with self.transaction(True) as conn:
            conn.execute(
                insert(WORKSPACES).values(
                    token_hash=self.digest(token), generation=0, created_at=now()
                )
            )
        return token

    def history(self, token, account_id=None):
        with self.transaction() as conn:
            key, generation = self.scope(conn, token)
            query = select(EVENTS).where(EVENTS.c.workspace == key)
            if account_id:
                query = query.where(EVENTS.c.account_id == account_id)
            events = [
                dict(row) | {"body": json.loads(row["body"])}
                for row in conn.execute(query.order_by(EVENTS.c.id.desc())).mappings()
            ]
            return events, generation

    def get_forecast(self, token, forecast_id, account_id):
        with self.transaction() as conn:
            self.scope(conn, token)
            row = (
                conn.execute(
                    select(FORECASTS).where(
                        FORECASTS.c.id == forecast_id, FORECASTS.c.account_id == account_id
                    )
                )
                .mappings()
                .first()
            )
            if not row:
                raise ValueError("Forecast is outside the active account")
            return json.loads(row["body"])

    def save(self, token, account_id, forecast_id, kind, payload, intent, generation):
        if not re.fullmatch(r"[a-f0-9]{64}", intent or ""):
            raise ValueError("A valid idempotency key is required")
        with self.transaction(True) as conn:
            key, current = self.scope(conn, token)
            if current != generation:
                raise ValueError("Workspace changed. Refresh before saving.")
            old = (
                conn.execute(
                    select(EVENTS).where(EVENTS.c.workspace == key, EVENTS.c.intent == intent)
                )
                .mappings()
                .first()
            )
            if old:
                if (
                    old["forecast_id"] != forecast_id
                    or old["account_id"] != account_id
                    or old["kind"] != kind
                ):
                    raise ValueError("Idempotency key belongs to another saved action")
                return old["id"]
            row = (
                conn.execute(
                    select(FORECASTS).where(
                        FORECASTS.c.id == forecast_id, FORECASTS.c.account_id == account_id
                    )
                )
                .mappings()
                .first()
            )
            if not row:
                raise ValueError("Forecast is outside the active account")
            record = json.loads(row["body"])
            if not record["available"]:
                raise ValueError("Review/scenario saves need a valid forecast")
            if kind == "Review":
                status = payload.get("status")
                note = payload.get("note", "").strip()
                if status not in REVIEW_STATUSES or not 1 <= len(note) <= 2000:
                    raise ValueError("Choose a review status and enter a note (1–2000 characters).")
                body = {"status": status, "note": note, "origin": record["origin"]}
            elif kind == "Scenario":
                name = payload.get("name", "").strip()
                if not 1 <= len(name) <= 100:
                    raise ValueError("Give the scenario a name (1–100 characters).")
                body = {
                    "name": name,
                    **scenario(record, payload.get("item_id"), payload.get("delay_days")),
                }
            else:
                raise ValueError("Unsupported saved action")
            result = conn.execute(
                insert(EVENTS).values(
                    workspace=key,
                    forecast_id=forecast_id,
                    account_id=account_id,
                    kind=kind,
                    created_at=now(),
                    intent=intent,
                    body=json.dumps(body),
                )
            )
            return result.inserted_primary_key[0]

    def reset(self, token, generation):
        with self.transaction(True) as conn:
            key, current = self.scope(conn, token)
            if current != generation:
                raise ValueError("Workspace changed. Refresh before resetting.")
            conn.execute(delete(EVENTS).where(EVENTS.c.workspace == key))
            conn.execute(
                update(WORKSPACES)
                .where(WORKSPACES.c.token_hash == key)
                .values(generation=current + 1)
            )


def review_status(events, forecast_id):
    event = next(
        (e for e in events if e["forecast_id"] == forecast_id and e["kind"] == "Review"), None
    )
    return event["body"]["status"] if event else "Not reviewed"
