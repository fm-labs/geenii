from typing import List

from fastapi import APIRouter
from fastapi_websocket_pubsub import PubSubEndpoint

router = APIRouter(prefix="/ps", tags=["pubsub"])

endpoint = PubSubEndpoint()
endpoint.register_route(router, "/")

def get_pubsub_endpoint():
    """
    Get the PubSubEndpoint instance.
    This is used to access the endpoint in other parts of the application.
    """
    return endpoint

def publish_event(topics: List[str] | str, payload: dict):
    """
    Publish an event to the specified topics with the given payload.
    This is a utility function to publish events from anywhere in the application.
    """
    if isinstance(topics, str):
        topics = [topics]
    return endpoint.publish(topics, payload)


# Register a regular HTTP route to trigger debug events
@router.post("/publish/{topic}")
async def trigger_events(topic: str, payload: dict):
    await endpoint.publish(["debug", topic], payload)
    print(f"Published event to topic '{topic}': {payload}")
    return {"status": "success", "topic": topic, "payload": payload}
