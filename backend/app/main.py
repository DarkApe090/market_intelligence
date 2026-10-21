import truststore

truststore.inject_into_ssl()

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from app.core.config import settings
from app.services.Auth import get_current_user
from app.controllers import Auth, CareerProfile, Google, Company, Contact, CompanyContact, UserJobPosting, Legal

app = FastAPI(
    title="Scrapper Mercado Dev",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

@app.middleware("http")
async def reject_foreign_origin(request: Request, call_next):
    """Bloqueia pedidos que alteram dados vindos de origens não autorizadas (CSRF)."""
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin.rstrip("/") not in settings.origins:
        return JSONResponse({"detail": "Origem não autorizada."}, status_code=403)
    return await call_next(request)


@app.get("/")
def root():
    return {
        "message: Scapper Mercado Dev está a correr"
    }

app.include_router(Legal.router)
app.include_router(Auth.router)
app.include_router(Company.router)
app.include_router(CareerProfile.router)
app.include_router(Google.router)
app.include_router(Contact.router)
app.include_router(CompanyContact.router)
app.include_router(UserJobPosting.router, dependencies=[Depends(get_current_user)])