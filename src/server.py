import asyncio
import contextlib
import signal
from contextlib import asynccontextmanager

import uvicorn

from fastapi import FastAPI, Security
from fastapi.middleware.cors import CORSMiddleware

from fastmcp import Client

from starlette.testclient import TestClient
from starlette.websockets import WebSocket, WebSocketDisconnect

from geenii.server.deps import dep_current_token_user
# from geenii.server.middleware.proxy_middleware import ProxyMiddleware
# from geenii.server.middleware.request_logger_middleware import RequestLoggerMiddleware
from geenii.server.router import app_router
from geenii.server.routes.route_ws import manager, process_message, subs_lock, subscriptions, redis_pubsub_listener
from geenii.settings import APP_VERSION


#redis_listener_stop_event = asyncio.Event()

@asynccontextmanager
async def lifespan(app: FastAPI):
    #task = asyncio.create_task(redis_pubsub_listener(redis_listener_stop_event))
    try:
        yield
    finally:
        #redis_listener_stop_event.set()
        #task.cancel()
        #with contextlib.suppress(Exception):
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
   uvicorn.run(app, host="127.0.0.1", port=13030, workers=1, reload=False, log_level="info")

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