from dataclasses import dataclass


@dataclass
class User:
    username: str


def dep_current_user() -> User | None:
    return User(username="test_user")
