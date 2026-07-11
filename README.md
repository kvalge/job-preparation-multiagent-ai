# Job Preparation Multiagent AI

A multi-agent AI system that helps you prepare for a **specific job application**: paste a job posting and your CV, and the system analyzes the skill gap, builds a prioritized learning plan, finds real learning resources, and can generate CV feedback and a motivation letter — all grounded in that specific role, not generic advice.

Built as a portfolio project demonstrating agentic AI system design: multi-agent orchestration, tool use, structured outputs, and adaptive planning.

## Why this project

Generic "what should I learn for role X" advice ignores the fact that every job posting has different requirements, priorities, and a real deadline. This system treats each job post as its own case: it evaluates what you already know (from your CV), what the specific posting actually asks for, how much time you realistically have before the deadline, and builds a plan around that — then adjusts as you make progress or as circumstances change.

## How it works

```mermaid
flowchart TD
    CV["CV Input\n(LLM-friendly text)"]
    JOB["Job Post Input\n(pasted text)"]

    CV --> ASSESS
    JOB --> ASSESS

    ASSESS["Assessment Agent\nAsks clarifying questions,\nevaluates current skill level,\nskips irrelevant questions gracefully"]

    ASSESS --> GAP["Gap Analysis Agent\nCompares CV vs job requirements,\nprioritizes gaps,\nweighs against time left until deadline"]

    GAP --> PLAN["Learning Plan Agent\nBuilds a prioritized, time-aware\nstudy plan"]
    GAP --> CVADV["CV Advisor Agent\nSuggests CV edits\nbefore applying"]
    GAP --> LETTER["Motivation Letter Agent\nDrafts a tailored\napplication letter"]

    PLAN --> FIND["Resource-Finder Agent\nFinds courses, docs,\nYouTube videos (web search)"]

    FIND --> PROGRESS["Progress Tracking"]
    PROGRESS --> ADJUST["Adjust / Replan Agent\nReacts to user progress\nor changed constraints"]
    ADJUST --> PLAN

    JOB --> STORE[("Job Post Records\ncompany, title, skills,\nsalary, remote/onsite, deadline")]
    STORE --> COMPARE["Comparison View\nRanks saved job posts by\nreadiness & deadline urgency"]

    style ASSESS fill:#e8f0fe,stroke:#4285f4
    style GAP fill:#fef7e0,stroke:#f9ab00
    style PLAN fill:#e6f4ea,stroke:#34a853
    style CVADV fill:#e6f4ea,stroke:#34a853
    style LETTER fill:#e6f4ea,stroke:#34a853
    style FIND fill:#fce8e6,stroke:#ea4335
    style ADJUST fill:#f3e8fd,stroke:#a142f4
```

## Agents

| Agent | Responsibility |
|---|---|
| **Assessment Agent** | Asks only relevant clarifying questions (time available, learning style, deadline); if a question is skipped, makes a reasonable default decision instead of blocking the pipeline. May also probe CV claims against the job post to gauge real skill depth (e.g. "you list SQL — have you used window functions?"). |
| **Gap Analysis Agent** | Compares CV against job requirements, grades skill level (not just yes/no), prioritizes gaps by importance and time-to-learn, and weighs this against days remaining until the application deadline. |
| **Learning Plan Agent** | Turns prioritized gaps into a structured, sequenced study plan with milestones. |
| **Resource-Finder Agent** | Uses web search to find current, real learning resources (courses, docs, YouTube) per topic — not hallucinated links. |
| **CV Advisor Agent** | Recommends concrete CV edits where skill evidence is unclear or missing, tailored to the specific job post. |
| **Motivation Letter Agent** | Drafts a tailored motivation letter using the CV, job post, and gap analysis as context. |
| **Adjust / Replan Agent** | Reacts to two kinds of change: the user reports progress/struggle on a topic, or the user's constraints change (less time, new priority) — replans accordingly. |

Each "agent" is a distinct system prompt (and, where relevant, a distinct toolset) — not a separate service. Agents pass a shared state object between stages rather than maintaining independent conversation histories.

## Data model (planned)

Each pasted job posting is stored as its own record, since gap analysis and plans are specific to that posting, not the user in general:

- **Job Post**: company, title, description, extracted skills/tools, salary, remote/onsite, application deadline, disclaimers, date saved
- **CV**: versioned, editable, stored as LLM-friendly text (file format support planned for later)
- **Gap Analysis**: linked to a CV + job post pair, includes per-skill evidence level and priority
- **Learning Plan**: linked to a gap analysis, includes milestones and resource links
- **Progress**: tracks completed topics, feeds the Adjust/Replan Agent

This also enables a **comparison view** across saved job posts — since users usually apply to more than one role, ranking posts by estimated readiness vs. deadline urgency helps decide where to focus effort first.

## Privacy

This is designed as a self-hosted, single-user tool, not a multi-tenant SaaS. Data (CV, job posts, gap analyses) is stored locally by default and is not shared beyond the LLM API call itself. Only the minimum text needed for a given agent call is sent to the model provider — nothing is persisted server-side outside your own machine.

## Tech Stack

- Python
- OpenRouter API (OpenAI-compatible SDK)
- *(add: storage — SQLite planned; web framework — TBD)*

## Setup

1. Clone the repo:
   ```bash
   git clone <repo-url>
   cd job-preparation-multiagent-ai
   ```

2. Copy `.env.example` to `.env` and fill in the required values:

   **PowerShell:**
   ```powershell
   Copy-Item .env.example .env
   ```

   **Bash/Linux/Mac:**
   ```bash
   cp .env.example .env
   ```

3. Open `.env` and add your OpenRouter credentials:
   ```
   API_KEY=
   MODEL=
   ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Run the project:
   ```bash
   python main.py
   ```

> ⚠️ **Note:** The `.env` file contains sensitive credentials and should never be committed to Git. It's already included in `.gitignore`.

## Usage

*(add once CLI/UI is finalized: example flow — paste job post, paste CV, view generated plan)*

## Roadmap

- [x] Basic conversational agent with memory (prior prototype, carried into this project)
- [ ] Job post input and structured extraction (company, title, skills, salary, deadline, etc.)
- [ ] CV input (plain text first, file formats later)
- [ ] Assessment Agent with adaptive, skippable clarifying questions
- [ ] Gap Analysis Agent with prioritization and deadline-awareness
- [ ] Learning Plan Agent
- [ ] Resource-Finder Agent with real web search tool use
- [ ] Progress tracking and Adjust/Replan Agent
- [ ] CV Advisor Agent
- [ ] Motivation Letter Agent
- [ ] Job post comparison / prioritization view
- [ ] Persistent storage (SQLite)
- [ ] Evaluation harness for agent output quality
- [ ] Simple front end (Streamlit/Gradio or FastAPI + minimal UI)

## Project Structure

```
.
├── main.py
├── agents/
├── data/
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## License

This project is licensed under the MIT License.
