import os
import sqlite3

DB_PATH = "data/jobs.db"


def init_db(path: str = DB_PATH) -> None:
    """Create the SQLite database and tables if they don't already exist."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT,
                job_title TEXT,
                salary TEXT,
                location_type TEXT,
                job_post_deadline TEXT,
                disclaimers TEXT,
                summary TEXT,
                date_saved TEXT,
                match_verdict TEXT,
                match_reasoning TEXT,
                status TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_post_skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_post_id INTEGER,
                skill TEXT,
                FOREIGN KEY (job_post_id) REFERENCES job_posts (id)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
