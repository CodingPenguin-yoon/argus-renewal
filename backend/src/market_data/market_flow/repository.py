from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from typing import Sequence

from ..db import get_connection, resolve_db_path
from .domain import (
    DataMode,
    DataQuality,
    FlowUnit,
    MarketFlowFact,
    MarketScope,
    MarketSegment,
)


class SQLiteMarketFlowRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def save(self, facts: Sequence[MarketFlowFact]) -> int:
        if not facts:
            return 0
        with get_connection(self.db_path) as connection:
            before = connection.total_changes
            connection.executemany(
                """
                INSERT INTO market_data_market_flow_facts (
                    source,
                    source_record_id,
                    data_mode,
                    market_scope,
                    segment,
                    quality,
                    trade_date,
                    observed_at,
                    collected_at,
                    unit,
                    individual_net,
                    foreign_net,
                    institution_net
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, data_mode, source_record_id) DO NOTHING
                """,
                [
                    (
                        fact.source,
                        fact.source_record_id,
                        fact.data_mode.value,
                        fact.market_scope.value,
                        fact.segment.value,
                        fact.quality.value,
                        fact.trade_date.isoformat(),
                        fact.observed_at.astimezone(timezone.utc).isoformat(),
                        fact.collected_at.astimezone(timezone.utc).isoformat(),
                        fact.unit.value,
                        fact.individual_net,
                        fact.foreign_net,
                        fact.institution_net,
                    )
                    for fact in facts
                ],
            )
            return connection.total_changes - before

    def list_latest(self, *, data_mode: DataMode) -> list[MarketFlowFact]:
        resolved_path = resolve_db_path(self.db_path)
        if not resolved_path.exists():
            return []

        connection = sqlite3.connect(f"{resolved_path.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            table_exists = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table' AND name = 'market_data_market_flow_facts'
                """
            ).fetchone()
            if table_exists is None:
                return []
            rows = connection.execute(
                """
                SELECT
                    source,
                    source_record_id,
                    data_mode,
                    market_scope,
                    segment,
                    quality,
                    trade_date,
                    observed_at,
                    collected_at,
                    unit,
                    individual_net,
                    foreign_net,
                    institution_net
                FROM market_data_market_flow_facts
                WHERE data_mode = ?
                ORDER BY observed_at DESC, id DESC
                """,
                (data_mode.value,),
            ).fetchall()
        finally:
            connection.close()

        latest: list[MarketFlowFact] = []
        seen: set[tuple[str, str]] = set()
        for row in rows:
            key = (row["segment"], row["quality"])
            if key in seen:
                continue
            seen.add(key)
            latest.append(
                MarketFlowFact(
                    source=row["source"],
                    source_record_id=row["source_record_id"],
                    data_mode=DataMode(row["data_mode"]),
                    market_scope=MarketScope(row["market_scope"]),
                    segment=MarketSegment(row["segment"]),
                    quality=DataQuality(row["quality"]),
                    trade_date=date.fromisoformat(row["trade_date"]),
                    observed_at=datetime.fromisoformat(row["observed_at"]),
                    collected_at=datetime.fromisoformat(row["collected_at"]),
                    unit=FlowUnit(row["unit"]),
                    individual_net=int(row["individual_net"]),
                    foreign_net=int(row["foreign_net"]),
                    institution_net=int(row["institution_net"]),
                )
            )
        return latest
