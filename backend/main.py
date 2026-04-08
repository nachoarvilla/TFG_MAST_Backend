from fastapi import FastAPI

import models
from database import engine, get_db
from routers import auth_router, root_router, team_router, project_router

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="MAST Backend API")

app.include_router(root_router)
app.include_router(auth_router)
app.include_router(team_router)
app.include_router(project_router)
