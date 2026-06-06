from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd

from app.engine.news_intel import NewsIntel, analyze_news_titles
from app.engine.smart_money_intel import SmartMoneyIntel, analyze_smart_money
from app.engine.sector_rules import pe_pb_thresholds, sector_bucket


@dataclass
class ScanContext:
    symbol: str
    market: str
    hist: pd.DataFrame
    info: dict[str, Any]
    earnings: dict[str, Any] | None = None
    news_count: int = 0
    news_titles: list[str] = field(default_factory=list)
    calendar: dict[str, Any] | None = None

    # computed
    price: float = 0.0
    day_chg_pct: float = 0.0
    ret5d_pct: float = 0.0
    ret20d_pct: float = 0.0
    rvol: float = 1.0
    sector: str = ""
    industry: str = ""
    bucket: str = "general"
    val_thresholds: dict[str, float] = field(default_factory=dict)
    news_intel: NewsIntel = field(default_factory=NewsIntel)
    smart_money: SmartMoneyIntel = field(default_factory=SmartMoneyIntel)
    dividend_days: int | None = None

    def __post_init__(self):
        self._compute_price()
        self.sector = self.info.get("sector") or ""
        self.industry = self.info.get("industry") or ""
        self.bucket = sector_bucket(self.sector, self.industry, self.market)
        self.val_thresholds = pe_pb_thresholds(self.bucket, self.market)
        self.news_intel = analyze_news_titles(self.news_titles)
        self.smart_money = analyze_smart_money(self.news_titles, market=self.market)
        self.dividend_days = self._dividend_days()

    def _compute_price(self) -> None:
        close = self.hist["Close"]
        volume = self.hist["Volume"]
        self.price = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) > 1 else self.price
        self.day_chg_pct = (self.price / prev - 1) * 100 if prev else 0
        self.ret5d_pct = (
            (self.price / float(close.iloc[-6]) - 1) * 100 if len(close) > 6 else 0
        )
        self.ret20d_pct = (
            (self.price / float(close.iloc[-21]) - 1) * 100 if len(close) > 21 else 0
        )
        avg10 = float(volume.tail(11).iloc[:-1].mean()) if len(volume) > 1 else 0
        today = float(volume.iloc[-1])
        self.rvol = today / avg10 if avg10 else 1.0

    def _dividend_days(self) -> int | None:
        cal = self.calendar or {}
        if not isinstance(cal, dict):
            return None
        raw = cal.get("Ex-Dividend Date") or cal.get("Dividend Date")
        dates: list[date] = []
        if isinstance(raw, list):
            for d in raw:
                if isinstance(d, datetime):
                    dates.append(d.date())
                elif hasattr(d, "year"):
                    dates.append(d)
        elif raw is not None:
            if isinstance(raw, datetime):
                dates.append(raw.date())
            elif hasattr(raw, "year"):
                dates.append(raw)
        if not dates:
            return None
        today = datetime.now(timezone.utc).date()
        future = [d for d in dates if d >= today]
        if not future:
            return None
        return (min(future) - today).days

    def metric(self, key: str, default=None):
        return self.info.get(key, default)