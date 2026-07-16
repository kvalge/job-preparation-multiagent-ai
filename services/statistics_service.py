"""Aggregate job-post statistics, write text reports and bar-chart PNGs."""

from __future__ import annotations

import os
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from data.db import count_by_field, count_job_posts, count_skills
from utils.date_utils import get_today

STATS_DIR = "statistics"
DIAGRAMS_DIR = os.path.join(STATS_DIR, "diagrams")

DEFAULT_TOP_COMPANIES = 5
DEFAULT_TOP_TITLES = 5
DEFAULT_TOP_SKILLS = 20

JOB_TITLES_TXT = os.path.join(STATS_DIR, "job_titles.txt")
SKILLS_TXT = os.path.join(STATS_DIR, "skills.txt")
COMPANIES_PNG = os.path.join(DIAGRAMS_DIR, "companies.png")
JOB_TITLES_PNG = os.path.join(DIAGRAMS_DIR, "job_titles.png")
SKILLS_PNG = os.path.join(DIAGRAMS_DIR, "skills.png")


def _top_with_share(
    counts: list[tuple[str, int]], total: int, n: int
) -> list[dict[str, Any]]:
    """Take the top n (label, count) pairs and add share % of total posts."""
    if n < 1:
        n = 1
    items: list[dict[str, Any]] = []
    for label, count in counts[:n]:
        share = (count / total * 100.0) if total else 0.0
        items.append(
            {
                "name": label,
                "count": count,
                "share": round(share, 1),
            }
        )
    return items


def compute_statistics(
    *,
    top_companies: int = DEFAULT_TOP_COMPANIES,
    top_titles: int = DEFAULT_TOP_TITLES,
    top_skills: int = DEFAULT_TOP_SKILLS,
) -> dict[str, Any]:
    """Compute top companies, job titles, and skills with counts and shares."""
    total = count_job_posts()
    return {
        "total_job_posts": total,
        "updated_at": get_today(),
        "top_companies": _top_with_share(
            count_by_field("company"), total, top_companies
        ),
        "top_job_titles": _top_with_share(
            count_by_field("job_title"), total, top_titles
        ),
        "top_skills": _top_with_share(count_skills(), total, top_skills),
        "limits": {
            "companies": top_companies,
            "job_titles": top_titles,
            "skills": top_skills,
        },
    }


def _format_txt_report(title: str, items: list[dict[str, Any]], total: int, updated: str) -> str:
    lines = [
        title,
        f"Updated: {updated}",
        f"Total job posts: {total}",
        "",
        f"{'Rank':<6}{'Name':<40}{'Count':>8}{'Share':>10}",
        "-" * 64,
    ]
    for i, item in enumerate(items, start=1):
        lines.append(
            f"{i:<6}{item['name'][:40]:<40}{item['count']:>8}{item['share']:>9.1f}%"
        )
    if not items:
        lines.append("(no data yet)")
    lines.append("")
    return "\n".join(lines)


def _write_txt(path: str, content: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _save_bar_chart(
    path: str,
    items: list[dict[str, Any]],
    title: str,
    xlabel: str = "Share of job posts (%)",
) -> str:
    """Write a horizontal bar chart PNG for the given items."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    if not items:
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.text(0.5, 0.5, "No data yet", ha="center", va="center", fontsize=14)
        ax.set_axis_off()
        ax.set_title(title)
    else:
        labels = [item["name"] for item in reversed(items)]
        shares = [item["share"] for item in reversed(items)]
        counts = [item["count"] for item in reversed(items)]
        height = max(3.5, 0.4 * len(items) + 1.5)
        fig, ax = plt.subplots(figsize=(9, height))
        bars = ax.barh(labels, shares, color="#3d6b8e")
        ax.set_xlabel(xlabel)
        ax.set_title(title)
        ax.set_xlim(0, max(shares) * 1.25 if shares else 1)
        for bar, count, share in zip(bars, counts, shares):
            ax.text(
                bar.get_width() + 0.5,
                bar.get_y() + bar.get_height() / 2,
                f"{count} ({share:.1f}%)",
                va="center",
                fontsize=9,
            )
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return path


def write_statistics_artifacts(stats: dict[str, Any]) -> dict[str, str]:
    """Write public txt reports (titles + skills) and PNG diagrams (all three).

    Company charts are written for local/UI use but are git-ignored and not
    linked from the README. Title and skill txt/png are project artifacts.
    """
    total = stats["total_job_posts"]
    updated = stats["updated_at"]
    paths: dict[str, str] = {}

    paths["job_titles_txt"] = _write_txt(
        JOB_TITLES_TXT,
        _format_txt_report(
            "Top job titles (count / share of job posts)",
            stats["top_job_titles"],
            total,
            updated,
        ),
    )
    paths["skills_txt"] = _write_txt(
        SKILLS_TXT,
        _format_txt_report(
            "Top skills (count / share of job posts mentioning the skill)",
            stats["top_skills"],
            total,
            updated,
        ),
    )

    paths["companies_png"] = _save_bar_chart(
        COMPANIES_PNG,
        stats["top_companies"],
        f"Top companies (n={stats['limits']['companies']}) — {updated}",
    )
    paths["job_titles_png"] = _save_bar_chart(
        JOB_TITLES_PNG,
        stats["top_job_titles"],
        f"Top job titles (n={stats['limits']['job_titles']}) — {updated}",
    )
    paths["skills_png"] = _save_bar_chart(
        SKILLS_PNG,
        stats["top_skills"],
        f"Top skills (n={stats['limits']['skills']}) — {updated}",
    )
    return paths


def refresh_statistics(
    *,
    top_companies: int = DEFAULT_TOP_COMPANIES,
    top_titles: int = DEFAULT_TOP_TITLES,
    top_skills: int = DEFAULT_TOP_SKILLS,
) -> dict[str, Any]:
    """Recompute statistics, write txt/PNG artifacts, and return the result dict."""
    print(
        f"[statistics] Refreshing (companies={top_companies}, "
        f"titles={top_titles}, skills={top_skills})..."
    )
    stats = compute_statistics(
        top_companies=top_companies,
        top_titles=top_titles,
        top_skills=top_skills,
    )
    paths = write_statistics_artifacts(stats)
    stats["paths"] = paths
    print(
        f"[statistics] Updated: {stats['total_job_posts']} posts -> "
        f"{JOB_TITLES_TXT}, {SKILLS_TXT}, {DIAGRAMS_DIR}/"
    )
    return stats
