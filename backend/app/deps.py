import uuid

from fastapi import Depends
from sqlalchemy.orm import Session

from .db import get_db
from .models import User

DEMO_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


def current_user(db: Session = Depends(get_db)) -> User:
    # shortcut: utilizador de demonstração fixo, sem autenticação; substituir por token/sessão em T076.
    user = db.get(User, DEMO_USER_ID)
    if user is None:
        user = User(id=DEMO_USER_ID, name="Demo")
        db.add(user)
        db.commit()
    return user
