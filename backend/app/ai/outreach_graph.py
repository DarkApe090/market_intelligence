from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.ai.llm import chat_json

MIN_FIT_SCORE = 35

LANGUAGE_NAMES = {"en": "English", "pt": "European Portuguese"}


class OutreachState(TypedDict, total=False):
    company: str
    title: str
    area: str
    cv_skills: list[str]
    matched_skills: list[str]
    language: Literal["en", "pt"]
    candidate_name: str | None
    force: bool
    fit_score: int
    fit_reason: str
    subject: str
    body: str


def score_job(state: OutreachState) -> OutreachState:
    result = chat_json(
        "You assess how well a candidate fits a job. Answer only with JSON "
        '{"fit_score": integer 0-100, "fit_reason": one short sentence in European Portuguese}. '
        "Base the score only on the skills listed; do not invent experience.",
        f"Job title: {state['title']}\nCompany: {state['company']}\nArea: {state.get('area', '')}\n"
        f"Candidate skills: {', '.join(state.get('cv_skills', [])) or 'none listed'}\n"
        f"Skills that appear in the job: {', '.join(state.get('matched_skills', [])) or 'none'}",
    )
    try:
        score = max(0, min(100, int(result.get("fit_score", 0))))
    except (TypeError, ValueError):
        score = 0
    return {"fit_score": score, "fit_reason": str(result.get("fit_reason", "")).strip()}


def route_after_score(state: OutreachState) -> str:
    if state.get("force") or state["fit_score"] >= MIN_FIT_SCORE:
        return "draft_email"
    return END


def draft_email(state: OutreachState) -> OutreachState:
    language = LANGUAGE_NAMES.get(state.get("language", "en"), "English")
    name = (state.get("candidate_name") or "").strip()
    result = chat_json(
        "You write short, honest job application emails. Answer only with JSON "
        '{"subject": string, "body": string}. Write in '
        f"{language}. Maximum 120 words, no invented facts. "
        "Claim ONLY the candidate skills listed below. The job title may mention technologies "
        "the candidate does not list: never claim experience with those; at most say you are keen to learn them. "
        "Say the CV is attached. "
        + (f"Sign off with exactly this name: {name}." if name else "Sign off with the placeholder [Nome]."),
        f"Role: {state['title']} at {state['company']}\n"
        f"Candidate skills relevant to the role: {', '.join(state.get('matched_skills') or state.get('cv_skills', []))}",
    )
    body = str(result.get("body", "")).strip()
    if name:
        body = body.replace("[Nome]", name).replace("[Name]", name).replace("[nome]", name)
    return {"subject": str(result.get("subject", "")).strip(), "body": body}


def build_graph():
    graph = StateGraph(OutreachState)
    graph.add_node("score_job", score_job)
    graph.add_node("draft_email", draft_email)
    graph.add_edge(START, "score_job")
    graph.add_conditional_edges("score_job", route_after_score, {"draft_email": "draft_email", END: END})
    graph.add_edge("draft_email", END)
    return graph.compile()


outreach_graph = build_graph()
