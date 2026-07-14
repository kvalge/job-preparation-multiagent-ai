import hashlib
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
                status TEXT,
                content_hash TEXT
            )
            """
        )
        # Migrate databases created before content_hash existed.
        columns = [row[1] for row in conn.execute("PRAGMA table_info(job_posts)")]
        if "content_hash" not in columns:
            conn.execute("ALTER TABLE job_posts ADD COLUMN content_hash TEXT")
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


def _hash_job_post(job_post: str) -> str:
    """Stable content hash of a job post, used to detect duplicates."""
    return hashlib.sha256(job_post.strip().encode("utf-8")).hexdigest()


def find_job_post_by_hash(content_hash: str, path: str = DB_PATH) -> int | None:
    """Return the id of an existing job post with this content hash, or None."""
    conn = sqlite3.connect(path)
    try:
        row = conn.execute(
            "SELECT id FROM job_posts WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        return row[0] if row else None
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

    If an identical job post was already saved, its existing id is returned without
    re-extracting or re-inserting (avoids duplicate rows and a wasted LLM call).
    """
    content_hash = _hash_job_post(job_post)
    existing_id = find_job_post_by_hash(content_hash, path)
    if existing_id is not None:
        print(f"  (This job post is already saved as id {existing_id}; skipping re-save.)")
        return existing_id

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
                disclaimers, summary, date_saved, match_verdict, match_reasoning,
                status, content_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                content_hash,
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


def get_job_post(job_post_id: int, path: str = DB_PATH) -> dict | None:
    """Return a saved job post (with its skills) as a dict, or None if not found."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM job_posts WHERE id = ?", (job_post_id,)
        ).fetchone()
        if row is None:
            return None
        record = dict(row)
        skill_rows = conn.execute(
            "SELECT skill FROM job_post_skills WHERE job_post_id = ?", (job_post_id,)
        ).fetchall()
        record["skills"] = [r["skill"] for r in skill_rows]
        return record
    finally:
        conn.close()
