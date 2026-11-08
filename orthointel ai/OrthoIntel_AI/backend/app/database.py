import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv("DATABASE_PATH", str(ROOT / "backend" / "orthointel.db")))
if not DB_PATH.is_absolute():
    DB_PATH = ROOT / DB_PATH

@contextmanager
def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT, review TEXT NOT NULL,
            product TEXT DEFAULT 'Unspecified', region TEXT DEFAULT 'Unknown',
            source TEXT DEFAULT 'Manual', rating REAL, sentiment TEXT,
            sentiment_score REAL, pillars TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, region TEXT NOT NULL,
            product TEXT NOT NULL, sales REAL NOT NULL, units_sold REAL DEFAULT 0,
            returns REAL DEFAULT 0, cost REAL DEFAULT 0, channel TEXT DEFAULT 'Unknown',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS competitor_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, competitor TEXT NOT NULL,
            product TEXT NOT NULL, region TEXT NOT NULL, status TEXT NOT NULL,
            source TEXT DEFAULT 'Manual observation', observed_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS factory_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, product TEXT NOT NULL,
            issue TEXT NOT NULL, recommendation TEXT NOT NULL, priority TEXT DEFAULT 'Medium',
            status TEXT DEFAULT 'Open', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT, action TEXT NOT NULL,
            details TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """)
