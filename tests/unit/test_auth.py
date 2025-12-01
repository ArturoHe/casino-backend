# tests/unit/test_auth.py
import pytest
from fastapi.testclient import TestClient

def test_user_registration(client: TestClient):
    response = client.post("/auth/signup", json={
        "username": "testuser",
        "password": "testpass123",
        "email": "test@example.com",
        "name": "Test",
        "apellidos": "User"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Usuario creado exitosamente"

def test_user_login(client: TestClient):
    client.post("/auth/signup", json={
        "username": "loginuser", 
        "password": "loginpass123",
        "email": "login@example.com"
    })
    
    response = client.post("/auth/login", json={
        "username": "loginuser",
        "password": "loginpass123"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"