import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import models
from database import engine, get_db
from routers import auth_router, document_router, root_router, team_router, project_router, regions_router, user_router

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MAST Backend API",
    root_path=os.getenv("ROOT_PATH", "/api"),
)

UPLOADS_DIR = Path(__file__).resolve().parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

app.include_router(root_router)
app.include_router(auth_router)
app.include_router(document_router)
app.include_router(team_router)
app.include_router(project_router)
app.include_router(regions_router)
app.include_router(user_router)
