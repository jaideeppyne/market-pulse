#!/usr/bin/env python3
"""
validate_weights.py — turn the hand-tuned scoring weights into something measurable.

The app stores historical scan_snapshots (symbol, market, score, payload JSON,
created_at). Each payload carries metrics.price, metrics.buy_score and
metrics.quality_score. Forward returns are NOT stored directly, so this script
reconstructs them by joining each snapshot of a symbol to a LATER snapshot of the
SAME symbol (the nearest one at least `--horizon-hours` ahead) and computing the
realized price move between them.

It then asks the only question that matters for the weights:
    do higher buy_score / quality_score snapshots actually precede higher
    forward returns?

Output: per score-band (and per tier, inferred from the top weighted factor)
mean forward return, hit-rate (% positive), count, plus a rank correlation
(Spearman, computed without scipy). Robust to thin data — it just prints clear
"insufficient data" notes rather than crashing.

SAFETY: never touches the live DB. Point --db at a COPY. The convenience flow is:
    cp data/market_pulse.db /tmp/mp_copy.db
    python3 scripts/validate_weights.py --db /tmp/mp_copy.db
If --db is omitted it makes its own copy of data/market_pulse.db into a temp file.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sqlite3
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "data" / "market_pulse.db"


# ----------------------------------------------------------------------------- helpers

def _parse_ts(ts: str) -> float | None:
    """Best-effort parse of stored created_at into epoch seconds."""
    if not ts:
        return None
    ts = ts.strip().replace("T", " ")
    if ts.endswith("Z"):
        ts = ts[:-1]
    # drop timezone offset if present, keep it simple/comparable
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(ts[:26], fmt).timestamp()
        except ValueError:
            continue
    # try fromisoformat as a fallback (handles offsets)
    try:
        return datetime.fromisoformat(ts).timestamp()
    except Exception:
        return None


def _spearman(pairs: list[tuple[float, float]]) -> float | None:
    """Spearman rank correlation without scipy. None if not enough data."""
    n = len(pairs)
    if n < 5:
        return None

    def rank(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(values):
            j = i
            while j + 1 < len(values) and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0  # 1-based average rank for ties
            for k in range(i, j + 1):
                ranks[order[k]] = avg
            i = j + 1
        return ranks

    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    rx = rank(xs)
    ry = rank(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    vy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if vx == 0 or vy == 0:
        return None
    return cov / (vx * vy)


def _band(score: float) -> str:
    if score >= 80:
        return "80-100"
    if score >= 70:
        return "70-79"
    if score >= 60:
        return "60-69"
    if score >= 50:
        return "50-59"
    return "<50"


_BAND_ORDER = ["<50", "50-59", "60-69", "70-79", "80-100"]


# ----------------------------------------------------------------------------- load

class Obs:
    __slots__ = ("buy", "quality", "tier", "fwd_ret")

    def __init__(self, buy, quality, tier, fwd_ret):
        self.buy = buy
        self.quality = quality
        self.tier = tier
        self.fwd_ret = fwd_ret


def load_snapshots(db_path: Path) -> dict[str, list[dict]]:
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    cur = con.execute(
        "SELECT symbol, score, payload, created_at FROM scan_snapshots "
        "ORDER BY symbol, created_at"
    )
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    rows = 0
    bad = 0
    for r in cur:
        rows += 1
        try:
            payload = json.loads(r["payload"] or "{}")
        except Exception:
            bad += 1
            continue
        m = payload.get("metrics") or {}
        price = m.get("price")
        if price in (None, 0):
            continue
        ts = _parse_ts(r["created_at"])
        if ts is None:
            continue
        buy = m.get("buy_score")
        if buy is None:
            buy = payload.get("buy_score")
        quality = m.get("quality_score")
        if quality is None:
            quality = payload.get("quality_score")
        tier = None
        top = m.get("top_weighted_factors") or []
        if top and isinstance(top[0], dict):
            tier = top[0].get("tier")
        by_symbol[r["symbol"]].append(
            {
                "ts": ts,
                "price": float(price),
                "buy": float(buy) if buy is not None else None,
                "quality": float(quality) if quality is not None else None,
                "tier": tier,
            }
        )
    con.close()
    print(f"  loaded {rows} snapshot rows ({bad} unparseable payloads)")
    return by_symbol


def build_observations(
    by_symbol: dict[str, list[dict]], horizon_hours: float
) -> list[Obs]:
    """For each snapshot, find the nearest later snapshot of the same symbol at
    least horizon_hours ahead; forward return = pct price change to it."""
    horizon_s = horizon_hours * 3600.0
    obs: list[Obs] = []
    symbols_used = 0
    for symbol, snaps in by_symbol.items():
        snaps.sort(key=lambda s: s["ts"])
        if len(snaps) < 2:
            continue
        used_any = False
        for i, s in enumerate(snaps):
            if s["buy"] is None and s["quality"] is None:
                continue
            target = None
            for j in range(i + 1, len(snaps)):
                if snaps[j]["ts"] - s["ts"] >= horizon_s:
                    target = snaps[j]
                    break
            if target is None:
                continue
            if s["price"] <= 0:
                continue
            fwd = (target["price"] - s["price"]) / s["price"] * 100.0
            # guard against absurd values from bad data / splits
            if abs(fwd) > 60.0:
                continue
            obs.append(Obs(s["buy"], s["quality"], s["tier"], fwd))
            used_any = True
        if used_any:
            symbols_used += 1
    print(f"  built {len(obs)} (snapshot -> forward-return) observations "
          f"across {symbols_used} symbols")
    return obs


# ----------------------------------------------------------------------------- report

def _fmt_row(label, count, mean_ret, hit_rate):
    return f"  {label:<10} n={count:<6} mean_fwd_ret={mean_ret:+6.2f}%  hit_rate={hit_rate:5.1f}%"


def report_by_band(obs: list[Obs], score_attr: str, title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    buckets: dict[str, list[float]] = defaultdict(list)
    pairs: list[tuple[float, float]] = []
    for o in obs:
        score = getattr(o, score_attr)
        if score is None:
            continue
        buckets[_band(score)].append(o.fwd_ret)
        pairs.append((score, o.fwd_ret))

    if not pairs:
        print("  (no observations with this score — insufficient data)")
        return

    for band in _BAND_ORDER:
        rets = buckets.get(band)
        if not rets:
            continue
        mean_ret = sum(rets) / len(rets)
        hit = sum(1 for r in rets if r > 0) / len(rets) * 100.0
        print(_fmt_row(band, len(rets), mean_ret, hit))

    rho = _spearman(pairs)
    if rho is None:
        print("  Spearman corr(score, fwd_ret): n/a (need >=5 obs / variance)")
    else:
        verdict = (
            "positive edge" if rho > 0.05
            else "negative (weights inverted?)" if rho < -0.05
            else "no measurable edge"
        )
        print(f"  Spearman corr(score, fwd_ret) = {rho:+.3f}  -> {verdict}")

    # monotonicity check across populated bands
    band_means = [
        (b, sum(buckets[b]) / len(buckets[b]))
        for b in _BAND_ORDER
        if buckets.get(b)
    ]
    if len(band_means) >= 2:
        ascending = all(
            band_means[i][1] <= band_means[i + 1][1] + 1e-9
            for i in range(len(band_means) - 1)
        )
        print(f"  band means monotonically increasing with score: {ascending}")


def report_by_tier(obs: list[Obs]) -> None:
    title = "Forward return by inferred top-factor TIER"
    print(f"\n{title}")
    print("-" * len(title))
    buckets: dict[str, list[float]] = defaultdict(list)
    for o in obs:
        if o.tier:
            buckets[o.tier].append(o.fwd_ret)
    if not buckets:
        print("  (no tier info in snapshots — insufficient data)")
        return
    tier_order = ["S+", "S", "A", "B", "C", "D"]
    for t in tier_order + sorted(k for k in buckets if k not in tier_order):
        rets = buckets.get(t)
        if not rets:
            continue
        mean_ret = sum(rets) / len(rets)
        hit = sum(1 for r in rets if r > 0) / len(rets) * 100.0
        print(_fmt_row(t, len(rets), mean_ret, hit))


# ----------------------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to a COPY of market_pulse.db. If omitted, a temp copy is made.",
    )
    ap.add_argument(
        "--horizon-hours",
        type=float,
        default=12.0,
        help="Minimum forward gap (hours) between a snapshot and its outcome.",
    )
    args = ap.parse_args(argv)

    print("=" * 64)
    print("  MARKET PULSE — WEIGHT / EDGE VALIDATION HARNESS")
    print("=" * 64)

    cleanup = None
    if args.db is None:
        if not DEFAULT_DB.exists():
            print(f"  ! no DB found at {DEFAULT_DB}; nothing to validate.")
            return 1
        tmp = Path(tempfile.mkdtemp()) / "mp_copy.db"
        print(f"  copying {DEFAULT_DB} -> {tmp} (never touching the original)")
        shutil.copy2(DEFAULT_DB, tmp)
        db_path = tmp
        cleanup = tmp
    else:
        db_path = args.db
        if not db_path.exists():
            print(f"  ! DB copy not found: {db_path}")
            return 1
        print(f"  using DB copy: {db_path}")

    print(f"  forward horizon: >= {args.horizon_hours}h\n")

    try:
        by_symbol = load_snapshots(db_path)
        if not by_symbol:
            print("  ! no usable snapshots — insufficient data.")
            return 0
        obs = build_observations(by_symbol, args.horizon_hours)
        if len(obs) < 5:
            print("\n  ! Fewer than 5 (snapshot->return) pairs — data is too thin")
            print("    to draw conclusions. Re-run after more scan history accrues.")
            # still print whatever we have
        report_by_band(obs, "buy", "Forward return by BUY_SCORE band")
        report_by_band(obs, "quality", "Forward return by QUALITY_SCORE band")
        report_by_tier(obs)

        print("\n" + "=" * 64)
        print("  INTERPRETATION")
        print("=" * 64)
        print("  - Positive Spearman + bands rising with score = weights have")
        print("    real, measurable forward edge.")
        print("  - Flat / negative = the hand-tuned tier multipliers are not")
        print("    yet validated by realized moves (expected when history is")
        print("    only a few days deep, as it is here).")
    finally:
        if cleanup is not None:
            try:
                shutil.rmtree(cleanup.parent, ignore_errors=True)
            except Exception:
                pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
