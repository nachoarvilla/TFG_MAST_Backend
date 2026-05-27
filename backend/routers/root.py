from fastapi import APIRouter

router = APIRouter(tags=["default"])


@router.get("/")
def read_root():
    return {"message": "Welcome to the Annot8 backend", "status": "online"}


@router.get("/health")
def health_check():
    return {"database": "connected_placeholder", "api": "running"}
