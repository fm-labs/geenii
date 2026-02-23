import asyncio
import hashlib
import json
import logging
import sqlite3

from fastapi import APIRouter, HTTPException, Query
from fastapi.params import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sse_starlette import EventSourceResponse
from starlette.requests import HTTPConnection, Request
from starlette.websockets import WebSocket, WebSocketDisconnect

from geenii.chat.chat_manager import ChatManager
from geenii.chat.chat_models import Room, RoomCreate, Member, JoinRoom, LeaveRoom, InviteUser, Message, MessageCreate, \
    SystemMessage, ChatMessage
from geenii.chat.chat_server_core import SseConnection, WebSocketConnection, MessageHandler, ConnectionManager

logger = logging.getLogger(__name__)

async def dep_chat_mgr(request: HTTPConnection) -> "ChatManager":
    """Get the ChatManager instance from the app state."""
    return request.app.state.chat_server.chat_manager

async def dep_conn_mgr(request: HTTPConnection) -> "ConnectionManager":
    """Get the ConnectionManager instance from the app state."""
    return request.app.state.chat_server.conn_manager

async def dep_msg_handler(request: HTTPConnection) -> "MessageHandler":
    """Get the main message handler function from the app state."""
    return request.app.state.chat_server.message_handler



router = APIRouter(prefix="/chat", tags=["chat"])


def _dummy_token(username: str) -> str:
    """Hash a username into a dummy bearer token (must match chat_client.make_token)."""
    return hashlib.sha256(username.encode()).hexdigest()

# Pre-built registry: token -> username.  Add entries for every dummy user you need.
DUMMY_USERS = ["alice", "bob", "charlie", "dummy_user", "admin"]
TOKEN_REGISTRY: dict[str, str] = {_dummy_token(u): u for u in DUMMY_USERS}


# ---------- Security dependency ----------

class User(BaseModel):
    username: str
    is_active: bool = True


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> User:
    """Resolve bearer token to a User via the dummy token registry."""
    #token = credentials.credentials
    #username = TOKEN_REGISTRY.get(token)
    #print(f"Authenticating token={token}, resolved username={username}")
    #if username is None:
    #    raise HTTPException(status_code=401, detail="Invalid or unknown bearer token")
    #return User(username=username)
    return User(username="dummy_user")  # TODO replace with real auth


# ---------- REST: Rooms ----------
@router.post("", response_model=Room, status_code=201)
def create_room_endpoint(body: RoomCreate, 
                         current_user: User = Depends(get_current_user),
                         chat_mgr:ChatManager=Depends(dep_chat_mgr)):
    try:
        return chat_mgr.create_room(
            body.name,
            owner=current_user.username,
            is_public=body.is_public,
            password=body.password,
            room_type=body.room_type,
            dm_peer=body.dm_peer,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Room name already exists")


@router.get("", response_model=list[Room])
def list_rooms_endpoint(current_user: User = Depends(get_current_user), chat_mgr:ChatManager=Depends(dep_chat_mgr)):
    return chat_mgr.list_rooms()


@router.get("/stats", status_code=200)
def stats_endpoint(chat_mgr:ChatManager=Depends(dep_chat_mgr), conns:ConnectionManager=Depends(dep_conn_mgr)):
    return {
        "active_rooms": len(conns.rooms),
        "active_connections": sum(len(conns.rooms[room_id]) for room_id in conns.rooms),
        # "active_bot_connections": sum(
        #     sum(1 for c in conns.rooms[room_id] if isinstance(c, BotConnection)) for room_id in conns.rooms),
        # "active_websocket_connections": sum(
        #     sum(1 for c in conns.rooms[room_id] if isinstance(c, WebSocketConnection)) for room_id in conns.rooms),
        # "active_sse_connections": sum(
        #     sum(1 for c in conns.rooms[room_id] if isinstance(c, SseConnection)) for room_id in conns.rooms),
    }


@router.get("/rooms/{room_id}")
def get_room_endpoint(room_id: str,
                      current_user: User = Depends(get_current_user), 
                      chat_mgr:ChatManager=Depends(dep_chat_mgr)):
    room = chat_mgr.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    members = chat_mgr.get_members(room_id)
    return {"room": room, "members": members}


# ---------- REST: Participants ----------
@router.post("/rooms/{room_id}/join", response_model=Member, status_code=201)
def join_room_endpoint(room_id: str, 
                       body: JoinRoom,
                       current_user: User = Depends(get_current_user),
                       chat_mgr:ChatManager=Depends(dep_chat_mgr)):
    if not chat_mgr.get_room(room_id):
        raise HTTPException(status_code=404, detail="Room not found")

    pw_hash = chat_mgr.get_room_password_hash(room_id)
    if pw_hash:
        if not body.password:
            raise HTTPException(status_code=403, detail="Password required")
        if not chat_mgr.verify_password(body.password, pw_hash):
            raise HTTPException(status_code=403, detail="Invalid password")

    try:
        return chat_mgr.join_room(room_id, body.username, member_type=body.member_type)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="User already joined")


