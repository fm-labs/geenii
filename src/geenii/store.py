import abc

class DataStore(abc.ABC):

    @abc.abstractmethod
    def set(self, key, value):
        pass

    @abc.abstractmethod
    def get(self, key, default=None):
        pass

    @abc.abstractmethod
    def delete(self, key):
        pass


class InMemoryDataStore(DataStore):
    def __init__(self):
        self.store = {}

    def set(self, key, value):
        self.store[key] = value

    def get(self, key, default=None):
        return self.store.get(key, default)

    def delete(self, key):
        if key in self.store:
            del self.store[key]


class RedisDataStore(DataStore):
    def __init__(self, redis_client):
        self.redis = redis_client

    def set(self, key, value):
        self.redis.hset(key, value)

    def get(self, key, default=None):
        value = self.redis.hget(key)
        return value if value is not None else default

    def delete(self, key):
        self.redis.delete(key)


class MongoDbDataStore(DataStore):
    def __init__(self, mongo_collection):
        self.collection = mongo_collection

    def set(self, key, value):
        self.collection.update_one({'_id': key}, {'$set': value}, upsert=True)

    def get(self, key, default=None):
        doc = self.collection.find_one({'_id': key})
        return doc if doc is not None else default

    def delete(self, key):
        self.collection.delete_one({'_id': key})