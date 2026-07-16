from openai import OpenAI

from agents.job_post_extraction import extract_job_post
from data.db import (
    find_job_post_by_hash,
    get_job_post,
    hash_job_post,
    insert_job_post,
)
from data.job_post import save_job_post_file
from utils.date_utils import get_today


def add_job_post(client: OpenAI, model: str, text: str) -> dict:
    """Extract, de-duplicate, and persist a single job post (DB + named txt file).

    Saves the post with status 'saved' and no analysis yet, so several posts can be
    added in a row before any follow-up actions. Returns a summary dict:
    {id, duplicate, company, job_title, path}.
    """
    content_hash = hash_job_post(text)

    existing_id = find_job_post_by_hash(content_hash)
    if existing_id is not None:
        existing = get_job_post(existing_id) or {}
        print(f"[job post] Already saved as id {existing_id}; skipping duplicate.")
        return {
            "id": existing_id,
            "duplicate": True,
            "company": existing.get("company"),
            "job_title": existing.get("job_title"),
            "path": existing.get("txt_path"),
        }

    print("[job post] Extracting details...")
    fields = extract_job_post(client, model, text)

    date_saved = get_today()
    txt_path = save_job_post_file(
        text,
        fields.get("company"),
        fields.get("job_title"),
        date_saved,
        content_hash[:8],
    )

    job_post_id = insert_job_post(fields, content_hash, txt_path=txt_path)
    print(
        f"[job post] Saved id {job_post_id}: "
        f"{fields.get('company')} — {fields.get('job_title')} -> {txt_path}"
    )
    return {
        "id": job_post_id,
        "duplicate": False,
        "company": fields.get("company"),
        "job_title": fields.get("job_title"),
        "path": txt_path,
    }
