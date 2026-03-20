import asyncio
import json
from collections import defaultdict
from typing import DefaultDict, Set
from typing import List

import pydantic
import redis.asyncio as redis
from fastapi import WebSocket, APIRouter

from geenii import ai
from geenii.datamodels import CompletionRequest

# topic -> websockets subscribed to that topic (per process)
subscriptions: DefaultDict[str, Set[WebSocket]] = defaultdict(set)

# Track what this socket subscribed to so we can clean up on disconnect
user_topics: DefaultDict[str, set[str]] = defaultdict(set)

# A lock to avoid concurrent mutation surprises while broadcasting / disconnecting
subs_lock = asyncio.Lock()

REDIS_URL = "redis://localhost:13379/0"
CHANNEL_PATTERN = "topic:*"

# Store active WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        print("Accepting WebSocket connection")
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, websocket: WebSocket, message: str):
        await websocket.send_text(message)

    async def send_json(self, websocket: WebSocket, data: dict):
        await websocket.send_json(data)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Remove dead connections
                self.active_connections.remove(connection)


manager = ConnectionManager()
router = APIRouter(prefix="/ws", tags=["websocket"])

class JsonRpcError(pydantic.BaseModel):
    code: int
    message: str
    data: dict | None = None

class JsonRpcRequest(pydantic.BaseModel):
    jsonrpc: str
    method: str
    params: dict | None = None
    id: int | str | None = None

class JsonRpcResponse(pydantic.BaseModel):
    jsonrpc: str = "2.0"
    result: dict | str | None = None
    error: JsonRpcError | None = None
    id: int | str | None = None


class JsonRpcException(Exception):
    def __init__(self, error: tuple[int, str], data: dict | None = None):
        self.code = error[0]
        self.message = error[1]
        self.data = data

    def to_jsonrpc_error(self) -> JsonRpcError:
        return JsonRpcError(code=self.code, message=self.message, data=self.data)

    def to_dict(self) -> dict:
        error_dict = {
            "code": self.code,
            "message": self.message
        }
        if self.data is not None:
            error_dict["data"] = self.data
        return error_dict

#type JsonRpcErrorCode = tuple[int, str]
# Standard error codes
JSON_RPC_E_PARSE_ERROR = (-32700, "Parse error")
JSON_RPC_E_INVALID_REQUEST = (-32600, "Invalid Request")
JSON_RPC_E_METHOD_NOT_FOUND = (-32601, "Method not found")
JSON_RPC_E_INVALID_PARAMS = (-32602, "Invalid params")
JSON_RPC_E_INTERNAL_ERROR = (-32603, "Internal error")
# Reserved for implementation-defined server-errors (-32000 to -32099)
JSON_RPC_E_SERVER_ERROR = (-32000, "Server error")
JSON_RPC_E_SERVER_OVERLOAD = (-32001, "Server overload")
JSON_RPC_E_RATE_LIMIT_EXCEEDED = (-32002, "Rate limit exceeded")
JSON_RPC_E_SESSION_EXPIRED = (-32003, "Session expired")
JSON_RPC_E_METHOD_NOT_READY = (-32004, "Method not ready")
# Implementation-specific error codes
JSON_RPC_E_INVALID_BATCH_REQUEST = (-32040, "Invalid batch request")
JSON_RPC_E_CONTENT_TYPE_ERROR = (-32050, "Content-Type error")
JSON_RPC_E_TRANSPORT_ERROR = (-32060, "Transport error")
JSON_RPC_E_TIMEOUT_ERROR = (-32070, "Timeout error")


rpc_message_handlers = dict()
rpc_message_handlers["ping"] = lambda params,ws: "pong"
rpc_message_handlers["hello"] = lambda params,ws: "hello"
rpc_message_handlers["echo"] = lambda params,ws: params

def handle_sleep(params, ws: WebSocket):
    import time
    print("Handle sleep with params:", params)
    sleep_time = params.get("timeout", 5)
    time.sleep(sleep_time)
    return {"status": "completed", "slept_for": sleep_time}
rpc_message_handlers["sleep"] = handle_sleep

def handle_loop(params, ws: WebSocket):
    import time
    print("Handle loop with params:", params)
    loop_count = params.get("count", 5)
    interval = params.get("interval", 1)
    for i in range(loop_count):
        print(f"Loop {i+1}/{loop_count}")
        time.sleep(interval)
    return {"status": "completed", "loops": loop_count, "interval": interval}

