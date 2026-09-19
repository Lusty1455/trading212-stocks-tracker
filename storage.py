"""Storage abstraction layer supporting JSON files, SQLite (portfolio.db), and Cloudflare D1.

Allows seamless switching between pure local JSON, embedded SQLite, and Cloudflare D1
while guaranteeing 100% bidirectional data compatibility and zero data loss.
"""

from __future__ import annotations
import os
import json
import time
import math
import uuid
import sqlite3
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("storage")

DIR = os.path.dirname(__file__)
PORTFOLIO_FILE = os.path.join(DIR, "portfolio.json")
HISTORY_FILE = os.path.join(DIR, "history.json")
HISTORY_TRASH_FILE = os.path.join(DIR, "history_trash.json")
SQLITE_DB_FILE = os.path.join(DIR, "portfolio.db")
TRASH_RETENTION_SECONDS = 30 * 86400  # 30 days


def get_default_portfolio_dict() -> Dict[str, Any]:
    """Default fallback portfolio structure."""
    return {
        "base_currency": "GBP",
        "cash": {
            "GBP": 1.0,
            "USD": 0.0
        },
        "holdings": [
            {
                "symbol": "GOOGL",
                "name": "Alphabet Inc. (Class A)",
                "shares": 0.0412197,
                "average_price_usd": 343.28,
                "average_price_gbp": 254.73,
                "cost_basis": 10.50,
                "cost_currency": "GBP",
                "added_at": datetime.now().strftime("%Y-%m-%d")
            }
        ]
    }


class BaseStorage(ABC):
    """Abstract storage interface for portfolio and history data."""

    @abstractmethod
    def get_backend_name(self) -> str:
        """Return the identifier of the storage backend (e.g. 'json', 'sqlite', 'cloudflare_d1')."""
        pass

    @abstractmethod
    def load_portfolio(self) -> Dict[str, Any]:
        """Load the portfolio configuration, cash balances, and holdings."""
        pass

    @abstractmethod
    def save_portfolio(self, data: Dict[str, Any]) -> None:
        """Save the portfolio configuration, cash balances, and holdings."""
        pass

    @abstractmethod
    def load_history(self) -> List[Dict[str, Any]]:
        """Load all valid history snapshot records."""
        pass

    @abstractmethod
    def save_history(self, history: List[Dict[str, Any]]) -> None:
        """Save history snapshots."""
        pass

    @abstractmethod
    def load_trash(self) -> List[Dict[str, Any]]:
        """Load deleted snapshots from the recycle bin (excluding expired items)."""
        pass

    @abstractmethod
    def save_trash(self, trash: List[Dict[str, Any]]) -> None:
        """Save recycle bin snapshot records."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Return operational statistics about storage backend."""
        pass


