"""
회의녹음요약 - SQLite DB 관리
"""
import sqlite3
from datetime import datetime
from config import DB_FILE


def _conn():
    return sqlite3.connect(str(DB_FILE))


def init_database():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS meetings (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at          TEXT,
                file_name           TEXT,
                mp3_local_path      TEXT,
                stt_local_path      TEXT,
                summary_local_path  TEXT,
                stt_text            TEXT,
                summary_text        TEXT,
                drive_mp3_link      TEXT,
                drive_stt_link      TEXT,
                drive_summary_link  TEXT,
                file_size_mb        REAL
            )
        """)
        con.commit()


def save_meeting(**kw) -> int:
    kw.setdefault("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    cols = ", ".join(kw.keys())
    vals = ", ".join("?" * len(kw))
    with _conn() as con:
        cur = con.execute(f"INSERT INTO meetings ({cols}) VALUES ({vals})",
                          list(kw.values()))
        con.commit()
        return cur.lastrowid


def get_all_meetings() -> list:
    with _conn() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT * FROM meetings ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_meeting(mid: int) -> dict:
    with _conn() as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM meetings WHERE id=?", (mid,)
        ).fetchone()
        return dict(row) if row else {}


def update_meeting_summary(mid: int, stt_text=None,
                           summary_text=None, summary_local_path=None):
    sets, vals = [], []
    if stt_text is not None:
        sets.append("stt_text=?");            vals.append(stt_text)
    if summary_text is not None:
        sets.append("summary_text=?");        vals.append(summary_text)
    if summary_local_path is not None:
        sets.append("summary_local_path=?");  vals.append(summary_local_path)
    if not sets:
        return
    vals.append(mid)
    with _conn() as con:
        con.execute(f"UPDATE meetings SET {', '.join(sets)} WHERE id=?", vals)
        con.commit()


def delete_meeting(mid: int):
    with _conn() as con:
        con.execute("DELETE FROM meetings WHERE id=?", (mid,))
        con.commit()
