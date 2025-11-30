# manual_check.py
from sqlmodel import Session, select
from app.database import engine
from app.model import CreditRequest

with Session(engine) as s:
    reqs = s.exec(select(CreditRequest)).all()
    for r in reqs:
        print(r.id, r.user_id, r.amount, r.status, r.created_at)