@router.post("/rooms/{room_id}/leave", response_model=Member)
def leave_room_endpoint(room_id: str, body: LeaveRoom, current_user: User = Depends(get_current_user),
                        chat_mgr:ChatManager=Depends(dep_chat_mgr)):
    if not chat_mgr.get_room(room_id):
        raise HTTPException(status_code=404, detail="Room not found")
    member = chat_mgr.leave_room(room_id, body.username)
    if not member:
        raise HTTPException(status_code=404, detail="User is not an active member")
    return member


@router.post("/rooms/{room_id}/invite", response_model=Member, status_code=201)
def invite_user_endpoint(room_id: str, body: InviteUser, current_user: User = Depends(get_current_user),
                         chat_mgr:ChatManager=Depends(dep_chat_mgr)):
    if not chat_mgr.get_room(room_id):
        raise HTTPException(status_code=404, detail="Room not found")
    if chat_mgr.get_room_owner(room_id) != current_user.username:
        raise HTTPException(status_code=403, detail="Only the room owner can invite members")
    try:
        return chat_mgr.invite_user(room_id, body.username, member_type=body.member_type)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="User already exists in room")


# ---------- REST: Messages ----------

@router.post("/rooms/{room_id}/messages", response_model=Message, status_code=201)
def send_message_endpoint(room_id: str, body: MessageCreate, current_user: User = Depends(get_current_user),
                          chat_mgr:ChatManager=Depends(dep_chat_mgr)):
    if not chat_mgr.get_room(room_id):
        raise HTTPException(status_code=404, detail="Room not found")
    if not chat_mgr.is_member(room_id, current_user.username):
        raise HTTPException(status_code=403, detail="Not a member of this room")
    logger.info("REST message in room=%s from user=%s", room_id, current_user.username)
    return chat_mgr.add_message(room_id, current_user.username, body.content)


@router.get("/rooms/{room_id}/messages", response_model=list[Message])
def poll_messages_endpoint(room_id: str, current_user: User = Depends(get_current_user),
                           after: int | None = Query(default=None), chat_mgr:ChatManager=Depends(dep_chat_mgr)):
    if not chat_mgr.get_room(room_id):
        raise HTTPException(status_code=404, detail="Room not found")
    return chat_mgr.get_messages(room_id, after=after)


# ---------- SSE: Message Stream ----------

@router.get("/rooms/{room_id}/stream")
async def stream_messages_endpoint(room_id: str,
                                   request: Request,
                                   current_user: User = Depends(get_current_user),
                                   conns: ConnectionManager=Depends(dep_conn_mgr),
                                   chat_mgr: ChatManager=Depends(dep_chat_mgr)):

    if not chat_mgr.get_room(room_id):
        raise HTTPException(status_code=404, detail="Room not found")
    if not chat_mgr.is_member(room_id, current_user.username):
        raise HTTPException(status_code=403, detail="Not a member of this room")

    sse_conn = SseConnection(current_user.username)
    conns.add(room_id, sse_conn)
    logger.info("SSE connect room=%s user=%s", room_id, current_user.username)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(sse_conn.queue.get(), timeout=30.0)
                    if message is None:
                        # Sentinel value to indicate connection should be closed
                        break

                    yield {
                        "event": message.get("type", "message"),
                        "data": json.dumps(message),
                    }
                except asyncio.TimeoutError:
                    # Send keep-alive comment to prevent connection timeout
                    yield {"comment": "keep-alive"}
        finally:
            logger.info("SSE disconnect room=%s user=%s", room_id, current_user.username)
            conns.remove(room_id, sse_conn)

    return EventSourceResponse(event_generator())


