# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app
from app.database import get_session
from app.model import User

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", 
        connect_args={"check_same_thread": False}, 
        poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

@pytest.fixture
def auth_headers(client: TestClient):
    
    client.post("/auth/signup", json={
        "username": "testuser",
        "password": "testpass123",
        "email": "test@example.com",
        "name": "Test",
        "apellidos": "User"
    })
    
    # Login y obtener token
    login_response = client.post("/auth/login", json={
        "username": "testuser", 
        "password": "testpass123"
    })
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Ensure test user has some balance for game tests
    client.post("/v1/roulette/user/deposit", headers=headers, json={"amount": 100.0})
    return headers


@pytest.fixture
def admin_headers(client: TestClient):
    # Create admin user if not exists
    client.get("/auth/create-admin")
    # Login as admin
    login_response = client.post("/auth/login", json={
        "username": "admin",
        "password": "admin"
    })
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}