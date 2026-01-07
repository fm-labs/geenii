import os
import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.mongodb import MongoDbContainer

from geenii.modelstore import ModelStore, MongoDbModelStore
from tests.geenii.test_modelstore import TestModelStore, MyModel


def create_mongodb_testcontainer():
    container = DockerContainer("mongo:8")
    container.with_exposed_ports(27017)
    return container


mongo_container = create_mongodb_testcontainer()

@pytest.fixture(scope="session")
def mongo_db():
    # Choose a MongoDB image tag you want to pin for reproducibility
    with MongoDbContainer("mongo:8") as mongo:
        # testcontainers gives you a ready-to-use connection URL
        yield mongo


@pytest.fixture(scope="session")
def mongo_client(mongo_db):
    from pymongo import MongoClient
    client = MongoClient(mongo_db.get_connection_url())
    yield client
    client.close()

# @pytest.fixture(scope="module", autouse=True)
# def setup(request):
#     mongo_container.start()
#     delay = wait_for_logs(mongo_container, "Waiting for connections", timeout=10)
#
#     def remove_container():
#         mongo_container.stop()
#
#     request.addfinalizer(remove_container)
#     os.environ["MONGODB_URI"] = f"mongodb://localhost:{mongo_container.get_exposed_port(27017)}"
#
#
# @pytest.fixture(scope="function", autouse=True)
# def setup_data():
#     pass



def test_mongodb_client(mongo_client):
    # from geenii.db.mongodb import get_mongo_client
    # os.environ["MONGODB_URI"] = mongo_db.get_connection_url()
    # print(">>>> TESTING WITH MONGODB_URI", os.environ["MONGODB_URI"])
    # client = get_mongo_client(uri=mongo_db.get_connection_url(), ping=True)
    db_names = mongo_client.list_database_names()
    assert "admin" in db_names
    assert "local" in db_names



class TestMongoDbModelStore(TestModelStore):

    @pytest.fixture(autouse=True)
    def _setup(self, mongo_client):
        self.mongo = mongo_client

    def get_store(self) -> ModelStore:
        return MongoDbModelStore(model_class=MyModel, key_field="id", collection_name="test", mongo=self.mongo)