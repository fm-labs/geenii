import abc
import json
import uuid
from typing import Any, Optional, List

import pydantic
from pymongo import MongoClient
from redis import Redis

# from bson import ObjectId
# from pydantic import Field, ConfigDict
# from pydantic_core import core_schema

from geenii.db.mongodb import get_mongo_collection, get_mongo_client
from geenii.settings import MONGODB_DB_NAME


class ModelStore(abc.ABC):

    def __init__(self, model_class=pydantic.BaseModel, key_field: str = 'uuid'):
        self.key_field = key_field
        self.model_class = model_class

    @abc.abstractmethod
    def create(self, model: pydantic.BaseModel) -> pydantic.BaseModel:
        pass

    @abc.abstractmethod
    def read(self, key: str) -> pydantic.BaseModel | None:
        pass

    @abc.abstractmethod
    def update(self, key: str, model: pydantic.BaseModel) -> None:
        pass

    @abc.abstractmethod
    def delete(self, key: str) -> bool:
        pass

    @abc.abstractmethod
    def find(self, query: Optional[dict] = None) -> List[pydantic.BaseModel]:
        pass

    def _get_model_key(self, model: pydantic.BaseModel) -> str | None:
        if hasattr(model, self.key_field):
            value = getattr(model, self.key_field)
            if value is None:
                return None
            return str(value)
        else:
            raise ValueError(f"Model does not have '{self.key_field}' attribute.")

    @staticmethod
    def model_to_dict(model: pydantic.BaseModel) -> dict:
        return model.model_dump(exclude_none=True, by_alias=True)

    @staticmethod
    def model_to_json(model: pydantic.BaseModel) -> str:
        return model.model_dump_json(exclude_none=True, by_alias=True)

    @staticmethod
    def dict_to_model(model_class: Any, data: dict) -> pydantic.BaseModel:
        return model_class.model_validate(data)

    @staticmethod
    def build_model_key() -> str:
        return str(uuid.uuid4().hex)


class InMemoryModelStore(ModelStore):
    def __init__(self, model_class=pydantic.BaseModel, key_field: str = 'uuid'):
        super().__init__(model_class=model_class, key_field=key_field)
        self.store = {}

    def create(self, model: pydantic.BaseModel) -> pydantic.BaseModel:
        key = self._get_model_key(model)
        if not key:
            key = ModelStore.build_model_key()
            model = model.model_copy(update={self.key_field: key})

        self.store[key] = model
        return model

    def update(self, key: str, model: pydantic.BaseModel) -> None:
        self.store[key] = model

    def read(self, key):
        return self.store.get(key)

    def delete(self, key: str) -> bool:
        if key in self.store:
            del self.store[key]
        return True

    def find(self, query: Optional[dict] = None) -> List[pydantic.BaseModel]:
        raise NotImplementedError("Find method is not implemented for InMemoryModelStore.")



class SerializedInMemoryModelStore(ModelStore):
    def __init__(self, model_class=pydantic.BaseModel, key_field: str = 'uuid'):
        super().__init__(model_class=model_class, key_field=key_field)
        self.store = {}

    def create(self, model: pydantic.BaseModel) -> pydantic.BaseModel:
        key = self._get_model_key(model)
        if not key:
            key = ModelStore.build_model_key()
            model = model.model_copy(update={self.key_field: key})

        model_dict = ModelStore.model_to_dict(model)
        self.store[key] = model_dict
        return model

    def update(self, key: str, model: pydantic.BaseModel) -> None:
        model_dict = ModelStore.model_to_dict(model)
        self.store[key] = model_dict

    def read(self, key) -> pydantic.BaseModel | None:
        doc = self.store.get(key)
        return ModelStore.dict_to_model(model_class=self.model_class, data=doc) if doc else None

    def delete(self, key: str) -> bool:
        if key in self.store:
            del self.store[key]
        return True

    def find(self, query: Optional[dict] = None) -> List[pydantic.BaseModel]:
        raise NotImplementedError("Find method is not implemented for SerializedInMemoryModelStore.")


