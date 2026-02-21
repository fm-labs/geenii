import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from geenii.chat.chat_server_ctx import ChatServerState
from geenii.chat.chat_server_routes import router

logger = logging.getLogger("chat_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    chat_server_state = ChatServerState(app)
    await chat_server_state.startup()
    app.state.chat_server_state = chat_server_state

    yield  # app is running

    await chat_server_state.stop()

app = FastAPI(title="Chat Server", lifespan=lifespan)
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    uvicorn.run(app, host="0.0.0.0", port=3333, log_level="info")
