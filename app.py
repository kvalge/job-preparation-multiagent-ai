import os

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from data.cv import load_cv, save_cv
from data.db import init_db, list_job_posts
from services.job_post_service import add_job_post

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

st.set_page_config(page_title="Job Preparation Multiagent AI", page_icon="🧭")

load_dotenv()
init_db()

api_key = os.getenv("API_KEY")
model = os.getenv("MODEL")
client = (
    OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL) if api_key and model else None
)

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
        save_cv(cv_to_save)
        st.success("CV saved.")
        st.rerun()

# --- Job posts --------------------------------------------------------------
st.header("Job posts")
st.caption(
    "Paste a job posting and save it. You can add several in a row — each is stored "
    "separately, and identical postings are detected and skipped."
)

if client is None:
    st.error("Set API_KEY and MODEL in your .env file to add job posts.")
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
