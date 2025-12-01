# tests/unit/test_roulette.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

def test_create_roulette_session(client: TestClient, auth_headers):
    """Test creación de sesión de ruleta"""
    # Act
    response = client.post("/v1/roulette/session", headers=auth_headers)
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "server_seed_hash" in data
    assert isinstance(data["session_id"], int)

def test_place_roulette_bet_success(client: TestClient, auth_headers):
    """Test apuesta exitosa en ruleta"""
    # Arrange - Crear sesión primero
    session_response = client.post("/v1/roulette/session", headers=auth_headers)
    session_id = session_response.json()["session_id"]
    
    # Act - Hacer apuesta
    bet_data = {
        "client_seed": "test_seed_123",
        "bet": {
            "type": "color",
            "side": "red",
            "amount": 10.0
        }
    }
    
    response = client.post(
        f"/v1/roulette/session/{session_id}/bet",
        headers=auth_headers,
        json=bet_data
    )
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "spin" in data
    assert "bet_result" in data
    assert "user" in data
    assert "pocket" in data["spin"]
    assert "color" in data["spin"]

def test_roulette_bet_insufficient_balance(client: TestClient, auth_headers):
    """Test que impide apuestas sin saldo suficiente"""
    # Arrange
    session_response = client.post("/v1/roulette/session", headers=auth_headers)
    session_id = session_response.json()["session_id"]
    
    # Act - Intentar apostar cantidad enorme
    bet_data = {
        "client_seed": "test_seed",
        "bet": {
            "type": "color", 
            "side": "red",
            "amount": 1000000.0  # Monto imposible
        }
    }
    
    response = client.post(
        f"/v1/roulette/session/{session_id}/bet",
        headers=auth_headers, 
        json=bet_data
    )
    
    # Assert
    assert response.status_code == 400
    assert "saldo" in response.json()["detail"].lower() or "balance" in response.json()["detail"].lower()

def test_roulette_bet_validation_invalid_bet_type(client: TestClient, auth_headers):
    """Test validación de tipos de apuesta inválidos"""
    # Arrange
    session_response = client.post("/v1/roulette/session", headers=auth_headers)
    session_id = session_response.json()["session_id"]
    
    # Act - Tipo de apuesta inválido
    bet_data = {
        "client_seed": "test_seed",
        "bet": {
            "type": "invalid_bet_type",  # Tipo no existente
            "side": "red", 
            "amount": 10.0
        }
    }
    
    response = client.post(
        f"/v1/roulette/session/{session_id}/bet",
        headers=auth_headers,
        json=bet_data
    )
    
    # Assert
    assert response.status_code == 400

def test_roulette_spin_provably_fair_verification(client: TestClient, auth_headers):
    """Test que verifica el sistema provably fair"""
    # Arrange
    session_response = client.post("/v1/roulette/session", headers=auth_headers)
    session_id = session_response.json()["session_id"]
    
    # Act - Hacer apuesta con seed específico
    bet_data = {
        "client_seed": "fixed_seed_for_testing",
        "bet": {
            "type": "straight",
            "number": 17,
            "amount": 5.0
        }
    }
    
    response = client.post(
        f"/v1/roulette/session/{session_id}/bet", 
        headers=auth_headers,
        json=bet_data
    )
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    
    # Verificar que todos los elementos del sistema provably fair están presentes
    assert "hmac_hex" in data["spin"]
    assert "nonce" in data["spin"]
    assert "pocket" in data["spin"]
    assert "color" in data["spin"]
    
    # El pocket debe estar entre 0 y 36
    assert 0 <= data["spin"]["pocket"] <= 36
    
    # El color debe ser consistente con el pocket
    pocket = data["spin"]["pocket"]
    if pocket == 0:
        assert data["spin"]["color"] == "green"
    elif pocket in [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]:
        assert data["spin"]["color"] == "red"
    else:
        assert data["spin"]["color"] == "black"

def test_roulette_different_bet_types(client: TestClient, auth_headers):
    """Test diferentes tipos de apuesta"""
    # Arrange
    session_response = client.post("/v1/roulette/session", headers=auth_headers)
    session_id = session_response.json()["session_id"]
    
    bet_types = [
        {"type": "color", "side": "red", "amount": 5.0},
        {"type": "odd_even", "side": "odd", "amount": 5.0},
        {"type": "low_high", "side": "low", "amount": 5.0},
        {"type": "dozen", "which": 1, "amount": 5.0},
        {"type": "column", "which": 2, "amount": 5.0},
        {"type": "straight", "number": 17, "amount": 5.0}
    ]
    
    for bet in bet_types:
        # Act
        response = client.post(
            f"/v1/roulette/session/{session_id}/bet",
            headers=auth_headers,
            json={"client_seed": "test_seed", "bet": bet}
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "bet_result" in data
        assert "won" in data["bet_result"]
        assert "payout" in data["bet_result"]

def test_roulette_session_not_found(client: TestClient, auth_headers):
    """Test apuesta en sesión inexistente"""
    # Act - Sesión que no existe
    response = client.post(
        "/v1/roulette/session/9999/bet",
        headers=auth_headers,
        json={
            "client_seed": "test_seed",
            "bet": {"type": "color", "side": "red", "amount": 10.0}
        }
    )
    
    # Assert
    assert response.status_code == 404

def test_roulette_list_spins(client: TestClient, auth_headers):
    """Test listado de spins de una sesión"""
    # Arrange - Crear sesión y hacer algunas apuestas
    session_response = client.post("/v1/roulette/session", headers=auth_headers)
    session_id = session_response.json()["session_id"]
    
    # Hacer algunas apuestas
    for i in range(3):
        client.post(
            f"/v1/roulette/session/{session_id}/bet",
            headers=auth_headers,
            json={
                "client_seed": f"seed_{i}",
                "bet": {"type": "color", "side": "red", "amount": 5.0}
            }
        )
    
    # Act - Listar spins
    response = client.get(f"/v1/roulette/session/{session_id}/spins", headers=auth_headers)
    
    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "spins" in data
    assert "session_id" in data
    assert len(data["spins"]) == 3
    assert data["session_id"] == session_id

def test_roulette_bet_without_authentication(client: TestClient):
    """Test que impide apostar sin autenticación"""
    # Act
    response = client.post(
        "/v1/roulette/session/1/bet",
        json={
            "client_seed": "test_seed",
            "bet": {"type": "color", "side": "red", "amount": 10.0}
        }
    )
    
    # Assert
    assert response.status_code == 401