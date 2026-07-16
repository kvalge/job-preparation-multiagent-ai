import hashlib
import json
import os
import sqlite3

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
                content_hash TEXT,
                txt_path TEXT,
                cv_version_id INTEGER,
                analysis_summary TEXT
            )
            """
        )
        # Migrate databases created before newer columns existed.
        columns = [row[1] for row in conn.execute("PRAGMA table_info(job_posts)")]
        if "content_hash" not in columns:
            conn.execute("ALTER TABLE job_posts ADD COLUMN content_hash TEXT")
        if "txt_path" not in columns:
            conn.execute("ALTER TABLE job_posts ADD COLUMN txt_path TEXT")
        if "cv_version_id" not in columns:
            conn.execute("ALTER TABLE job_posts ADD COLUMN cv_version_id INTEGER")
        if "analysis_summary" not in columns:
            conn.execute("ALTER TABLE job_posts ADD COLUMN analysis_summary TEXT")
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cv_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                content_hash TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rankings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                created_at TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def hash_job_post(job_post: str) -> str:
    """Stable content hash of a job post, used to detect duplicates and name files."""
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


def insert_job_post(
    fields: dict,
    content_hash: str,
    *,
    match_verdict: str | None = None,
    match_reasoning: str | None = None,
    status: str = "saved",
    txt_path: str | None = None,
    path: str = DB_PATH,
) -> int:
    """Insert one job post (already-extracted fields) plus its skills. Returns the id.

    Analysis fields (verdict/reasoning) are optional so a post can be saved before any
    analysis is run; they can be filled in later via update_job_post_analysis().
    """
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
                status, content_hash, txt_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                txt_path,
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


def update_job_post_analysis(
    job_post_id: int,
    match_verdict: str,
    match_reasoning: str,
    status: str,
    cv_version_id: int | None = None,
    path: str = DB_PATH,
) -> None:
    """Record fit-analysis results on an existing job post.

    Also stamps which CV version the analysis was run against, so it stays clear even
    after the CV is edited later.
    """
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            UPDATE job_posts
            SET match_verdict = ?, match_reasoning = ?, status = ?, cv_version_id = ?
            WHERE id = ?
            """,
            (match_verdict, match_reasoning, status, cv_version_id, job_post_id),
        )
        conn.commit()
    finally:
        conn.close()


def save_cv_version(text: str, path: str = DB_PATH) -> int:
    """Snapshot a CV version, returning its id.

    De-duplicates: if the most recent version has identical content, its id is returned
    instead of inserting a copy.
    """
    content = text.strip()
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    conn = sqlite3.connect(path)
    try:
        latest = conn.execute(
            "SELECT id, content_hash FROM cv_versions ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if latest is not None and latest[1] == content_hash:
            return latest[0]
        cursor = conn.execute(
            "INSERT INTO cv_versions (content, content_hash, created_at) VALUES (?, ?, ?)",
            (content, content_hash, get_today()),
        )
        conn.commit()
        version_id = cursor.lastrowid
        if version_id is None:
            raise RuntimeError("Failed to insert CV version: no row id returned.")
        return version_id
    finally:
        conn.close()


def get_latest_cv_version(path: str = DB_PATH) -> dict | None:
    """Return the most recent CV version as a dict, or None if none saved yet."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM cv_versions ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_cv_version(version_id: int, path: str = DB_PATH) -> dict | None:
    """Return a specific CV version as a dict, or None if not found."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM cv_versions WHERE id = ?", (version_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_job_posts(path: str = DB_PATH) -> list[dict]:
    """Return saved job posts (most recent first) as a list of dicts."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, company, job_title, location_type, job_post_deadline,
                   status, date_saved
            FROM job_posts
            ORDER BY id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


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


def update_job_post_summary(
    job_post_id: int, summary_json: str, path: str = DB_PATH
) -> None:
    """Store a compact JSON summary of the latest analysis on the job post row.

    This snapshot (verdict, days remaining, gaps, plan feasibility) feeds the
    cross-post ranking without having to re-read the generated output files.
    """
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "UPDATE job_posts SET analysis_summary = ? WHERE id = ?",
            (summary_json, job_post_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_analyzed_job_posts(path: str = DB_PATH) -> list[dict]:
    """Return job posts that have an analysis summary, for ranking/comparison."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, company, job_title, job_post_deadline, status,
                   match_verdict, analysis_summary
            FROM job_posts
            WHERE analysis_summary IS NOT NULL
            ORDER BY id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def save_ranking(content: str, path: str = DB_PATH) -> int:
    """Persist a ranking result (JSON string). Keeps history; returns the row id."""
    conn = sqlite3.connect(path)
    try:
        cursor = conn.execute(
            "INSERT INTO rankings (content, created_at) VALUES (?, ?)",
            (content, get_today()),
        )
        conn.commit()
        ranking_id = cursor.lastrowid
        if ranking_id is None:
            raise RuntimeError("Failed to insert ranking: no row id returned.")
        return ranking_id
    finally:
        conn.close()


def get_latest_ranking(path: str = DB_PATH) -> dict | None:
    """Return the most recent ranking as {content, created_at}, or None."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT content, created_at FROM rankings ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def count_job_posts(path: str = DB_PATH) -> int:
    """Return the total number of saved job posts."""
    conn = sqlite3.connect(path)
    try:
        row = conn.execute("SELECT COUNT(*) FROM job_posts").fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def count_by_field(field: str, path: str = DB_PATH) -> list[tuple[str, int]]:
    """Count job posts grouped by a text column (e.g. company, job_title).

    Empty/null values are grouped as '(unknown)'. Returns (label, count) pairs
    ordered by count descending.
    """
    if field not in ("company", "job_title"):
        raise ValueError(f"Unsupported field for counting: {field!r}")
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            f"""
            SELECT
                COALESCE(NULLIF(TRIM({field}), ''), '(unknown)') AS label,
                COUNT(*) AS cnt
            FROM job_posts
            GROUP BY label
            ORDER BY cnt DESC, label ASC
            """
        ).fetchall()
        return [(str(r[0]), int(r[1])) for r in rows]
    finally:
        conn.close()


def count_skills(path: str = DB_PATH) -> list[tuple[str, int]]:
    """Count how many job posts list each skill (case-insensitive).

    Display label is the most common original casing. Ordered by count descending.
    """
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            """
            SELECT
                (
                    SELECT s2.skill
                    FROM job_post_skills s2
                    WHERE LOWER(TRIM(s2.skill)) = LOWER(TRIM(s1.skill))
                    GROUP BY s2.skill
                    ORDER BY COUNT(*) DESC, s2.skill ASC
                    LIMIT 1
                ) AS label,
                COUNT(DISTINCT s1.job_post_id) AS cnt
            FROM job_post_skills s1
            WHERE s1.skill IS NOT NULL AND TRIM(s1.skill) != ''
            GROUP BY LOWER(TRIM(s1.skill))
            ORDER BY cnt DESC, label ASC
            """
        ).fetchall()
        return [(str(r[0]), int(r[1])) for r in rows]
    finally:
        conn.close()
