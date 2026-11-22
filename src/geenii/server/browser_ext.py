import json

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/browser")

@router.get("/")
def browser_ext_info():
    return { "version": "0.1.0" }


@router.post("/")
async def browser_ext_request(request: Request):
    """Process a post request from the browser extension."""
    body = await request.body()
    try:
        payload = json.loads(body) if body else None
    except json.JSONDecodeError:
        payload = body.decode(errors="replace")
    print(f"[browser_ext] received POST: {payload}")
    return {"status": "ok"}


@router.websocket("/ws")
async def browser_ext_socket(websocket: WebSocket):
    """Websocket connection with browser extension"""
    await websocket.accept()
    client = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
    print(f"[browser_ext] websocket connected: {client}")

    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break

            if message.get("text") is not None:
                print(f"[browser_ext] received text from {client}: {message['text']}")
            elif message.get("bytes") is not None:
                print(f"[browser_ext] received {len(message['bytes'])} bytes from {client}")
    except WebSocketDisconnect:
        pass
    finally:
        print(f"[browser_ext] websocket disconnected: {client}")
