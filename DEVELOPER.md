# geeniid

The geeniid is the service daemon that runs background services and provides an API for managing agents, tools and skills.
It is one of the core component of the OpenGeenii platform, responsible for executing AI agents and handling interactions.



## Developer Guide

### Run geeniid

```bash
uv run src/server.py
```

or with uvicorn:

```bash
uvicorn --app-dir ./src geenii.server.server:app --port 33311 --reload
```