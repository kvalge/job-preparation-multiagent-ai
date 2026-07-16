import json
import os

import streamlit as st

from config import create_client, web_search_enabled_default
from data.cv import load_cv
from data.db import get_cv_version, get_job_post, init_db, list_job_posts
from services.analysis_service import run_analysis
from services.cv_service import ensure_cv_version, save_cv_with_version
from services.job_post_service import add_job_post
from services.ranking_service import load_latest_ranking

st.set_page_config(page_title="Job Preparation Multiagent AI", page_icon="🧭")

init_db()
st.session_state.setdefault("analysis", {})

try:
    client, model = create_client()
except ValueError:
    client, model = None, None

st.title("Job Preparation Multiagent AI")
st.caption(
    "Prepare for a specific job application: evaluate fit, analyze skill gaps, "
    "build a learning plan, tailor your CV, and draft a motivation letter."
)

# --- CV ---------------------------------------------------------------------
st.header("Your CV")

existing_cv = load_cv()
if existing_cv:
    st.success("A CV is currently saved. Edit it below and save to update.")
else:
    st.info("No CV saved yet. Paste your CV text below and save it.")

cv_text = st.text_area(
    "CV text",
    value=existing_cv or "",
    height=400,
    placeholder="Paste your CV here...",
)

if st.button("Save CV", type="primary"):
    cv_to_save = (cv_text or "").strip()
    if not cv_to_save:
        st.error("CV text cannot be empty.")
    else:
        version_id = save_cv_with_version(cv_to_save)
        st.success(f"CV saved (version {version_id}).")
        st.rerun()

# --- Job posts --------------------------------------------------------------
st.header("Job posts")
st.caption(
    "Paste a job posting and save it. You can add several in a row — each is stored "
    "separately, and identical postings are detected and skipped."
)

if client is None or model is None:
    st.error("Set API_KEY and MODEL in your .env file to add and analyze job posts.")
else:
    with st.form("add_job_post", clear_on_submit=True):
        job_post_text = st.text_area(
            "Job post text",
            height=300,
            placeholder="Paste a job posting here...",
        )
        submitted = st.form_submit_button("Save job post", type="primary")

    if submitted:
        text = (job_post_text or "").strip()
        if not text:
            st.error("Job post text cannot be empty.")
        else:
            with st.spinner("Extracting details and saving..."):
                try:
                    saved = add_job_post(client, model, text)
                except Exception as e:
                    st.error(f"Could not save job post: {e}")
                    saved = None
            if saved is not None:
                label = " — ".join(
                    part for part in (saved["company"], saved["job_title"]) if part
                ) or f"id {saved['id']}"
                if saved["duplicate"]:
                    st.warning(f"Already saved: {label} (id {saved['id']}).")
                else:
                    st.success(f"Saved: {label} (id {saved['id']}).")

st.subheader("Saved job posts")
posts = list_job_posts()
if not posts:
    st.write("No job posts saved yet.")
else:
    st.dataframe(
        posts,
        hide_index=True,
        column_config={
            "id": "ID",
            "company": "Company",
            "job_title": "Title",
            "location_type": "Location",
            "job_post_deadline": "Deadline",
            "status": "Status",
            "date_saved": "Saved",
        },
    )


# --- Analyze a job post -----------------------------------------------------
def _post_label(post: dict) -> str:
    parts = [part for part in (post.get("company"), post.get("job_title")) if part]
    name = " — ".join(parts) if parts else "(untitled)"
    return f"#{post['id']} · {name}"


