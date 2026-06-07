"""SQLite persistence helpers for DeepMemo."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from typing import Any, Dict, List, Optional, Sequence, Tuple

from backend.scheduler_engine import schedule_next
from tools.utils import question_cache
from tools.utils.config import DATABASE_FILE, ensure_data_dir


DB_NAME = str(DATABASE_FILE)


def _connect() -> sqlite3.Connection:
    ensure_data_dir()
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cur.fetchone() is not None


def _get_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return [row["name"] for row in cur.fetchall()]


def _add_column_if_missing(conn: sqlite3.Connection, table: str, col: str, col_def: str) -> None:
    if col not in set(_get_columns(conn, table)):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")


def create_tables() -> None:
    """Create or lightly migrate all local tables."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS flashcards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL UNIQUE,
                explanation TEXT,
                next_review_date TEXT,
                interval INTEGER DEFAULT 1,
                status TEXT DEFAULT 'learning',
                scheduler_state TEXT
            )
            """
        )

        if _table_exists(conn, "flashcards"):
            _add_column_if_missing(conn, "flashcards", "explanation", "TEXT")
            _add_column_if_missing(conn, "flashcards", "next_review_date", "TEXT")
            _add_column_if_missing(conn, "flashcards", "interval", "INTEGER DEFAULT 1")
            _add_column_if_missing(conn, "flashcards", "status", "TEXT DEFAULT 'learning'")
            _add_column_if_missing(conn, "flashcards", "scheduler_state", "TEXT")

            cols = set(_get_columns(conn, "flashcards"))
            if "content" in cols:
                conn.execute(
                    """
                    UPDATE flashcards
                    SET explanation = COALESCE(explanation, content)
                    WHERE explanation IS NULL OR explanation = ''
                    """
                )
            if "next_review" in cols:
                conn.execute(
                    """
                    UPDATE flashcards
                    SET next_review_date = COALESCE(next_review_date, next_review)
                    WHERE next_review_date IS NULL OR next_review_date = ''
                    """
                )

            today = dt.date.today().isoformat()
            conn.execute(
                """
                UPDATE flashcards
                SET next_review_date = COALESCE(next_review_date, ?)
                WHERE next_review_date IS NULL OR next_review_date = ''
                """,
                (today,),
            )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mistake_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER,
                question TEXT,
                user_answer TEXT,
                feedback TEXT,
                create_time TEXT,
                FOREIGN KEY(card_id) REFERENCES flashcards(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS study_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER,
                result TEXT,
                timestamp TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS study_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                question TEXT NOT NULL,
                question_type TEXT NOT NULL DEFAULT 'open',
                options_json TEXT DEFAULT '[]',
                standard_answer TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def create_table() -> None:
    create_tables()


def add_new_card(topic: str, explanation: str) -> Tuple[bool, str]:
    create_tables()
    today = dt.date.today().isoformat()
    try:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO flashcards (topic, explanation, next_review_date, interval, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (topic.strip(), explanation.strip(), today, 1, "learning"),
            )
            conn.commit()
        return True, "Added successfully"
    except sqlite3.IntegrityError:
        return False, "Topic already exists"


def delete_card(card_id: int) -> None:
    create_tables()
    with _connect() as conn:
        row = conn.execute("SELECT topic FROM flashcards WHERE id = ?", (card_id,)).fetchone()
        topic = row["topic"] if row else None
        conn.execute("DELETE FROM mistake_logs WHERE card_id = ?", (card_id,))
        conn.execute("DELETE FROM study_logs WHERE card_id = ?", (card_id,))
        if topic:
            conn.execute("DELETE FROM custom_questions WHERE topic = ?", (topic,))
        conn.execute("DELETE FROM flashcards WHERE id = ?", (card_id,))
        conn.commit()
    if topic:
        question_cache.remove_questions_by_topic(str(topic))


def get_cards_by_type(view_type: str = "all") -> List[Tuple[Any, ...]]:
    create_tables()
    with _connect() as conn:
        if view_type == "mistake":
            cur = conn.execute(
                "SELECT id, topic, explanation, interval, next_review_date FROM flashcards WHERE interval = 1"
            )
        else:
            cur = conn.execute("SELECT id, topic, explanation, interval, next_review_date FROM flashcards")
        return [tuple(row) for row in cur.fetchall()]


def get_all_topics() -> List[str]:
    create_tables()
    with _connect() as conn:
        cur = conn.execute("SELECT topic FROM flashcards ORDER BY topic")
        return [row["topic"] for row in cur.fetchall()]


def get_card_id_by_topic(topic: str) -> Optional[int]:
    create_tables()
    with _connect() as conn:
        row = conn.execute("SELECT id FROM flashcards WHERE topic = ?", (topic,)).fetchone()
        return int(row["id"]) if row else None


def add_custom_question(
    topic: str,
    question: str,
    question_type: str,
    options: Sequence[str],
    standard_answer: str,
) -> Tuple[bool, str]:
    create_tables()
    options_clean = [str(item).strip() for item in options if str(item).strip()]
    q_type = "choice" if question_type == "choice" else "open"
    if q_type == "choice" and len(options_clean) < 2:
        return False, "Choice questions require at least two options"

    now = dt.datetime.now().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO custom_questions (topic, question, question_type, options_json, standard_answer, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                topic.strip(),
                question.strip(),
                q_type,
                json.dumps(options_clean, ensure_ascii=False),
                standard_answer.strip(),
                now,
            ),
        )
        conn.commit()
    return True, "Question saved"


def get_custom_questions_by_topic(topic: str, limit: int = 50) -> List[Dict[str, Any]]:
    create_tables()
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT id, topic, question, question_type, options_json, standard_answer, created_at
            FROM custom_questions
            WHERE topic = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (topic, limit),
        )
        out: List[Dict[str, Any]] = []
        for row in cur.fetchall():
            try:
                options = json.loads(row["options_json"] or "[]")
            except Exception:
                options = []
            out.append(
                {
                    "id": int(row["id"]),
                    "topic": row["topic"],
                    "question": row["question"],
                    "type": row["question_type"],
                    "options": options if isinstance(options, list) else [],
                    "answer": row["standard_answer"],
                    "created_at": row["created_at"],
                }
            )
        return out


def log_mistake(card_id: Optional[int], question: str, user_answer: str, feedback: str) -> None:
    create_tables()
    now = dt.datetime.now().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO mistake_logs (card_id, question, user_answer, feedback, create_time)
            VALUES (?, ?, ?, ?, ?)
            """,
            (card_id, question, user_answer, feedback, now),
        )
        conn.commit()


