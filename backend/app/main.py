from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.actions import router as actions_router
from app.api.routes.data import router as data_router
from app.api.routes.pegging import router as pegging_router
from app.api.routes.planning import router as planning_router
from app.core.config import settings

app = FastAPI(title=settings.api_title)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(planning_router)
app.include_router(data_router)
app.include_router(pegging_router)
app.include_router(actions_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
