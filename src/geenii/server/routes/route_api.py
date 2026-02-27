import os
from typing import List

from fastapi import APIRouter

from geenii.ai import enumerate_models, enumerate_providers
from geenii.config import APP_VERSION, get_user_data_dir
from geenii.utils.os_util import get_user_home_dir
from geenii.utils.system_util import get_system_report

router = APIRouter(prefix="/api", tags=["api"])

ALLOWED_ENV_VARS = ["PATH", "HOME", "USER", "USERNAME"]


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/info")
async def info() -> dict:
    ai_providers = enumerate_providers()
    ai_models = enumerate_models()

    data = dict({
        "app": {
            "version": APP_VERSION,
            "cwd": os.getcwd(),
            "user_home_dir": get_user_home_dir(),
            "data_dir": get_user_data_dir()
        },
        "config": {

        },
        "providers": ai_providers,
        "models": ai_models
    })

    # add system report
    # if not in DEV_MODE, remove the env variables from the report for security reasons
    report = get_system_report()
    if not os.environ.get("DEV_MODE", "0") == "1":
        if "env" in report:
            report["env"] = {k: v for k, v in report["env"].items() if k in ALLOWED_ENV_VARS}
    data.update({"system": report})

    return data