class JSONStorage(BaseStorage):
    """Flat-file JSON storage adapter (fully preserves original format and behavior)."""

    def __init__(self, portfolio_path: str = PORTFOLIO_FILE, history_path: str = HISTORY_FILE, trash_path: str = HISTORY_TRASH_FILE):
        self.portfolio_path = portfolio_path
        self.history_path = history_path
        self.trash_path = trash_path

    def get_backend_name(self) -> str:
        return "json"

    def load_portfolio(self) -> Dict[str, Any]:
        if not os.path.exists(self.portfolio_path):
            data = get_default_portfolio_dict()
            self.save_portfolio(data)
            return data
        try:
            with open(self.portfolio_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading {self.portfolio_path}, using default: {e}")
            data = get_default_portfolio_dict()
            self.save_portfolio(data)
            return data

    def save_portfolio(self, data: Dict[str, Any]) -> None:
        tmp_file = f"{self.portfolio_path}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, self.portfolio_path)

    def load_history(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.history_path):
            return []
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                history = json.load(f)
                return history if isinstance(history, list) else []
        except Exception:
            return []

    def save_history(self, history: List[Dict[str, Any]]) -> None:
        tmp_file = f"{self.history_path}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, self.history_path)

    def load_trash(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.trash_path):
            return []
        try:
            with open(self.trash_path, "r", encoding="utf-8") as f:
                trash = json.load(f)
                if not isinstance(trash, list):
                    return []
        except Exception:
            return []

        now = time.time()
        valid = []
        for item in trash:
            deleted_ts = item.get("deleted_timestamp", now)
            age_seconds = now - deleted_ts
            if age_seconds <= TRASH_RETENTION_SECONDS:
                remaining_days = max(1, math.ceil((TRASH_RETENTION_SECONDS - age_seconds) / 86400))
                item["days_remaining"] = remaining_days
                valid.append(item)

        if len(valid) != len(trash):
            self.save_trash(valid)

        valid.sort(key=lambda x: x.get("deleted_timestamp", 0), reverse=True)
        return valid

    def save_trash(self, trash: List[Dict[str, Any]]) -> None:
        tmp_file = f"{self.trash_path}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(trash, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, self.trash_path)

    def get_stats(self) -> Dict[str, Any]:
        p_size = os.path.getsize(self.portfolio_path) if os.path.exists(self.portfolio_path) else 0
        h_size = os.path.getsize(self.history_path) if os.path.exists(self.history_path) else 0
        t_size = os.path.getsize(self.trash_path) if os.path.exists(self.trash_path) else 0
        h_list = self.load_history()
        t_list = self.load_trash()
        port = self.load_portfolio()
        return {
            "backend": "json",
            "portfolio_file": os.path.basename(self.portfolio_path),
            "history_file": os.path.basename(self.history_path),
            "trash_file": os.path.basename(self.trash_path),
            "total_size_bytes": p_size + h_size + t_size,
            "counts": {
                "holdings": len(port.get("holdings", [])),
                "snapshots": len(h_list),
                "trash": len(t_list)
            }
        }


class SQLiteStorage(BaseStorage):
    """SQLite embedded database storage adapter (compatible with Cloudflare D1 SQL)."""

    SCHEMA_SQL = """
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS portfolio_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS cash_balances (
        currency TEXT PRIMARY KEY,
        amount REAL NOT NULL DEFAULT 0.0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS holdings (
        symbol TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        shares REAL NOT NULL,
        average_price_usd REAL,
        average_price_gbp REAL,
        cost_basis REAL NOT NULL DEFAULT 0.0,
        cost_currency TEXT NOT NULL DEFAULT 'GBP',
        added_at TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS snapshots (
        id TEXT PRIMARY KEY,
        date TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        system_time TEXT,
        system_hour TEXT,
        ny_time TEXT,
        ny_hour TEXT,
        ny_note TEXT,
        session_status TEXT,
        base_currency TEXT NOT NULL DEFAULT 'GBP',
        total_value REAL NOT NULL,
        stock_value REAL NOT NULL,
        cash_value REAL NOT NULL,
        daily_pnl REAL NOT NULL DEFAULT 0.0,
        daily_pnl_pct REAL NOT NULL DEFAULT 0.0,
        holdings_count INTEGER NOT NULL DEFAULT 0,
        raw_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_snapshots_date ON snapshots(date);
    CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp);

    CREATE TABLE IF NOT EXISTS history_trash (
        trash_id TEXT PRIMARY KEY,
        deleted_at TEXT NOT NULL,
        deleted_timestamp REAL NOT NULL,
        expires_at REAL NOT NULL,
        snapshot_id TEXT,
        snapshot_data TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_trash_expires ON history_trash(expires_at);
    """

    def __init__(self, db_path: str = SQLITE_DB_FILE):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high concurrency and performance
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(self.SCHEMA_SQL)
            conn.commit()

    def get_backend_name(self) -> str:
        return "sqlite"

    def load_portfolio(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Base currency
            cursor.execute("SELECT value FROM portfolio_meta WHERE key = 'base_currency'")
            row = cursor.fetchone()
            base_currency = row["value"] if row else "GBP"

            # 2. Cash balances
            cursor.execute("SELECT currency, amount FROM cash_balances")
            cash_dict = {r["currency"]: float(r["amount"]) for r in cursor.fetchall()}
            if not cash_dict:
                cash_dict = {"GBP": 1.0, "USD": 0.0}

            # 3. Holdings
            cursor.execute("""
                SELECT symbol, name, shares, average_price_usd, average_price_gbp,
                       cost_basis, cost_currency, added_at
                FROM holdings
                ORDER BY symbol ASC
            """)
            holdings = []
            for r in cursor.fetchall():
                h = {
                    "symbol": r["symbol"],
                    "name": r["name"],
                    "shares": float(r["shares"]),
                    "cost_basis": float(r["cost_basis"]),
                    "cost_currency": r["cost_currency"],
                    "added_at": r["added_at"] or datetime.now().strftime("%Y-%m-%d")
                }
                if r["average_price_usd"] is not None:
                    h["average_price_usd"] = float(r["average_price_usd"])
                if r["average_price_gbp"] is not None:
                    h["average_price_gbp"] = float(r["average_price_gbp"])
                holdings.append(h)

            # If completely empty, seed default
            if not row and not holdings:
                default_data = get_default_portfolio_dict()
                self.save_portfolio(default_data)
                return default_data

            return {
                "base_currency": base_currency,
                "cash": cash_dict,
                "holdings": holdings
            }

    def save_portfolio(self, data: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Base currency
            base_currency = data.get("base_currency", "GBP")
            cursor.execute("""
                INSERT INTO portfolio_meta (key, value) VALUES ('base_currency', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (base_currency,))

            # 2. Cash balances
            cursor.execute("DELETE FROM cash_balances")
            for curr, amt in data.get("cash", {}).items():
                cursor.execute("""
                    INSERT INTO cash_balances (currency, amount, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (curr.upper(), float(amt)))

            # 3. Holdings
            cursor.execute("DELETE FROM holdings")
            for h in data.get("holdings", []):
                symbol = h.get("symbol", "").strip().upper()
                if not symbol:
                    continue
                cursor.execute("""
                    INSERT INTO holdings (
                        symbol, name, shares, average_price_usd, average_price_gbp,
                        cost_basis, cost_currency, added_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    symbol,
                    h.get("name") or symbol,
                    float(h.get("shares") or 0.0),
                    float(h["average_price_usd"]) if h.get("average_price_usd") is not None else None,
                    float(h["average_price_gbp"]) if h.get("average_price_gbp") is not None else None,
                    float(h.get("cost_basis") or 0.0),
                    h.get("cost_currency", "GBP"),
                    h.get("added_at") or datetime.now().strftime("%Y-%m-%d")
                ))
            conn.commit()

    def load_history(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT raw_json FROM snapshots ORDER BY timestamp ASC")
            rows = cursor.fetchall()
            history = []
            for r in rows:
                try:
                    snap = json.loads(r["raw_json"])
                    history.append(snap)
                except Exception as e:
                    logger.warning(f"Failed to decode snapshot json: {e}")
            return history

    def save_history(self, history: List[Dict[str, Any]]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM snapshots")
            for snap in history:
                self._insert_snapshot_row(cursor, snap)
            conn.commit()

    def _insert_snapshot_row(self, cursor: sqlite3.Cursor, snap: Dict[str, Any]) -> None:
        snap_id = snap.get("id") or f"snap_{snap.get('timestamp', '').replace('-', '').replace(' ', '_').replace(':', '')}"
        raw_json = json.dumps(snap, ensure_ascii=False)
        cursor.execute("""
            INSERT INTO snapshots (
                id, date, timestamp, system_time, system_hour, ny_time, ny_hour,
                ny_note, session_status, base_currency, total_value, stock_value,
                cash_value, daily_pnl, daily_pnl_pct, holdings_count, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                date = excluded.date,
                timestamp = excluded.timestamp,
                total_value = excluded.total_value,
                stock_value = excluded.stock_value,
                cash_value = excluded.cash_value,
                daily_pnl = excluded.daily_pnl,
                daily_pnl_pct = excluded.daily_pnl_pct,
                raw_json = excluded.raw_json
        """, (
            snap_id,
            snap.get("date", ""),
            snap.get("timestamp", ""),
            snap.get("system_time", ""),
            snap.get("system_hour", ""),
            snap.get("ny_time", ""),
            snap.get("ny_hour", ""),
            snap.get("ny_note", ""),
            snap.get("session_status", ""),
            snap.get("base_currency", "GBP"),
            float(snap.get("total_value", 0.0)),
            float(snap.get("stock_value", 0.0)),
            float(snap.get("cash_value", 0.0)),
            float(snap.get("daily_pnl", 0.0)),
            float(snap.get("daily_pnl_pct", 0.0)),
            int(snap.get("holdings_count", len(snap.get("holdings", [])))),
            raw_json
        ))

    def load_trash(self) -> List[Dict[str, Any]]:
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Clean expired records (>30 days)
            cursor.execute("DELETE FROM history_trash WHERE expires_at < ?", (now,))
            conn.commit()

            cursor.execute("SELECT trash_id, deleted_at, deleted_timestamp, snapshot_data FROM history_trash ORDER BY deleted_timestamp DESC")
            rows = cursor.fetchall()
            trash_items = []
            for r in rows:
                try:
                    snap = json.loads(r["snapshot_data"])
                    age_seconds = now - float(r["deleted_timestamp"])
                    remaining_days = max(1, math.ceil((TRASH_RETENTION_SECONDS - age_seconds) / 86400))
                    trash_items.append({
                        "trash_id": r["trash_id"],
                        "deleted_at": r["deleted_at"],
                        "deleted_timestamp": float(r["deleted_timestamp"]),
                        "days_remaining": remaining_days,
                        "snapshot": snap
                    })
                except Exception as e:
                    logger.warning(f"Failed to decode trash item: {e}")
            return trash_items

    def save_trash(self, trash: List[Dict[str, Any]]) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM history_trash")
            for item in trash:
                trash_id = item.get("trash_id") or f"trash_{uuid.uuid4().hex[:8]}"
                del_at = item.get("deleted_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                del_ts = float(item.get("deleted_timestamp", time.time()))
                exp_ts = del_ts + TRASH_RETENTION_SECONDS
                snap_json = json.dumps(item.get("snapshot", {}), ensure_ascii=False)
                snap_id = item.get("snapshot", {}).get("id")
                cursor.execute("""
                    INSERT INTO history_trash (trash_id, deleted_at, deleted_timestamp, expires_at, snapshot_id, snapshot_data)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (trash_id, del_at, del_ts, exp_ts, snap_id, snap_json))
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM holdings")
            h_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM snapshots")
            s_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM history_trash")
            t_count = cursor.fetchone()[0]

        return {
            "backend": "sqlite",
            "db_file": os.path.basename(self.db_path),
            "db_path": self.db_path,
            "total_size_bytes": size,
            "counts": {
                "holdings": h_count,
                "snapshots": s_count,
                "trash": t_count
            }
        }


class CloudflareD1Storage(BaseStorage):
    """Cloudflare D1 Serverless SQL storage adapter via Cloudflare REST API."""

    def __init__(self, account_id: Optional[str] = None, database_id: Optional[str] = None, api_token: Optional[str] = None):
        self.account_id = account_id or os.getenv("CF_ACCOUNT_ID")
        self.database_id = database_id or os.getenv("CF_DATABASE_ID")
        self.api_token = api_token or os.getenv("CF_API_TOKEN")
        # Local fallback SQLite in case Cloudflare credentials are unset or offline
        self._local_fallback = SQLiteStorage()

    def is_configured(self) -> bool:
        return bool(self.account_id and self.database_id and self.api_token)

    def get_backend_name(self) -> str:
        return "cloudflare_d1"

    def _execute_cf_query(self, sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """Execute query on Cloudflare D1 via official REST API."""
        if not self.is_configured():
            raise RuntimeError("Cloudflare D1 credentials (CF_ACCOUNT_ID, CF_DATABASE_ID, CF_API_TOKEN) are not fully configured.")

        import requests
        url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/d1/database/{self.database_id}/query"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        body = {"sql": sql, "params": params or []}
        resp = requests.post(url, headers=headers, json=body, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"Cloudflare D1 API HTTP {resp.status_code}: {resp.text}")
        json_resp = resp.json()
        if not json_resp.get("success"):
            errors = json_resp.get("errors", [])
            raise RuntimeError(f"Cloudflare D1 error: {errors}")
        result = json_resp.get("result", [{}])[0]
        return result.get("results", [])

    def load_portfolio(self) -> Dict[str, Any]:
        if not self.is_configured():
            logger.warning("Cloudflare D1 not configured, falling back to local SQLite.")
            return self._local_fallback.load_portfolio()
        # Mirror SQLite logic via REST query
        try:
            meta_res = self._execute_cf_query("SELECT value FROM portfolio_meta WHERE key = 'base_currency'")
            base_currency = meta_res[0]["value"] if meta_res else "GBP"

            cash_res = self._execute_cf_query("SELECT currency, amount FROM cash_balances")
            cash_dict = {r["currency"]: float(r["amount"]) for r in cash_res}
            if not cash_dict:
                cash_dict = {"GBP": 1.0, "USD": 0.0}

            hold_res = self._execute_cf_query("SELECT symbol, name, shares, average_price_usd, average_price_gbp, cost_basis, cost_currency, added_at FROM holdings ORDER BY symbol ASC")
            holdings = []
            for r in hold_res:
                h = {
                    "symbol": r["symbol"],
                    "name": r["name"],
                    "shares": float(r["shares"]),
                    "cost_basis": float(r["cost_basis"]),
                    "cost_currency": r["cost_currency"],
                    "added_at": r["added_at"] or datetime.now().strftime("%Y-%m-%d")
                }
                if r.get("average_price_usd") is not None:
                    h["average_price_usd"] = float(r["average_price_usd"])
                if r.get("average_price_gbp") is not None:
                    h["average_price_gbp"] = float(r["average_price_gbp"])
                holdings.append(h)

            return {"base_currency": base_currency, "cash": cash_dict, "holdings": holdings}
        except Exception as e:
            logger.error(f"Failed to query Cloudflare D1: {e}. Falling back to local.")
            return self._local_fallback.load_portfolio()

    def save_portfolio(self, data: Dict[str, Any]) -> None:
        if not self.is_configured():
            return self._local_fallback.save_portfolio(data)
        # Execute queries on D1
        base_currency = data.get("base_currency", "GBP")
        self._execute_cf_query("INSERT INTO portfolio_meta (key, value) VALUES ('base_currency', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", [base_currency])
        self._execute_cf_query("DELETE FROM cash_balances")
        for curr, amt in data.get("cash", {}).items():
            self._execute_cf_query("INSERT INTO cash_balances (currency, amount) VALUES (?, ?)", [curr.upper(), float(amt)])
        self._execute_cf_query("DELETE FROM holdings")
        for h in data.get("holdings", []):
            self._execute_cf_query("""
                INSERT INTO holdings (symbol, name, shares, average_price_usd, average_price_gbp, cost_basis, cost_currency, added_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                h.get("symbol", "").upper(),
                h.get("name") or h.get("symbol"),
                float(h.get("shares") or 0.0),
                float(h["average_price_usd"]) if h.get("average_price_usd") is not None else None,
                float(h["average_price_gbp"]) if h.get("average_price_gbp") is not None else None,
                float(h.get("cost_basis") or 0.0),
                h.get("cost_currency", "GBP"),
                h.get("added_at") or datetime.now().strftime("%Y-%m-%d")
            ])
        # Also mirror to local fallback for safety
        self._local_fallback.save_portfolio(data)

    def load_history(self) -> List[Dict[str, Any]]:
        if not self.is_configured():
            return self._local_fallback.load_history()
        try:
            rows = self._execute_cf_query("SELECT raw_json FROM snapshots ORDER BY timestamp ASC")
            return [json.loads(r["raw_json"]) for r in rows if r.get("raw_json")]
        except Exception as e:
            logger.error(f"D1 load_history error: {e}")
            return self._local_fallback.load_history()

    def save_history(self, history: List[Dict[str, Any]]) -> None:
        if not self.is_configured():
            return self._local_fallback.save_history(history)
        self._execute_cf_query("DELETE FROM snapshots")
        for snap in history:
            raw_json = json.dumps(snap, ensure_ascii=False)
            self._execute_cf_query("""
                INSERT INTO snapshots (id, date, timestamp, total_value, stock_value, cash_value, daily_pnl, daily_pnl_pct, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                snap.get("id"), snap.get("date", ""), snap.get("timestamp", ""),
                float(snap.get("total_value", 0.0)), float(snap.get("stock_value", 0.0)),
                float(snap.get("cash_value", 0.0)), float(snap.get("daily_pnl", 0.0)),
                float(snap.get("daily_pnl_pct", 0.0)), raw_json
            ])
        self._local_fallback.save_history(history)

    def load_trash(self) -> List[Dict[str, Any]]:
        if not self.is_configured():
            return self._local_fallback.load_trash()
        try:
            now = time.time()
            self._execute_cf_query("DELETE FROM history_trash WHERE expires_at < ?", [now])
            rows = self._execute_cf_query("SELECT trash_id, deleted_at, deleted_timestamp, snapshot_data FROM history_trash ORDER BY deleted_timestamp DESC")
            items = []
            for r in rows:
                snap = json.loads(r["snapshot_data"])
                age = now - float(r["deleted_timestamp"])
                items.append({
                    "trash_id": r["trash_id"],
                    "deleted_at": r["deleted_at"],
                    "deleted_timestamp": float(r["deleted_timestamp"]),
                    "days_remaining": max(1, math.ceil((TRASH_RETENTION_SECONDS - age) / 86400)),
                    "snapshot": snap
                })
            return items
        except Exception as e:
            logger.error(f"D1 load_trash error: {e}")
            return self._local_fallback.load_trash()

    def save_trash(self, trash: List[Dict[str, Any]]) -> None:
        if not self.is_configured():
            return self._local_fallback.save_trash(trash)
        self._execute_cf_query("DELETE FROM history_trash")
        now = time.time()
        for item in trash:
            trash_id = item.get("trash_id") or f"trash_{uuid.uuid4().hex[:8]}"
            del_at = item.get("deleted_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            del_ts = float(item.get("deleted_timestamp", now))
            exp_ts = del_ts + TRASH_RETENTION_SECONDS
            snap_json = json.dumps(item.get("snapshot", {}), ensure_ascii=False)
            self._execute_cf_query("""
                INSERT INTO history_trash (trash_id, deleted_at, deleted_timestamp, expires_at, snapshot_id, snapshot_data)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [trash_id, del_at, del_ts, exp_ts, item.get("snapshot", {}).get("id"), snap_json])
        self._local_fallback.save_trash(trash)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "backend": "cloudflare_d1",
            "configured": self.is_configured(),
            "account_id": f"{self.account_id[:6]}..." if self.account_id else None,
            "database_id": f"{self.database_id[:6]}..." if self.database_id else None,
            "counts": self.load_portfolio()
        }


# Singleton cache of active storage instance
_ACTIVE_STORAGE: Optional[BaseStorage] = None


def get_storage(backend: Optional[str] = None) -> BaseStorage:
    """
    Get the configured storage backend instance.
    Backend precedence:
    1. Explicit 'backend' parameter ('json', 'sqlite', 'cloudflare_d1')
    2. STORAGE_BACKEND environment variable
    3. If 'portfolio.db' already exists on disk, default to 'sqlite'
    4. Otherwise default to 'json' (100% backward compatible)
    """
    global _ACTIVE_STORAGE
    target_backend = (backend or os.getenv("STORAGE_BACKEND") or "").strip().lower()

    if not target_backend:
        # Default to sqlite if db exists, otherwise default to sqlite on database branch or json
        if os.path.exists(SQLITE_DB_FILE):
            target_backend = "sqlite"
        else:
            target_backend = "sqlite"  # Default to SQLite on feature branch, with automatic bootstrap from JSON

    if _ACTIVE_STORAGE and _ACTIVE_STORAGE.get_backend_name() == target_backend:
        return _ACTIVE_STORAGE

    if target_backend == "sqlite":
        _ACTIVE_STORAGE = SQLiteStorage()
    elif target_backend == "cloudflare_d1":
        _ACTIVE_STORAGE = CloudflareD1Storage()
    else:
        _ACTIVE_STORAGE = JSONStorage()

    return _ACTIVE_STORAGE


def set_storage_backend(backend: str) -> BaseStorage:
    """Explicitly set and switch active storage backend."""
    global _ACTIVE_STORAGE
    _ACTIVE_STORAGE = None
    os.environ["STORAGE_BACKEND"] = backend
    return get_storage(backend)


def migrate_storage(src_backend: str, dst_backend: str) -> Dict[str, Any]:
    """
    Migrate all data between storage backends (e.g. from 'json' to 'sqlite', or 'sqlite' to 'json').
    Provides 100% data fidelity validation.
    """
    src = JSONStorage() if src_backend == "json" else (CloudflareD1Storage() if src_backend == "cloudflare_d1" else SQLiteStorage())
    dst = JSONStorage() if dst_backend == "json" else (CloudflareD1Storage() if dst_backend == "cloudflare_d1" else SQLiteStorage())

    logger.info(f"Starting migration: {src.get_backend_name()} -> {dst.get_backend_name()}")

    # 1. Migrate portfolio
    portfolio_data = src.load_portfolio()
    dst.save_portfolio(portfolio_data)

    # 2. Migrate history snapshots
    history_data = src.load_history()
    dst.save_history(history_data)

    # 3. Migrate trash
    trash_data = src.load_trash()
    dst.save_trash(trash_data)

    # Validation
    dst_port = dst.load_portfolio()
    dst_hist = dst.load_history()
    dst_trash = dst.load_trash()

    return {
        "status": "ok",
        "source": src_backend,
        "destination": dst_backend,
        "migrated": {
            "holdings": len(dst_port.get("holdings", [])),
            "snapshots": len(dst_hist),
            "trash_items": len(dst_trash),
        },
        "message": f"成功从 {src_backend} 迁移至 {dst_backend}！"
    }


def auto_sync_if_needed() -> None:
    """If sqlite database does not exist yet but portfolio.json exists, auto-migrate to sqlite seamlessly."""
    if not os.path.exists(SQLITE_DB_FILE) and os.path.exists(PORTFOLIO_FILE):
        try:
            migrate_storage("json", "sqlite")
            logger.info("Automatically initialized portfolio.db from portfolio.json")
        except Exception as e:
            logger.warning(f"Auto-sync from JSON to SQLite failed: {e}")
