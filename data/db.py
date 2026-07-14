import json
import os
import sqlite3

from openai import OpenAI

from agents.job_post_extraction import extract_job_post
from utils.date_utils import get_today

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


def save_job_post(
    client: OpenAI,
    model: str,
    job_post: str,
    match_verdict: str,
    match_reasoning: str,
    status: str,
    path: str = DB_PATH,
) -> int:
    """Extract structured data from a job post and persist it to the database.

    Uses the extraction agent to pull structured fields from the raw job post text,
    then inserts one row into job_posts and one row per skill into job_post_skills.
    Returns the new job_posts.id.
    """
    fields = extract_job_post(client, model, job_post)

    disclaimers = fields.get("disclaimers")
    disclaimers_json = json.dumps(disclaimers) if disclaimers else None

    skills = fields.get("skills") or []

    conn = sqlite3.connect(path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO job_posts (
                company, job_title, salary, location_type, job_post_deadline,
                disclaimers, summary, date_saved, match_verdict, match_reasoning, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fields.get("company"),
                fields.get("job_title"),
                fields.get("salary"),
                fields.get("location_type"),
                fields.get("job_post_deadline"),
                disclaimers_json,
                fields.get("summary"),
                get_today(),
                match_verdict,
                match_reasoning,
                status,
            ),
        )
        job_post_id = cursor.lastrowid
        if job_post_id is None:
            raise RuntimeError("Failed to insert job post: no row id returned.")

        conn.executemany(
            "INSERT INTO job_post_skills (job_post_id, skill) VALUES (?, ?)",
            [(job_post_id, skill) for skill in skills],
        )
        conn.commit()
    finally:
        conn.close()

    return job_post_id
