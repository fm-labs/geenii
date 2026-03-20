import hashlib
import os
from typing import Annotated, Optional

import pydantic
from fastapi import Query, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette import status

from geenii.utils.mongodb import get_mongo_client

# ---------------------------------------------------------------------------
# User Deps
# ---------------------------------------------------------------------------

def _dummy_token(username: str) -> str:
    """Hash a username into a dummy bearer token (must match chat_client.make_token)."""
    return hashlib.sha256(username.encode()).hexdigest()

# Pre-built registry: token -> username.  Add entries for every dummy user you need.
DUMMY_USERS = ["alice", "bob", "charlie", "dummy_user", "admin"]
TOKEN_REGISTRY: dict[str, str] = {_dummy_token(u): u for u in DUMMY_USERS}


class User(pydantic.BaseModel):
    username: str
    is_active: bool = True


async def dep_current_user(
        #credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> User:
    """Resolve bearer token to a User via the dummy token registry."""
    #token = credentials.credentials
    #username = TOKEN_REGISTRY.get(token)
    #print(f"Authenticating token={token}, resolved username={username}")
    #if username is None:
    #    raise HTTPException(status_code=401, detail="Invalid or unknown bearer token")
    #return User(username=username)
    return User(username="testuser")  # TODO replace with real auth



# ---------------------------------------------------------------------------
# Token Auth
# ---------------------------------------------------------------------------

def dep_token_in_query(token: Annotated[str, Query]) -> str:
    """
    Dependency to extract token from query parameters.
    """
    return token

def dep_current_token_user(token: str = Depends(dep_token_in_query)) -> dict:
    """
    Dependency to get current user from token.
    For testing purposes, we accept any token that starts with "test-".
    """
    token = token.strip()
    if not token or token == "":
        raise Exception("Invalid token")

    # Simple token validation for testing
    if not token.startswith("test-"):
        raise Exception("Invalid token")
    test_username = token[5:]
    return {"username": test_username, "token": token}


# ---------------------------------------------------------------------------
# API Key Auth
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)

def _api_key() -> Optional[str]:
    return os.environ.get("GEENII_API_KEY")


async def require_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> None:
    key = _api_key()
    if key is None:
        return  # auth disabled
    if credentials is None or credentials.credentials != key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )



# def dep_mongo_client() -> 'MongoClient':
#     """
#     Dependency to get a MongoDB client.
#     """
#     return get_mongo_client(uri=config.MONGODB_URI)