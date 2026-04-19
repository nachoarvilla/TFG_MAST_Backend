from pathlib import Path
from uuid import uuid4

import fitz
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

import models
from auth import get_current_user
from database import get_db

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOADS_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _ensure_uuid_directory(base_dir: Path) -> Path:
    while True:
        directory = base_dir / uuid4().hex
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=False)
            return directory


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    description: str | None = Form(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted",
        )

    original_filename = Path(file.filename).name
    if not original_filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a .pdf extension",
        )

    document_bytes = await file.read()
    if not document_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded PDF is empty",
        )

    try:
        document = fitz.open(stream=document_bytes, filetype="pdf")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not a valid PDF",
        )

    document_dir = _ensure_uuid_directory(UPLOADS_DIR)
    pdf_path = document_dir / original_filename
    pdf_path.write_bytes(document_bytes)

    page_count = document.page_count
    page_files = []

    for page_index in range(page_count):
        page = document.load_page(page_index)
        matrix = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        image_name = f"page_{page_index + 1}.jpg"
        image_path = document_dir / image_name
        pix.save(str(image_path), "jpeg", jpg_quality=90)
        page_files.append(image_name)

    document.close()

    document_record = models.Document(
        file_path=str(Path(document_dir.name) / original_filename),
        total_pages=page_count,
        description=description,
        uploader_id=current_user.id,
    )
    db.add(document_record)
    db.commit()
    db.refresh(document_record)

    return {
        "id": document_record.id,
        "uuid": document_dir.name,
        "original_filename": original_filename,
        "total_pages": page_count,
        "description": description,
        "upload_directory": document_dir.name,
        "pages": page_files,
        "original_url": f"/uploads/{document_dir.name}/{original_filename}",
    }
