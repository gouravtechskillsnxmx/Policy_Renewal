# db.py
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "crm.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS clients(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        notes TEXT
    )""",
    """
    CREATE TABLE IF NOT EXISTS policies(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        policy_no TEXT,
        insurer TEXT,
        policy_type TEXT,
        issued_date TEXT,
        expiry_date TEXT,
        premium REAL,
        status TEXT DEFAULT 'Active',
        notes TEXT,
        FOREIGN KEY(client_id) REFERENCES clients(id)
    )"""
]

def init(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for s in SCHEMA: cur.execute(s)
    conn.commit(); conn.close()

def get_conn(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
