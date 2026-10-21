from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.User import UsageEvent, User

QUOTAS = {
    "analysis": (10, timedelta(hours=1), "Atingiste o limite de 10 análises por hora. Tenta daqui a pouco."),
    "draft": (30, timedelta(hours=1), "Atingiste o limite de 30 rascunhos por hora. Tenta daqui a pouco."),
    "find_email": (30, timedelta(hours=1), "Atingiste o limite de 30 procuras de email por hora. Tenta daqui a pouco."),
    "send": (25, timedelta(days=1), "Atingiste o limite de 25 envios nas últimas 24 horas. Envios a mais seguidos podem levar a Google a bloquear a tua conta."),
}


def consume_quota(db: Session, user: User, kind: str) -> None:
    limit, window, message = QUOTAS[kind]
    since = datetime.now(timezone.utc) - window
    used = (
        db.query(UsageEvent)
        .filter(UsageEvent.id_user == user.id_user, UsageEvent.kind == kind, UsageEvent.created_at >= since)
        .count()
    )
    if used >= limit:
        raise HTTPException(status_code=429, detail=message)
    db.add(UsageEvent(id_user=user.id_user, kind=kind))
    db.commit()
