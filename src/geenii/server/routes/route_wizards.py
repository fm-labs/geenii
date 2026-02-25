import json
import os
from fastapi import APIRouter

from geenii.config import DATA_DIR

router = APIRouter(prefix="/wizards", tags=["wizards"])

def read_wizards_from_file():
    fp = f"{DATA_DIR}/wizards.json"
    if os.path.exists(fp):
        try:
            with open(fp, "r") as f:
                wizards = json.load(f)
                return wizards
        except Exception as e:
            print(f"Error reading wizards from file: {e}")
            return []
    else:
        print(f"Error reading wizards from file: {fp}")
        return []


@router.get("/")
def list_wizards():
    """
    List all available wizards.
    """
    # For demonstration purposes, return static wizards.
    # In a real application, this could fetch from a database or configuration.
    wizards = read_wizards_from_file()
    return {"wizards": wizards}