def _render_results(results: dict) -> None:
    fit = results.get("fit")
    if fit is None:
        st.error("Fit evaluation failed — see the terminal log for details.")
        return

    verdict = fit.get("verdict", "unknown")
    icon = {"good_fit": "✅", "stretch_fit": "🟡", "poor_fit": "🔴"}.get(verdict, "")
    st.subheader(f"{icon} Fit: {verdict}")
    st.write(fit.get("reasoning", ""))
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Matches**")
        for m in fit.get("key_matches", []):
            st.markdown(f"- {m}")
    with col2:
        st.markdown("**Gaps**")
        for g in fit.get("key_gaps", []):
            st.markdown(f"- {g}")

    cv_version_id = results.get("cv_version_id")
    if cv_version_id is not None:
        version = get_cv_version(cv_version_id)
        saved_at = version.get("created_at") if version else "?"
        st.caption(f"Evaluated against CV version {cv_version_id} (saved {saved_at}).")

    if results.get("status") == "declined":
        st.warning("Stopped after fit evaluation (poor fit).")
        return

    gaps = results.get("gaps")
    if gaps is not None:
        st.subheader(f"Skill gaps ({results.get('days_remaining', '?')} days until deadline)")
        st.write(gaps.get("overall_summary", ""))
        for gap in gaps.get("prioritized_gaps", []):
            fit_note = "achievable" if gap.get("achievable_before_deadline") else "tight"
            st.markdown(
                f"**{gap['priority']}. {gap['skill']}** "
                f"[{gap['importance']}] · ~{gap['estimated_days_to_learn']}d ({fit_note})"
            )
            st.markdown(f"  {gap['recommendation']}")

    plan = results.get("plan")
    if plan is not None:
        st.subheader("Learning plan")
        st.write(
            f"{plan.get('total_estimated_days', '?')}d of "
            f"{plan.get('days_remaining', '?')}d available — {plan.get('feasibility_note', '')}"
        )
        for item in plan.get("items", []):
            with st.expander(
                f"{item['priority']}. {item['skill']} (~{item['estimated_days']}d)"
            ):
                st.markdown(f"**What:** {item['what']}")
                st.markdown(f"**Why:** {item['why']}")
                for res in item.get("resources", []):
                    st.markdown(f"- [{res['name']}]({res['link']}) — {res['description']}")
        if results.get("plan_path"):
            st.download_button(
                "Download learning plan (JSON)",
                data=json.dumps(plan, indent=2, ensure_ascii=False),
                file_name=os.path.basename(results["plan_path"]),
                mime="application/json",
                key=f"dl_plan_{results['job_post_id']}",
            )

    advice = results.get("cv")
    if advice is not None:
        st.subheader("Tailored CV")
        for rec in advice.get("recommendations", []):
            st.markdown(f"- **[{rec['section']}]** {rec['change']} — _{rec['why']}_")
        with st.expander("Preview revised CV"):
            st.markdown(advice["revised_cv"])
        if results.get("cv_path"):
            st.download_button(
                "Download tailored CV (Markdown)",
                data=advice["revised_cv"],
                file_name=os.path.basename(results["cv_path"]),
                mime="text/markdown",
                key=f"dl_cv_{results['job_post_id']}",
            )

    letter = results.get("letter")
    if letter is not None:
        st.subheader("Motivation letter")
        st.markdown(letter["motivation_letter"])
        if results.get("letter_path"):
            st.download_button(
                "Download motivation letter (Markdown)",
                data=letter["motivation_letter"],
                file_name=os.path.basename(results["letter_path"]),
                mime="text/markdown",
                key=f"dl_letter_{results['job_post_id']}",
            )


if posts and client is not None and model is not None:
    st.header("Analyze a job post")

    selected = st.selectbox(
        "Select a saved job post",
        options=posts,
        format_func=_post_label,
    )
    post_id = selected["id"]

    detail = get_job_post(post_id) or {}
    st.write(
        f"**Company:** {detail.get('company') or '—'}  |  "
        f"**Title:** {detail.get('job_title') or '—'}  |  "
        f"**Deadline:** {detail.get('job_post_deadline') or '—'}  |  "
        f"**Status:** {detail.get('status') or '—'}"
    )

    col_a, col_b = st.columns(2)
    with col_a:
        use_web_search = st.toggle(
            "Use web search for resources", value=web_search_enabled_default()
        )
    with col_b:
        proceed_on_poor_fit = st.toggle("Proceed even if poor fit", value=True)

    if st.button("Run analysis", type="primary", key=f"run_{post_id}"):
        cv = load_cv()
        if not cv:
            st.error("Save your CV first (above) before running analysis.")
        else:
            cv_version_id = ensure_cv_version(cv)
            with st.spinner("Running analysis pipeline... this can take a while."):
                try:
                    results = run_analysis(
                        client,
                        model,
                        post_id,
                        cv,
                        cv_version_id,
                        use_web_search=use_web_search,
                        proceed_on_poor_fit=proceed_on_poor_fit,
                    )
                    st.session_state["analysis"][post_id] = results
                    label = _post_label(detail)
                    print(
                        f"[ui] Analysis complete for {label} "
                        f"(status={results.get('status')}). Results shown in the browser."
                    )
                except Exception as e:
                    st.error(f"Analysis failed: {e}")

    cached = st.session_state["analysis"].get(post_id)
    if cached is not None:
        _render_results(cached)


# --- Which job to pursue (cross-post ranking) -------------------------------
def _render_ranking() -> None:
    ranking = load_latest_ranking()
    if not ranking:
        return

    st.header("Which job to pursue")
    st.caption(
        "Ranked across all analyzed job posts by fit and how realistically the gaps "
        "can be closed before each deadline. Refreshed after every analysis"
        + (f" (last updated {ranking['created_at']})." if ranking.get("created_at") else ".")
    )

    labels = {p["id"]: _post_label(p) for p in list_job_posts()}

    top = ranking.get("top_pick") or {}
    top_id = top.get("job_post_id")
    if top_id is not None:
        st.success(f"**Start here: {labels.get(top_id, f'#{top_id}')}**\n\n{top.get('why', '')}")

    for item in ranking.get("ranking", []):
        pid = item.get("job_post_id")
        rec = item.get("recommendation", "")
        icon = {"pursue": "✅", "maybe": "🟡", "skip": "🔴"}.get(rec, "•")
        st.markdown(
            f"**{item.get('rank')}. {labels.get(pid, f'#{pid}')}** "
            f"{icon} _{rec}_ — {item.get('reason', '')}"
        )

    if ranking.get("overall_note"):
        st.info(ranking["overall_note"])


_render_ranking()
