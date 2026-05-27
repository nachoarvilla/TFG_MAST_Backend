import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from database import engine, get_db
from main import app
import models
from auth import hash_password

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_connection():
    connection = engine.connect()
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def db_session(db_connection):
    session = TestingSessionLocal(bind=db_connection)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def create_user(db_session):
    def _create_user(username: str, email: str, password: str, role: str = "user"):
        user = models.User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=role,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create_user


@pytest.fixture(scope="function")
def auth_token(client, create_user):
    username = "testuser"
    password = "password123"
    create_user(username=username, email="testuser@example.com", password=password)
    response = client.post(
        "/login",
        json={"username_or_email": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture(scope="function")
def root_token(client, create_user):
    username = "rootuser"
    password = "rootpassword"
    create_user(username=username, email="rootuser@example.com", password=password, role="admin")
    response = client.post(
        "/login",
        json={"username_or_email": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]