# ---------- WebSocket endpoint ----------


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket,
                             room_id: str = Query(...),
                             username: str = Query(...), # todo get from token instead of query param
                             token: str | None = Query(...), # todo validate token and extract username
                             conns:ConnectionManager=Depends(dep_conn_mgr),
                             chat_mgr:ChatManager=Depends(dep_chat_mgr),
                             msg_handler:MessageHandler=Depends(dep_msg_handler)):

    logger.info("WebSocket connected to room=%s user=%s", room_id, username)

    # validate parameters
    if not room_id or not username:
        await websocket.close(code=4001, reason="Missing room_id or username")
        return


    # validate room exists, or auto-create DM room if not found
    if not chat_mgr.get_room(room_id):
        _default_bot_id = "geenii:bot:default"
        _dm_room = chat_mgr.get_dm_room(owner=username, peer=_default_bot_id, auto_create=True, auto_join=True)
        if _dm_room is None:
            logger.info("DM room for user %s and bot %s does not exist", username, _default_bot_id)
            await websocket.close(code=4004, reason="Room not found")
            return

        if _dm_room.id != room_id:
            logger.error("Generated DM room ID %s does not match expected room ID %s. This is fatal.", _dm_room.id,
                         room_id)
            await websocket.close(code=5001, reason="Internal server error")
            return

    # Auto-join if not already a member
    # if not cm.is_member(room_id, username):
    #     try:
    #         cm.join_room(room_id, username)
    #     except Exception:
    #         logger.exception("Error joining room")
    #         raise HTTPException(status_code=500, detail="Error joining room")

    if not chat_mgr.is_member(room_id, username):
        # not allowed
        logger.warning("WS connection attempt for room %s by non-member %s, rejecting", room_id, username)
        await websocket.close(code=4003, reason="You are not a member of this room")
        return

    # connect to the WebSocket and add to connection manager
    await websocket.accept()
    logger.info("WS connect room=%s user=%s", room_id, username)
    ws_conn = WebSocketConnection(username, websocket)
    conns.add(room_id, ws_conn)

    # notify room of join/leave via system messages
    await msg_handler.outbound.put(SystemMessage(room_id=room_id, content=f"{username} joined the room!"))
    #await msg_handler.outbound.put(ChatMessage(room_id=room_id, sender_id="system", content=[TextContent(text="Welcome back!")]))

    try:
        while True:
            data = await websocket.receive_json()
            logger.info("WS message in room=%s from user=%s data=%s", room_id, username, json.dumps(data))

            content = data.get("content", [])
            if not content:
                logger.info("Skipping empty message from user=%s in room=%s", username, room_id)
                continue

            try:
                if not msg_handler or not msg_handler.inbound or msg_handler.inbound.full():
                    logger.warning("Message handler inbound queue is not available or full, skipping message from user=%s in room=%s", username, room_id)
                    continue

                msg = ChatMessage(room_id=room_id, sender_id=username, content=content)
                await msg_handler.inbound.put(msg)
            except Exception:
                logger.warning("WS: Invalid message content from user=%s, skipping: %s", username, content)
                continue
    except WebSocketDisconnect:
        pass
    finally:
        logger.info("WS disconnect room=%s user=%s", room_id, username)
        conns.remove(room_id, ws_conn)
        await msg_handler.outbound.put(SystemMessage(room_id=room_id, content=f"{username} left the room!"))