def handle_ai_completion(params, ws: WebSocket):
    print("Handle AI completion with params:", params)
    args = CompletionRequest.model_validate(params)
    args.stream = False
    result = ai.generate_completion(args)
    print("Result:", result)
    return result.model_dump()
rpc_message_handlers["ai/completion"] = handle_ai_completion

async def handle_topics_subscribe(params, ws: WebSocket):
    topic = params.get("topic")
    topic = "topic:" + topic if not topic.startswith("topic:") else topic
    async with subs_lock:
        subscriptions[topic].add(ws)
    #my_topics.add(topic)
    return {"ok": True, "subscribed": topic}
rpc_message_handlers["topics/subscribe"] = handle_topics_subscribe

async def handle_topics_unsubscribe(params, ws: WebSocket):
    topic = params.get("topic")
    topic = "topic:" + topic if not topic.startswith("topic:") else topic
    async with subs_lock:
        subscriptions[topic].discard(ws)
        if topic in subscriptions and not subscriptions[topic]:
            subscriptions.pop(topic, None)
    #my_topics.discard(topic)
    return {"ok": True, "unsubscribed": topic}
rpc_message_handlers["topics/unsubscribe"] = handle_topics_unsubscribe


async def handle_topics_publish(params, ws: WebSocket):
    topic = params.get("topic")
    topic = "topic:" + topic if not topic.startswith("topic:") else topic
    message = params.get("message", "")
    #await fanout(topic, message) # direct fanout
    print("Publishing to Redis Pub/Sub:", topic, message)
    await publish_to_redis_pubsub(topic, message)
    return {"ok": True, "published": topic}
rpc_message_handlers["topics/publish"] = handle_topics_publish


async def process_message(websocket: WebSocket, data: str | dict | list, context: dict):
    # Check if the message is JSON
    # Check if the message is a valid JSON-RPC 2.0 message
    # Following the JSON-RPC 2.0 specification
    # --> {"jsonrpc": "2.0", "method": "subtract", "params": {"minuend": 42, "subtrahend": 23}, "id": 3}
    # <-- {"jsonrpc": "2.0", "result": 19, "id": 3}

    print("--> Processing JSON-RPC message:", data)
    message = None # Parsed JSON-RPC message
    msgid = None
    try:
        if isinstance(data, str):
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                raise JsonRpcException(JSON_RPC_E_PARSE_ERROR)

        if isinstance(message, list):
            # If the message is a batch request, process each item
            for item in message:
                if not isinstance(item, dict) or "jsonrpc" not in item or item.get("jsonrpc") != "2.0":
                    #raise ValueError("Invalid JSON-RPC 2.0 batch message format")
                    raise JsonRpcException(JSON_RPC_E_INVALID_BATCH_REQUEST)
                await process_message(websocket, item, context)
            return

        if not isinstance(message, dict) \
                or "jsonrpc" not in message or message.get("jsonrpc") != "2.0":
            raise JsonRpcException(JSON_RPC_E_INVALID_REQUEST)

        msgid = message.get("id")
        method = message.get("method")
        params = message.get("params")

        # resolve & invoke method handler
        if method is None or method == "":
            #raise ValueError("Missing 'method' in JSON-RPC 2.0 message")
            raise JsonRpcException(JSON_RPC_E_INVALID_REQUEST)
        handler = rpc_message_handlers.get(method)
        if handler is None:
            raise JsonRpcException(JSON_RPC_E_METHOD_NOT_FOUND)

        if asyncio.iscoroutinefunction(handler):
            result = await handler(params, websocket)
        else:
            # run sync handler on thread pool to avoid blocking event loop
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, handler, params, websocket)

        print("JSON-RPC method handled:", method, "result:", result)
        if msgid is not None:
            res = JsonRpcResponse(result=result, id=msgid)
            await manager.send_json(websocket, res.model_dump(exclude_none=True))
    except JsonRpcException as e:
        res = JsonRpcResponse(error=e.to_jsonrpc_error(), id=msgid)
        await manager.send_json(websocket, res.model_dump(exclude_none=True))
    except Exception as e:
        print("Unexpected error processing JSON-RPC message:", str(e))
        error = JsonRpcException(JSON_RPC_E_INTERNAL_ERROR, data={"exception": str(e)})
        res = JsonRpcResponse(error=error.to_jsonrpc_error(), id=msgid)
        await manager.send_json(websocket, res.model_dump(exclude_none=True))