def get_mistake_details() -> List[Tuple[Any, ...]]:
    create_tables()
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT m.id, COALESCE(f.topic, '(deleted topic)') AS topic,
                   m.question, m.user_answer, m.feedback, m.create_time
            FROM mistake_logs m
            LEFT JOIN flashcards f ON m.card_id = f.id
            ORDER BY m.id DESC
            """
        )
        return [tuple(row) for row in cur.fetchall()]


def delete_mistake_log(log_id: int) -> None:
    create_tables()
    with _connect() as conn:
        conn.execute("DELETE FROM mistake_logs WHERE id = ?", (log_id,))
        conn.commit()


def get_review_queue(limit: int = 20) -> List[Dict[str, Any]]:
    create_tables()
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT m.id AS mistake_id,
                   COALESCE(f.topic, '(deleted topic)') AS topic,
                   m.question, m.user_answer, m.feedback, m.create_time
            FROM mistake_logs m
            LEFT JOIN flashcards f ON m.card_id = f.id
            ORDER BY m.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]


def get_topic_mistakes(topic: str, limit: int = 5) -> List[Dict[str, str]]:
    create_tables()
    card_id = get_card_id_by_topic(topic)
    if not card_id:
        return []
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT question, user_answer, feedback, create_time
            FROM mistake_logs
            WHERE card_id = ?
            ORDER BY create_time DESC
            LIMIT ?
            """,
            (card_id, limit),
        )
        return [
            {
                "question": row["question"] or "",
                "user_answer": row["user_answer"] or "",
                "feedback": row["feedback"] or "",
                "created_at": row["create_time"] or "",
            }
            for row in cur.fetchall()
        ]


def add_note(content: str) -> None:
    create_tables()
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        conn.execute("INSERT INTO study_notes (content, created_at) VALUES (?, ?)", (content, now))
        conn.commit()


def get_all_notes() -> List[Tuple[Any, ...]]:
    create_tables()
    with _connect() as conn:
        cur = conn.execute("SELECT id, content, created_at FROM study_notes ORDER BY id DESC")
        return [tuple(row) for row in cur.fetchall()]


def delete_note(note_id: int) -> None:
    create_tables()
    with _connect() as conn:
        conn.execute("DELETE FROM study_notes WHERE id = ?", (note_id,))
        conn.commit()


def record_study_log(card_id: Optional[int], result: str) -> None:
    create_tables()
    now = dt.datetime.now().isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO study_logs (card_id, result, timestamp) VALUES (?, ?, ?)",
            (card_id, result, now),
        )
        if card_id is not None:
            _update_card_schedule(conn, card_id, result)
        conn.commit()


def _update_card_schedule(conn: sqlite3.Connection, card_id: int, result: str) -> None:
    row = conn.execute(
        "SELECT interval, scheduler_state FROM flashcards WHERE id = ?",
        (card_id,),
    ).fetchone()
    if not row:
        return

    schedule = schedule_next(
        current_interval=int(row["interval"] or 1),
        is_correct=str(result).startswith("correct"),
        scheduler_state=row["scheduler_state"] if "scheduler_state" in row.keys() else None,
    )
    conn.execute(
        """
        UPDATE flashcards
        SET next_review_date = ?, interval = ?, status = ?, scheduler_state = ?
        WHERE id = ?
        """,
        (
            schedule.next_review_date,
            schedule.interval_days,
            schedule.status,
            schedule.scheduler_state,
            card_id,
        ),
    )


def get_today_review_count() -> int:
    create_tables()
    today = dt.date.today().isoformat()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM study_logs WHERE timestamp LIKE ?",
            (f"{today}%",),
        ).fetchone()
        return int(row["cnt"]) if row else 0
