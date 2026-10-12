"""Token interno compartido con la API (FE011, criterio 5)."""
import hmac

from fastapi import HTTPException, Request, status


def internal_token_guard(token: str):
    expected = f"Bearer {token}".encode()

    def require_internal_token(request: Request) -> None:
        # Comparación como bytes: `compare_digest` con `str` no ASCII lanza `TypeError` (lección 7).
        received = request.headers.get("authorization", "").encode()
        if not hmac.compare_digest(received, expected):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token interno no válido")

    return require_internal_token
