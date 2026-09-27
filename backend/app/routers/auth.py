from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app import auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    permissions: list[str]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


def _user_out(user: auth.User) -> UserOut:
    permissions = auth.get_store().permissions_for(user.role)
    return UserOut(id=user.id, name=user.name, email=user.email, role=user.role,
                   permissions=[p for p in auth.ALL_PERMISSIONS if p in permissions])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    user = auth.authenticate(body.email, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")
    return LoginResponse(access_token=auth.create_token(user), user=_user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: auth.User = Depends(auth.current_user)) -> UserOut:
    return _user_out(user)
