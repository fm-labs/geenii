import os
from contextlib import asynccontextmanager
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rich.logging import RichHandler

from geenii.apps import AppRegistry
from geenii.chat.chat_server_ctx import ChatServerState

from geenii.config import APP_VERSION, DATA_DIR
# from geenii.server.middleware.proxy_middleware import ProxyMiddleware
# from geenii.server.middleware.request_logger_middleware import RequestLoggerMiddleware
from geenii.server.router import app_router
from geenii.rt import init_builtin_tools, init_mcp_server_tools
from geenii.supervisor import Supervisor, ProcConfig
from geenii.tools import ToolRegistry

# logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    handlers=[
        RichHandler(
            show_time=True,  # show timestamps
            omit_repeated_times=False,  # show timestamp every line
            show_level=True,
            show_path=True,  # hide file path
            rich_tracebacks=False,  # beautiful exception tracebacks
        )
    ]
)

# redis_listener_stop_event = asyncio.Event()


async def initialize_tool_registry():
    print("Initializing tool registry...")
    registry = ToolRegistry()
    init_builtin_tools(registry)
    await init_mcp_server_tools(registry)
    return registry


async def initialize_supervisor():
    print("Initializing supervisor...")
    supervisor = Supervisor()
    # await supervisor.ensure("geenii_startup", ProcConfig(name="geenii_startup", cmd=["/bin/bash", "-c", "echo 'Geenii API Server Started'; echo `date` >> data/startup.log"], restart=False))
    # await supervisor.ensure("geenii_beat", ProcConfig(name="geenii_beat", cmd=["/bin/bash", "-c", "while true; do echo `date`; sleep 3; done"]))
    return supervisor

async def initialize_app_registry():
    print("Initializing apps...")
    apps = AppRegistry()
    apps.load_apps_from_directory(f"{DATA_DIR}/apps")
    print(f"Initialized {len(apps.apps)} apps: {list(apps.apps.keys())}")
    return apps

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Chat Server
    app.state.chat_server = ChatServerState(app)
    await app.state.chat_server.startup()
    # Tool Registry
    app.state.tool_registry = await initialize_tool_registry()
    # Supervisor
    app.state.supervisor = await initialize_supervisor()
    # Apps
    app.state.app_registry = await initialize_app_registry()
    # Redis
    # task = asyncio.create_task(redis_pubsub_listener(redis_listener_stop_event))
    try:
        yield
    finally:
        await app.state.chat_server.stop()
        await app.state.supervisor.stop()
        # cleanup tool registry if needed
        if app.state.tool_registry:
            del app.state.tool_registry

        # signal the Redis listener to stop
        # redis_listener_stop_event.set()
        # task.cancel()
        # with contextlib.suppress(Exception):
        #    await task
        pass


app = FastAPI(lifespan=lifespan, title="Geenii API", version=APP_VERSION)

# Note: Middlewares are executed in reverse order of addition (LIFO)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# # Request Logger Middleware
# app.add_middleware(
#     RequestLoggerMiddleware,
#     log_body=True,
#     log_headers=True,
#     max_body_size=5000,
#     exclude_paths=["/health", "/docs", "/openapi.json"],
#     sensitive_headers=["authorization", "x-api-key", "cookie"],
#     log_file="data/logs/app_requests.log"
# )
# # Proxy Middleware for OpenAI API
# app.add_middleware(
#     ProxyMiddleware,
#     target_url="https://api.openai.com/",
#     path_prefix="/openai/",
#     timeout=30.0
# )
# # Proxy Middleware for Anthropic API
# app.add_middleware(
#     ProxyMiddleware,
#     target_url="https://api.anthropic.com/",
#     path_prefix="/anthropic/",
#     timeout=30.0
# )

app.include_router(app_router, prefix="")

# # WebSocket endpoint
# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket, user = Security(dep_current_token_user)):
#
#     print(f"WebSocket connection request from user: {user}")
#
#     # get the request headers and query parameters
#     headers = websocket.headers
#     query_params = websocket.query_params
#     print(f"WebSocket connection request", headers, query_params)
#
#     context = {
#         "user": user,
#     }
#
#     await manager.connect(websocket)
#     # await manager.broadcast(json.dumps({
#     #     "type": "client_connected",
#     #     #"client_id": client_id,
#     #     #"message": f"Client {client_id} connected"
#     # }))
#     # await manager.send_json(websocket, {
#     #     "type": "event",
#     #     "event": "connected",
#     #     "data": {
#     #         "message": "WebSocket connection established"
#     #     }
#     # })
#     try:
#         # print number of active connections
#         print(f"Active WebSocket connections: {len(manager.active_connections)}")
#
#         while True:
#             # Receive message from client
#             data = await websocket.receive_text()
#             await process_message(websocket, data, context=context)
#
#     except WebSocketDisconnect:
#         manager.disconnect(websocket)
#         # await manager.broadcast(json.dumps({
#         #     "type": "client_disconnected",
#         #     "message": "A client disconnected"
#         # }))
#         print("WebSocket Disconnected")
#     finally:
#         # Cleanup all topics for this socket
#         async with subs_lock:
#             topics_to_remove = []
#             for topic, sockets in subscriptions.items():
#                 if websocket in sockets:
#                     sockets.remove(websocket)
#                     if not sockets:
#                         topics_to_remove.append(topic)
#             for topic in topics_to_remove:
#                 del subscriptions[topic]
#
#
# def test_websocket():
#     client = TestClient(app)
#     with client.websocket_connect("/ws") as websocket:
#         data = websocket.receive_json()
#         #assert data == {"msg": "Hello WebSocket"}
#         print("WebSocket Test Received:", data)
#
#
# if __name__ == "__main__":
#     test_websocket()

if __name__ == "__main__":
    # ensure data directories exist
    os.makedirs(f"{DATA_DIR}/apps", exist_ok=True)
    os.makedirs(f"{DATA_DIR}/cache", exist_ok=True)
    # os.makedirs(f"{DATA_DIR}/sessions", exist_ok=True)
    # os.makedirs(f"{DATA_DIR}/tmp", exist_ok=True)

    GEENII_SERVER_HOST = os.getenv("GEENII_SERVER_HOST", "127.0.0.1")
    GEENII_SERVER_PORT = os.getenv("GEENII_SERVER_PORT", "13030")
    uvicorn.run(app, host=GEENII_SERVER_HOST, port=int(GEENII_SERVER_PORT),
                workers=1, reload=False, log_level="info")

# async def serve():
#     config = uvicorn.Config(app, host="127.0.0.1", port=13030, log_level="info")
#     server = uvicorn.Server(config)
#
#     # Custom shutdown on SIGTERM/SIGINT
#     loop = asyncio.get_running_loop()
#     for sig in (signal.SIGTERM, signal.SIGINT):
#         print(f"Registering signal handler for {sig}")
#         loop.add_signal_handler(sig, server.handle_exit, sig, None)
#
#     await server.serve()
#
# if __name__ == "__main__":
#     asyncio.run(serve())