# def ws_handler(websocket: WebSocket):
#     """
#     This function handles the WebSocket connection and communication.
#     It receives messages from the client, processes them, and sends responses back.
#     """
#     async def handle():
#         await manager.connect(websocket)
#         try:
#             while True:
#                 data = await websocket.receive_text()
#                 await handle_ws_message(websocket, data)
#         except WebSocketDisconnect:
#             manager.disconnect(websocket)
#             await manager.broadcast("A client disconnected")
#
#     return handle


# # WebSocket with client ID support
# @router.websocket("/ws/{client_id}")
# async def websocket_with_id(websocket: WebSocket, client_id: str):
#     await manager.connect(websocket)
#     await manager.broadcast(json.dumps({
#         "type": "client_connected",
#         "client_id": client_id,
#         "message": f"Client {client_id} connected"
#     }))
#
#     try:
#         while True:
#             data = await websocket.receive_text()
#             await process_message(websocket, data)
#             # await manager.broadcast(json.dumps({
#             #     "type": "message",
#             #     "client_id": client_id,
#             #     "data": data
#             # }))
#     except WebSocketDisconnect:
#         manager.disconnect(websocket)
#         await manager.broadcast(json.dumps({
#             "type": "client_disconnected",
#             "client_id": client_id,
#             "message": f"Client {client_id} disconnected"
#         }))


@router.post("/broadcast")
async def broadcast_message(message: str):
    """REST endpoint to broadcast a message to all WebSocket clients"""
    await manager.broadcast(json.dumps({
        "type": "broadcast",
        "message": message
    }))
    return {"message": f"Broadcasted: {message}"}


async def publish_to_redis_pubsub(topic: str, payload: str) -> None:
    """
    Publish payload to Redis channel for topic.
    """
    r = get_redis_client()
    await r.publish(topic, payload)
    await r.aclose()


async def fanout_message_to_ws_subscribers(topic: str, payload: str) -> None:
    """
    Send payload to all sockets subscribed to topic.
    Drops dead sockets.
    """
    async with subs_lock:
        sockets = list(subscriptions.get(topic, set()))

    print("Fanning out to topic:", topic, "sockets:", len(sockets), "payload:", payload)

    if not sockets:
        return

    dead: list[WebSocket] = []
    for ws in sockets:
        try:
            await ws.send_text(json.dumps({"type": "notification", "topic": topic, "payload": payload}))
        except Exception:
            dead.append(ws)

    if dead:
        async with subs_lock:
            for ws in dead:
                subscriptions[topic].discard(ws)
            if topic in subscriptions and not subscriptions[topic]:
                subscriptions.pop(topic, None)


def get_redis_client() -> redis.Redis:
    """
    Get a Redis client instance.
    """
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


async def redis_pubsub_listener(stop_event: asyncio.Event) -> None:
    """
    Listens to Redis Pub/Sub and forwards messages to subscribed WebSockets.
    Reconnects on transient errors.
    """
    while not stop_event.is_set():
        r = get_redis_client()
        pubsub = r.pubsub()

        try:
            await pubsub.psubscribe(CHANNEL_PATTERN)
            # Consume messages until stop or error
            while not stop_event.is_set():
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not msg:
                    continue

                # msg example for psubscribe:
                # {"type":"pmessage","pattern":"topic:*","channel":"topic:orders:123","data":"..."}
                channel = msg.get("channel")
                data = msg.get("data")

                print(">> Redis Listener received:", channel, data)

                if not channel or data is None:
                    continue

                # Map Redis channel -> topic key used by websocket subscriptions
                # Here we just use the Redis channel string as the topic.
                topic = str(channel)

                # If you publish JSON in Redis, you can pass-through.
                # If you publish plain text, still fine.
                await fanout_message_to_ws_subscribers(topic, data)
        except asyncio.CancelledError:
            print("Redis Pub/Sub listener task cancelled")
            pass

        except Exception:
            # Backoff before reconnecting
            await asyncio.sleep(1.0)
        finally:
            try:
                await pubsub.aclose()
            except Exception:
                pass
            try:
                await r.aclose()
            except Exception:
                pass