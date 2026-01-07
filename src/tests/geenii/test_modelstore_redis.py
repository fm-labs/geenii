import pytest
import redis
from testcontainers.redis import RedisContainer

from geenii.db.redis import get_redis_client
from geenii.modelstore import RedisModelStore, ModelStore
from tests.geenii.test_modelstore import TestModelStore, MyModel


@pytest.fixture(scope="session")
def redis_container():
    # Pin an image tag for reproducibility
    with RedisContainer("redis:8") as c:
        yield c


@pytest.fixture(scope="session")
def redis_url(redis_container) -> str:
    # testcontainers exposes host/port; Redis URL format is:
    # redis://<host>:<port>/0
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    return f"redis://{host}:{port}/0"


@pytest.fixture(scope="function")
def redis_client(redis_url):
    client = get_redis_client(redis_url)
    yield client
    client.flushdb()  # Clean up after test


class TestRedisModelStore(TestModelStore):

    @pytest.fixture(autouse=True)
    def _setup(self, redis_client):
        self.redis = redis_client

    def get_store(self) -> ModelStore:
        return RedisModelStore(model_class=MyModel, key_field="id", redis=self.redis, collection_name="test")
