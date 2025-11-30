# app/credits/routes.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from sqlmodel import Session, select

from app.database import get_session
from app.admin import service as admin_service   # reusa la lógica ya creada
from app.auth.services import get_user_from_token

from fastapi.security import OAuth2PasswordBearer

router = APIRouter(prefix="/v1/credits", tags=["credits"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

class CreditRequestIn(BaseModel):
    amount: float = Field(..., gt=0, description="Monto positivo a solicitar")
    note: Optional[str] = None

class CreditRequestOut(BaseModel):
    id: int
    user_id: int
    amount: float
    status: str

@router.post("/request", response_model=CreditRequestOut)
def create_credit_request_endpoint(payload: CreditRequestIn, token: str = Depends(oauth2_scheme), db: Session = Depends(get_session)):
    """
    Endpoint para que un usuario autenticado solicite crédito.
    - Valida token JWT y obtiene el usuario.
    - No permite solicitudes con amount <= 0 (Pydantic lo valida).
    - Evita crear nueva solicitud si ya tiene una 'pending' existente.
    """
    user = get_user_from_token(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    # Comprobamos en DB si existen pendientes para este usuario
    from app.model import CreditRequest
    stmt = select(CreditRequest).where(CreditRequest.user_id == user.id, CreditRequest.status == "pending")
    existing = db.exec(stmt).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe una solicitud pendiente. Espera a que se procese.")

    # Crear solicitud usando la lógica del servicio admin
    try:
        req = admin_service.create_credit_request(db, user.id, payload.amount, payload.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return CreditRequestOut(id=req.id, user_id=req.user_id, amount=req.amount, status=req.status)
