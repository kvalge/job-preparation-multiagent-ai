import re


def slugify(value: str | None) -> str:
    """Turn arbitrary text into a filesystem-safe slug (fallback: 'unknown')."""
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return slug or "unknown"


def output_stem(
    company: str | None, job_title: str | None, date_saved: str, job_post_id: int
) -> str:
    """Build a shared filename stem: <company>_<title>_<date>_id<postid>.

    The post id keeps names unique across posts that share company/title/date.
    """
    return f"{slugify(company)}_{slugify(job_title)}_{date_saved}_id{job_post_id}"
