import sqlite3
from contextlib import closing


DB_NAME = "smart_attendance.db"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with closing(get_db()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                roll_no TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                branch TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                start_time TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance (
                student_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                time TEXT NOT NULL,
                PRIMARY KEY (student_id, session_id),
                FOREIGN KEY (student_id) REFERENCES students(roll_no) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()


def reset_db():
    with closing(get_db()) as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS attendance")
        cur.execute("DROP TABLE IF EXISTS sessions")
        cur.execute("DROP TABLE IF EXISTS students")
        conn.commit()

    init_db()
