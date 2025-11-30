# app/admin/service.py
from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel import Session, select

from app.model import CreditRequest, User
from sqlmodel import select

def create_credit_request(db: Session, user_id: int, amount: float, note: Optional[str]=None) -> CreditRequest:
    if amount <= 0:
        raise ValueError("Amount must be positive")
    req = CreditRequest(user_id=user_id, amount=float(amount), status="pending", note=note)
    db.add(req)
    db.commit()
    db.refresh(req)
    return req

def list_credit_requests(db: Session, status: Optional[str]=None) -> List[CreditRequest]:
    stmt = select(CreditRequest).order_by(CreditRequest.created_at.desc())
    if status:
        stmt = stmt.where(CreditRequest.status == status)
    return db.exec(stmt).all()

def get_credit_request(db: Session, request_id: int) -> Optional[CreditRequest]:
    stmt = select(CreditRequest).where(CreditRequest.id == request_id)
    return db.exec(stmt).one_or_none()

def approve_credit_request(db: Session, request_id: int, reviewer_user_id: int) -> CreditRequest:
    req = get_credit_request(db, request_id)
    if not req:
        raise ValueError("Request not found")
    if req.status != "pending":
        raise ValueError("Request already processed")

    # add amount to user's balance
    stmt = select(User).where(User.id == req.user_id)
    user = db.exec(stmt).one_or_none()
    if not user:
        raise ValueError("User not found")

    user.saldo = (user.saldo or 0.0) + float(req.amount)
    # store reviewer & timestamps
    req.status = "approved"
    req.reviewed_at = datetime.now(timezone.utc)
    req.reviewer_id = reviewer_user_id

    db.add(user)
    db.add(req)
    db.commit()
    db.refresh(user)
    db.refresh(req)
    return req

def deny_credit_request(db: Session, request_id: int, reviewer_user_id: int, note: Optional[str]=None) -> CreditRequest:
    req = get_credit_request(db, request_id)
    if not req:
        raise ValueError("Request not found")
    if req.status != "pending":
        raise ValueError("Request already processed")

    req.status = "denied"
    req.reviewed_at = datetime.now(timezone.utc)
    req.reviewer_id = reviewer_user_id
    if note:
        req.note = (req.note or "") + f" | Deny note: {note}"

    db.add(req)
    db.commit()
    db.refresh(req)
    return req
