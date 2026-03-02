# JSONL helper functions for reading and writing JSON files.
import json


def read_json(file_path: str) -> dict:
    """Read a JSON file and return a dictionary."""
    with open(file_path, "r") as f:
        return json.load(f)

def write_json(file_path: str, data: dict) -> None:
    """Write a dictionary to a JSON file."""
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

def read_jsonl(file_path: str) -> list[dict]:
    """Read a JSONL file and return a list of dictionaries."""
    data = []
    with open(file_path, "r") as f:
        for line in f:
            data.append(json.loads(line))
    return data

def write_jsonl(file_path: str, data: list[dict]) -> None:
    """Write a list of dictionaries to a JSONL file."""
    with open(file_path, "w") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")

def append_jsonl(file_path: str, item: dict) -> None:
    """Append a single dictionary to a JSONL file."""
    with open(file_path, "a") as f:
        f.write(json.dumps(item) + "\n")


def parse_json_safe(json_str: str) -> dict | list | None:
    """Parse a JSON string safely, returning None if parsing fails."""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None