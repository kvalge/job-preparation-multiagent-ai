# To run: python -m streamlit run app.py

import streamlit as st

from data.cv import load_cv, save_cv

st.set_page_config(page_title="Job Preparation Multiagent AI", page_icon="🧭")

st.title("Job Preparation Multiagent AI")
st.caption(
    "Prepare for a specific job application: evaluate fit, analyze skill gaps, "
    "build a learning plan, tailor your CV, and draft a motivation letter."
)

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
