from app.auth.utils import verify_password
from app.model import User
from sqlmodel import Session, select


def get_user(db: Session, username: str):
    statement = select(User).where(User.username == username)
    return db.exec(statement).first()
