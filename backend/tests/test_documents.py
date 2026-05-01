import io
import shutil
from pathlib import Path

import pytest
import fitz
from fastapi.testclient import TestClient

from models import Document
from routers.document import UPLOADS_DIR


@pytest.fixture(scope="function")
def sample_pdf():
    """Create a minimal valid PDF for testing."""
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n(Hello World) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000200 00000 n \ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n284\n%%EOF"
    return io.BytesIO(pdf_content)


@pytest.fixture(scope="function")
def cleanup_uploads():
    """Clean up uploads directory after tests."""
    yield
    # Do not clean up to avoid affecting local directory
    pass


class TestDocumentEndpoints:
    def test_upload_document_success(self, client: TestClient, auth_token: str, sample_pdf, cleanup_uploads):
        """Test successful document upload."""
        files = {"file": ("test.pdf", sample_pdf, "application/pdf")}
        data = {"description": "Test document"}
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.post("/documents", files=files, data=data, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["original_filename"] == "test.pdf"
        assert data["total_pages"] == 1
        assert data["description"] == "Test document"
        assert "uuid" in data
        assert "original_url" in data

        client.delete(f"/documents/{response.json()['id']}", headers=headers)

    def test_upload_document_thumbnail_has_fixed_width(self, client: TestClient, auth_token: str, sample_pdf, cleanup_uploads):
        """Test generated thumbnails keep a fixed width and preserve aspect ratio."""
        files = {"file": ("test.pdf", sample_pdf, "application/pdf")}
        data = {"description": "Test document"}
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.post("/documents", files=files, data=data, headers=headers)

        assert response.status_code == 201
        upload_uuid = response.json()["uuid"]
        thumbnail_path = UPLOADS_DIR / upload_uuid / "thumbnails" / "page_1.jpg"
        thumbnail = fitz.Pixmap(str(thumbnail_path))
        expected_height = 150 * 792 / 612

        assert thumbnail.width == 150
        assert abs(thumbnail.height - expected_height) <= 1

        client.delete(f"/documents/{response.json()['id']}", headers=headers)

    def test_upload_document_invalid_file_type(self, client: TestClient, auth_token: str, cleanup_uploads):
        """Test upload with invalid file type."""
        files = {"file": ("test.txt", io.BytesIO(b"not a pdf"), "text/plain")}
        data = {"description": "Test document"}
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.post("/documents", files=files, data=data, headers=headers)

        assert response.status_code == 400
        assert "Only PDF files are accepted" in response.json()["detail"]

    def test_upload_document_invalid_pdf(self, client: TestClient, auth_token: str, cleanup_uploads):
        """Test upload with invalid PDF content."""
        files = {"file": ("test.pdf", io.BytesIO(b"not a valid pdf"), "application/pdf")}
        data = {"description": "Test document"}
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.post("/documents", files=files, data=data, headers=headers)

        assert response.status_code == 400
        assert "not a valid PDF" in response.json()["detail"]

    def test_upload_document_empty_file(self, client: TestClient, auth_token: str, cleanup_uploads):
        """Test upload with empty file."""
        files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
        data = {"description": "Test document"}
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.post("/documents", files=files, data=data, headers=headers)

        assert response.status_code == 400
        assert "empty" in response.json()["detail"]

    def test_upload_document_wrong_extension(self, client: TestClient, auth_token: str, sample_pdf, cleanup_uploads):
        """Test upload with wrong file extension."""
        files = {"file": ("test.txt", sample_pdf, "application/pdf")}
        data = {"description": "Test document"}
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.post("/documents", files=files, data=data, headers=headers)

        assert response.status_code == 400
        assert "must have a .pdf extension" in response.json()["detail"]

    def test_get_document_success(self, client: TestClient, auth_token: str, db_session, sample_pdf, cleanup_uploads):
        """Test successful document retrieval."""
        # First upload a document
        files = {"file": ("test.pdf", sample_pdf, "application/pdf")}
        data = {"description": "Test document"}
        headers = {"Authorization": f"Bearer {auth_token}"}

        upload_response = client.post("/documents", files=files, data=data, headers=headers)

        assert upload_response.status_code == 201
        doc_id = upload_response.json()["id"]

        # Now get it
        response = client.get(f"/documents/{doc_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == doc_id
        assert data["name"] == "test.pdf"
        assert data["total_pages"] == 1
        assert data["uploader"] == "testuser"
        assert isinstance(data["uploader_id"], int)  # Just check it's an integer
        assert "created_at" in data
        assert "base_url" in data
        assert data["base_url"].endswith("/")

        client.delete(f"/documents/{upload_response.json()['id']}", headers=headers)

    def test_get_document_not_found(self, client: TestClient, auth_token: str):
        """Test get non-existent document."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.get("/documents/999", headers=headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_update_document_success(self, client: TestClient, auth_token: str, db_session, sample_pdf, cleanup_uploads):
        """Test successful document update."""
        # Upload document
        files = {"file": ("test.pdf", sample_pdf, "application/pdf")}
        data = {"description": "Test document"}
        headers = {"Authorization": f"Bearer {auth_token}"}

        upload_response = client.post("/documents", files=files, data=data, headers=headers)
        doc_id = upload_response.json()["id"]

        # Update it
        update_data = {"name": "updated.pdf", "description": "Updated description"}
        response = client.put(f"/documents/{doc_id}", json=update_data, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == doc_id
        assert data["name"] == "updated.pdf"
        assert data["description"] == "Updated description"
        assert "updated.pdf" in data["file_path"]

        client.delete(f"/documents/{upload_response.json()['id']}", headers=headers)

    def test_update_document_not_found(self, client: TestClient, auth_token: str):
        """Test update non-existent document."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        update_data = {"name": "new.pdf"}

        response = client.put("/documents/999", json=update_data, headers=headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_update_document_unauthorized(self, client: TestClient, auth_token: str, root_token: str, db_session, sample_pdf, cleanup_uploads):
        """Test update document by non-owner."""
        # Upload with auth_token (user 1)
        files = {"file": ("test.pdf", sample_pdf, "application/pdf")}
        data = {"description": "Test document"}
        headers = {"Authorization": f"Bearer {auth_token}"}

        upload_response = client.post("/documents", files=files, data=data, headers=headers)
        doc_id = upload_response.json()["id"]

        # Try to update with root_token (different user)
        headers_root = {"Authorization": f"Bearer {root_token}"}
        update_data = {"name": "hacked.pdf"}
        response = client.put(f"/documents/{doc_id}", json=update_data, headers=headers_root)

        assert response.status_code == 403
        assert "Not authorized to update this document" in response.json()["detail"]

        client.delete(f"/documents/{upload_response.json()['id']}", headers=headers)

    def test_delete_document_success(self, client: TestClient, auth_token: str, db_session, sample_pdf, cleanup_uploads):
        """Test successful document deletion."""
        # Upload document
        files = {"file": ("test.pdf", sample_pdf, "application/pdf")}
        data = {"description": "Test document"}
        headers = {"Authorization": f"Bearer {auth_token}"}

        upload_response = client.post("/documents", files=files, data=data, headers=headers)
        doc_id = upload_response.json()["id"]

        # Delete it
        response = client.delete(f"/documents/{doc_id}", headers=headers)

        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/documents/{doc_id}", headers=headers)
        assert get_response.status_code == 404

    def test_delete_document_not_found(self, client: TestClient, auth_token: str):
        """Test delete non-existent document."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        response = client.delete("/documents/999", headers=headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_delete_document_unauthorized(self, client: TestClient, auth_token: str, root_token: str, db_session, sample_pdf, cleanup_uploads):
        """Test delete document by non-owner."""
        # Upload with auth_token
        files = {"file": ("test.pdf", sample_pdf, "application/pdf")}
        data = {"description": "Test document"}
        headers = {"Authorization": f"Bearer {auth_token}"}

        upload_response = client.post("/documents", files=files, data=data, headers=headers)
        doc_id = upload_response.json()["id"]

        # Try to delete with root_token
        headers_root = {"Authorization": f"Bearer {root_token}"}
        response = client.delete(f"/documents/{doc_id}", headers=headers_root)

        assert response.status_code == 403
        assert "Not authorized to delete this document" in response.json()["detail"]

        client.delete(f"/documents/{upload_response.json()['id']}", headers=headers)
