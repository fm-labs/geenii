from typing import Annotated

from fastapi import Query, Depends

from geenii import config
from geenii.db.mongodb import get_mongo_client


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


def dep_current_user() -> dict:
    """
    Dependency to get current user.
    For testing purposes, we return a fixed user.
    """
    return {"username": "testuser", "token": "test-token"}


def dep_mongo_client() -> 'MongoClient':
    """
    Dependency to get a MongoDB client.
    """
    return get_mongo_client(uri=settings.MONGODB_URI)