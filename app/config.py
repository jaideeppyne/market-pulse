from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"


def load_config() -> dict[str, Any]:
    """Load config.yaml and allow environment variable overrides for easy PaaS hosting.

    Supported overrides (set as env vars):
      - PORT (int)          → server.port
      - DB_PATH (str)       → hint for persistent disk location
      - HOT_SCORE_THRESHOLD → scanner.hot_score_threshold
      - PRICE_SCAN_INTERVAL_SEC → scanner.price_scan_interval_sec
    """
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # Common PaaS / container override (Railway, Render, Fly, etc. inject PORT)
    if port := os.getenv("PORT"):
        cfg.setdefault("server", {})["port"] = int(port)

    # Quick tuning for public instances (reduce cost / rate limit pressure)
    if hot := os.getenv("HOT_SCORE_THRESHOLD"):
        cfg.setdefault("scanner", {})["hot_score_threshold"] = float(hot)
    if interval := os.getenv("PRICE_SCAN_INTERVAL_SEC"):
        cfg.setdefault("scanner", {})["price_scan_interval_sec"] = int(interval)

    if db_path := os.getenv("DB_PATH"):
        cfg["_db_path_hint"] = db_path

    return cfg