class RedisModelStore(ModelStore):
    def __init__(self, redis: Redis, collection_name="", model_class=pydantic.BaseModel, key_field: str = 'uuid'):
        super().__init__(model_class=model_class, key_field=key_field)
        self.redis = redis
        self.collection_name = collection_name

    def _build_redis_key(self, key) -> str:
        if self.collection_name:
            return f"{self.collection_name}:{key}"
        return key

    def create(self, model: pydantic.BaseModel) -> pydantic.BaseModel:
        key = self._get_model_key(model)
        if not key:
            key = ModelStore.build_model_key()
            model = model.model_copy(update={self.key_field: key})

        model_json_str = ModelStore.model_to_json(model)
        self.redis.set(self._build_redis_key(key), model_json_str)
        return model

    def update(self, key: str, model: pydantic.BaseModel) -> None:
        model_json_str = ModelStore.model_to_json(model)
        self.redis.set(self._build_redis_key(key), model_json_str)

    def read(self, key: str) -> pydantic.BaseModel | None:
        json_str = self.redis.get(self._build_redis_key(key))
        doc = json.loads(json_str) if json_str else None
        #if doc is None:
        #    raise KeyError(f"Key '{self._build_redis_key(key)}' not found in RedisModelStore.")
        return ModelStore.dict_to_model(model_class=self.model_class, data=doc) if doc else None

    def delete(self, key: str) -> bool:
        self.redis.delete(self._build_redis_key(key))
        return True

    def find(self, query: Optional[dict] = None) -> List[pydantic.BaseModel]:
        raise NotImplementedError("Find method is not implemented for RedisModelStore.")



class MongoDbModelStore(ModelStore):

    def __init__(self, mongo: MongoClient, collection_name: str, model_class=pydantic.BaseModel, key_field: str = 'uuid'):
        super().__init__(model_class=model_class, key_field=key_field)
        self.collection_name = collection_name
        self.collection = get_mongo_collection(mongo, MONGODB_DB_NAME, collection_name)

    def create(self, model: pydantic.BaseModel) -> pydantic.BaseModel:
        key = self._get_model_key(model)
        if not key:
            key = ModelStore.build_model_key()
            model = model.model_copy(update={self.key_field: key})

        model_dict = ModelStore.model_to_dict(model)
        self.collection.insert_one(model_dict)
        return model

    def update(self, key: str, model: pydantic.BaseModel) -> None:
        key = self._get_model_key(model)
        if not key:
            raise ValueError("Model must have a key to update.")

        model_dict = ModelStore.model_to_dict(model)
        self.collection.update_one({self.key_field: key}, {'$set': model_dict}, upsert=True)

    def read(self, key: str) -> pydantic.BaseModel | None:
        doc = self.collection.find_one({self.key_field: key})
        return ModelStore.dict_to_model(model_class=self.model_class, data=doc) if doc else None

    def delete(self, key: str) -> None:
        result = self.collection.delete_one({self.key_field: key})
        return result.deleted_count > 0

    def find(self, query: Optional[dict] = None) -> List[pydantic.BaseModel]:
        if query is None:
            query = {}
        records = list(self.collection.find(query))
        mapped = []
        for record in records:
            record = ModelStore.dict_to_model(model_class=self.model_class, data=record)
            mapped.append(record)
        return mapped


def build_model_store(model_class, collection_name) -> ModelStore:
    mongo_client = get_mongo_client()
    return MongoDbModelStore(mongo=mongo_client, collection_name=collection_name, model_class=model_class)


# class PyObjectId(ObjectId):
#     """Pydantic-friendly ObjectId type."""
#
#     @classmethod
#     def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> core_schema.CoreSchema:
#         # Accept either an ObjectId or a valid ObjectId string
#         return core_schema.union_schema(
#             [
#                 core_schema.is_instance_schema(ObjectId),
#                 core_schema.no_info_plain_validator_function(cls.validate),
#             ]
#         )
#
#     @classmethod
#     def validate(cls, v: Any) -> ObjectId:
#         if isinstance(v, ObjectId):
#             return v
#         if isinstance(v, str) and ObjectId.is_valid(v):
#             return ObjectId(v)
#         raise ValueError("Invalid ObjectId")
#
#
# class MongoBaseModel(pydantic.BaseModel):
#     model_config = ConfigDict(
#         populate_by_name=True,  # allow using "id" OR "_id"
#         arbitrary_types_allowed=True,  # allow ObjectId type
#         json_encoders={ObjectId: str},  # when exporting JSON, stringify ObjectId
#     )
#     id: Optional[PyObjectId] = Field(default=None, alias="_id")
