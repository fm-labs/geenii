import json
import os
from fastapi import APIRouter

from geenii.config import DATA_DIR

router = APIRouter(prefix="/agents", tags=["agents"])

def read_agents_from_file():
    fp = f"{DATA_DIR}/agents.json"
    if os.path.exists(fp):
        try:
            with open(fp, "r") as f:
                agents = json.load(f)
                return agents
        except Exception as e:
            print(f"Error reading agents from file: {e}")
            return []
    else:
        print(f"Error reading agents from file: {fp}")
        return []


@router.get("/")
def list_agents():
    """
    List all available agents.
    """
    # For demonstration purposes, return static agents.
    # In a real application, this could fetch from a database or configuration.
    agents = read_agents_from_file()
    return {"agents": agents}