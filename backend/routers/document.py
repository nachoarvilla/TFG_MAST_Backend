from pathlib import Path
from uuid import uuid4
import shutil

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
    stored_file_path = str(Path("uploads") / document_dir.name / original_filename)

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
        name=original_filename,
        file_path=stored_file_path,
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


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if document.uploader_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this document")

    # Extract UUID from file_path
    file_path = Path(document.file_path)
    if file_path.parts[0] != "uploads":
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid file path")

    uuid_dir_name = file_path.parent.name
    full_dir_path = UPLOADS_DIR / uuid_dir_name

    # Delete the directory
    if full_dir_path.exists():
        shutil.rmtree(full_dir_path)

    # Delete the database record
    db.delete(document)
    db.commit()
