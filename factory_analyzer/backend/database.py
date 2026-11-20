"""
database.py – SQLite WAL-mode database layer for Factory Efficiency Analyzer.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "output" / "factory.db"


def get_connection() -> sqlite3.Connection:
    """Open and return a WAL-mode SQLite connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create all tables if they don't exist."""
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS workers (
                worker_id TEXT PRIMARY KEY,
                division  TEXT,
                shift     TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id   TEXT PRIMARY KEY,
                created_at   TEXT,
                file_count   INT,
                worker_count INT
            );

            CREATE TABLE IF NOT EXISTS worker_sessions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id   TEXT,
                worker_id    TEXT,
                file_path    TEXT,
                duration_s   REAL,
                sample_count INT,
                parsed_at    TEXT
            );

            CREATE TABLE IF NOT EXISTS metrics (
                worker_session_id   INTEGER PRIMARY KEY,
                mean_acc_mag        REAL,
                mean_gyro_mag       REAL,
                active_ratio        REAL,
                active_duration_s   REAL,
                idle_duration_s     REAL,
                motion_bursts       INT,
                avg_burst_duration_s REAL,
                efficiency_score    REAL
            );
            """
        )


# ── Insert helpers ─────────────────────────────────────────────────────────────

def upsert_worker(conn: sqlite3.Connection, worker_id: str, division: str, shift: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO workers (worker_id, division, shift) VALUES (?,?,?)",
        (worker_id, division, shift),
    )


def insert_session(
    conn: sqlite3.Connection,
    session_id: str,
    created_at: str,
    file_count: int,
    worker_count: int,
) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO sessions (session_id, created_at, file_count, worker_count) VALUES (?,?,?,?)",
        (session_id, created_at, file_count, worker_count),
    )


def insert_worker_session(
    conn: sqlite3.Connection,
    session_id: str,
    worker_id: str,
    file_path: str,
    duration_s: float,
    sample_count: int,
    parsed_at: str,
) -> int:
    cur = conn.execute(
        """INSERT INTO worker_sessions
           (session_id, worker_id, file_path, duration_s, sample_count, parsed_at)
           VALUES (?,?,?,?,?,?)""",
        (session_id, worker_id, file_path, duration_s, sample_count, parsed_at),
    )
    return cur.lastrowid  # type: ignore[return-value]


def insert_metrics(
    conn: sqlite3.Connection,
    worker_session_id: int,
    mean_acc_mag: float,
    mean_gyro_mag: float,
    active_ratio: float,
    active_duration_s: float,
    idle_duration_s: float,
    motion_bursts: int,
    avg_burst_duration_s: float,
    efficiency_score: float,
) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO metrics
           (worker_session_id, mean_acc_mag, mean_gyro_mag, active_ratio,
            active_duration_s, idle_duration_s, motion_bursts,
            avg_burst_duration_s, efficiency_score)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            worker_session_id,
            mean_acc_mag,
            mean_gyro_mag,
            active_ratio,
            active_duration_s,
            idle_duration_s,
            motion_bursts,
            avg_burst_duration_s,
            efficiency_score,
        ),
    )


def get_session_metrics(conn: sqlite3.Connection, session_id: str) -> list[dict]:
    """Return all worker+metrics rows for a given session_id."""
    cur = conn.execute(
        """
        SELECT ws.worker_id, w.division, w.shift,
               ws.duration_s, ws.sample_count,
               m.mean_acc_mag, m.mean_gyro_mag, m.active_ratio,
               m.active_duration_s, m.idle_duration_s,
               m.motion_bursts, m.avg_burst_duration_s, m.efficiency_score
        FROM worker_sessions ws
        JOIN metrics m ON m.worker_session_id = ws.id
        LEFT JOIN workers w ON w.worker_id = ws.worker_id
        WHERE ws.session_id = ?
        ORDER BY m.efficiency_score DESC
        """,
        (session_id,),
    )
    return [dict(row) for row in cur.fetchall()]


def get_all_sessions(conn: sqlite3.Connection) -> list[dict]:
    cur = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC")
    return [dict(row) for row in cur.fetchall()]
