from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import create_user, authenticate
from app.security import create_access_token


router = APIRouter()


class RegisterIn(BaseModel):
    username: str
    password: str


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(body: RegisterIn):
    try:
        create_user(body.username, body.password)
    except ValueError:
        raise HTTPException(status_code=409, detail="User already exists")
    return {"ok": True}


@router.post("/login")
def login(body: LoginIn):
    if not authenticate(body.username, body.password):
        raise HTTPException(status_code=401, detail="Invalid username/password")
    token = create_access_token(body.username)
    return {"access_token": token, "token_type": "bearer"}
