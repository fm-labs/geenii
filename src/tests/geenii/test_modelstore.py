import abc
import uuid

import pytest
import pydantic

from geenii.modelstore import InMemoryModelStore, SerializedInMemoryModelStore, ModelStore


class MyModel(pydantic.BaseModel):
    id: str | None = None
    name: str


class TestModelStore(abc.ABC):

    @abc.abstractmethod
    def get_store(self) -> ModelStore:
        pass

    def test_create_uses_existing_uuid_key(self):
        store = self.get_store()
        key = uuid.uuid4().hex  # uuid string key

        m = MyModel(id=key, name="Alice")
        created = store.create(m)

        assert created is m
        assert created.id == key
        assert store.read(key) is not None
        assert store.read(key).model_dump() == m.model_dump()

    def test_create_generates_uuid_key_when_missing(self):
        store = self.get_store()
        m = MyModel(id=None, name="Bob")

        created = store.create(m)

        #assert created is m
        assert created.id is not None
        # keys are uuid strings (hex)
        assert isinstance(created.id, str)
        assert len(created.id) == 32
        # validate it's hex
        int(created.id, 16)

        assert store.read(created.id).model_dump() == created.model_dump()

    def test_read_returns_none_when_key_missing(self):
        store = self.get_store()
        assert store.read(uuid.uuid4().hex) is None

    def test_update_overwrites_value_for_key(self):
        store = self.get_store()
        key = uuid.uuid4().hex

        m1 = MyModel(id=key, name="Old")
        store.create(m1)

        m2 = MyModel(id=key, name="New")
        store.update(key, m2)

        assert store.read(key).name == "New"
        assert store.read(key).model_dump() == m2.model_dump()

    def test_delete_removes_key_and_is_idempotent(self):
        store = self.get_store()
        key = uuid.uuid4().hex

        m = MyModel(id=key, name="X")
        store.create(m)

        store.delete(key)
        assert store.read(key) is None

        # should not raise if called again
        store.delete(key)

    def test_get_model_key_raises_when_key_field_missing(self):
        class NoIdModel(pydantic.BaseModel):
            name: str

        store = InMemoryModelStore(model_class=NoIdModel, key_field="id")
        m = NoIdModel(name="NoId")

        with pytest.raises(ValueError, match=r"Model does not have 'id' attribute"):
            store._get_model_key(m)

    def test_model_to_dict_excludes_none_and_uses_alias(self):
        class AliasModel(pydantic.BaseModel):
            id: str | None = None
            name: str
            some_field: str | None = pydantic.Field(default=None, alias="someField")

        m = AliasModel(id=None, name="A", someField=None)
        d = ModelStore.model_to_dict(m)

        assert d == {"name": "A"}  # excludes None, uses alias (if present)

        m2 = AliasModel(id="abc", name="B", someField="x")
        d2 = ModelStore.model_to_dict(m2)
        assert d2 == {"id": "abc", "name": "B", "someField": "x"}

    def test_dict_to_model_validates(self):
        data = {"id": uuid.uuid4().hex, "name": "C"}
        m = ModelStore.dict_to_model(MyModel, data)

        assert isinstance(m, MyModel)
        assert m.id == data["id"]
        assert m.name == "C"

    def test_build_model_key_returns_uuid_hex_string(self):
        k = ModelStore.build_model_key()
        assert isinstance(k, str)
        assert len(k) == 32
        int(k, 16)  # should be valid hex



class TestInMemoryModelStore(TestModelStore):

    def get_store(self) -> ModelStore:
        return InMemoryModelStore(model_class=MyModel, key_field="id")


class TestSerializedInMemoryModelStore(TestModelStore):

    def get_store(self) -> ModelStore:
        return SerializedInMemoryModelStore(model_class=MyModel, key_field="id")


