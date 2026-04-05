from dataclasses import dataclass
from typing import Dict, Optional

from app.security import hash_password, verify_password


@dataclass
class User:
    username: str
    password_hash: str


_USERS: Dict[str, User] = {}


def create_user(username: str, password: str) -> User:
    if username in _USERS:
        raise ValueError("User exists")
    u = User(username=username, password_hash=hash_password(password))
    _USERS[username] = u
    return u


def authenticate(username: str, password: str) -> bool:
    u = _USERS.get(username)
    if not u:
        return False
    return verify_password(password, u.password_hash)


def get_user(username: str) -> Optional[User]:
    return _USERS.get(username)
