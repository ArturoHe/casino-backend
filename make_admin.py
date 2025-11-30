# make_admin.py
from sqlmodel import Session, select
from app.database import engine
from app.model import User

with Session(engine) as s:
    u = s.exec(select(User).where(User.username == "admin1")).one_or_none()
    if not u:
        print("admin1 no encontrado")
    else:
        u.role = "Admin"
        s.add(u)
        s.commit()
        print("admin1 actualizado a Admin")
