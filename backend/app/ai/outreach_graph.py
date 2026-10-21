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


def _role(state: OutreachState) -> str:
    return (state.get("title") or "").strip() or (state.get("area") or "").strip() or "a role matching the candidate profile"


def write_outreach(state: OutreachState) -> OutreachState:
    language = LANGUAGE_NAMES.get(state.get("language", "en"), "English")
    name = (state.get("candidate_name") or "").strip()
    force = bool(state.get("force"))
    result = chat_json(
        "You assess fit and write the application email in one reply. Answer only with JSON "
        '{"fit_score": integer 0-100, "fit_reason": one short sentence in European Portuguese, '
        '"subject": string, "body": string}. '
        "Use only the listed skills and languages. If the job title requires a spoken language "
        "that is not listed, score below 35. Do not invent experience. "
        + (
            "Always write subject and body. "
            if force
            else "If fit_score is below 35, leave subject and body empty. "
        )
        + f"When writing, use {language}, maximum 120 words, no invented facts. "
        "Claim ONLY the candidate skills listed. The job title may mention technologies "
        "the candidate does not list: never claim experience with those; at most say you are keen to learn them. "
        "Say the CV is attached. "
        + (f"Sign off with exactly this name: {name}." if name else "Sign off with the placeholder [Nome]."),
        f"Job title: {_role(state)}\nCompany: {state['company']}\nArea: {state.get('area', '')}\n"
        f"Candidate skills: {', '.join(state.get('cv_skills', [])) or 'none listed'}\n"
        f"Skills that appear in the job: {', '.join(state.get('matched_skills', [])) or 'none'}",
    )
    try:
        score = max(0, min(100, int(result.get("fit_score", 0))))
    except (TypeError, ValueError):
        score = 0
    update: OutreachState = {
        "fit_score": score,
        "fit_reason": str(result.get("fit_reason", "")).strip(),
    }
    if force or score >= MIN_FIT_SCORE:
        body = str(result.get("body", "")).strip()
        if name:
            body = body.replace("[Nome]", name).replace("[Name]", name).replace("[nome]", name)
        update["subject"] = str(result.get("subject", "")).strip()
        update["body"] = body
    return update


def build_graph():
    graph = StateGraph(OutreachState)
    graph.add_node("write_outreach", write_outreach)
    graph.add_edge(START, "write_outreach")
    graph.add_edge("write_outreach", END)
    return graph.compile()


outreach_graph = build_graph()
