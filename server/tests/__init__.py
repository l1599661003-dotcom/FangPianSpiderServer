import sys
import types
from contextlib import asynccontextmanager


def _install_fake_aiomysql():
    if "aiomysql" in sys.modules:
        return

    module = types.ModuleType("aiomysql")

    class FakePool:
        async def acquire(self):
            return object()

        def release(self, conn):
            return None

        def close(self):
            return None

        async def wait_closed(self):
            return None

    async def create_pool(*args, **kwargs):
        return FakePool()

    module.Pool = FakePool
    module.Connection = object
    module.create_pool = create_pool
    sys.modules["aiomysql"] = module


def _install_fake_motor():
    if "motor" in sys.modules and "motor.motor_asyncio" in sys.modules:
        return

    motor_module = types.ModuleType("motor")
    motor_asyncio_module = types.ModuleType("motor.motor_asyncio")
    motor_module.__path__ = []
    motor_module.__package__ = "motor"
    motor_asyncio_module.__package__ = "motor"

    class FakeAsyncIOMotorClient:
        def __init__(self, *args, **kwargs):
            self._databases = {}

        def __getitem__(self, key):
            if key not in self._databases:
                self._databases[key] = {}
            return self._databases[key]

        def close(self):
            return None

    motor_asyncio_module.AsyncIOMotorClient = FakeAsyncIOMotorClient
    motor_module.motor_asyncio = motor_asyncio_module
    sys.modules["motor"] = motor_module
    sys.modules["motor.motor_asyncio"] = motor_asyncio_module


def _install_fake_db_modules():
    if "server.app.db.database" not in sys.modules:
        database_module = types.ModuleType("server.app.db.database")

        class FakeBase:
            pass

        async def get_db():
            if False:
                yield None

        async def get_mongodb_collection(collection_name):
            if False:
                yield None

        async def get_mongodb_database():
            return None

        async def init_db():
            return None

        async def close_db():
            return None

        database_module.Base = FakeBase
        database_module.engine = None
        database_module.async_session = None
        database_module.get_db = get_db
        database_module.get_mongodb_collection = get_mongodb_collection
        database_module.get_mongodb_database = get_mongodb_database
        database_module.init_db = init_db
        database_module.close_db = close_db
        sys.modules["server.app.db.database"] = database_module

    if "server.app.db.context" not in sys.modules:
        context_module = types.ModuleType("server.app.db.context")

        class DatabaseManager:
            _mysql_pool = None
            _mongodb_pool = None

            @classmethod
            async def initialize(cls):
                return None

            @classmethod
            async def close(cls):
                return None

        @asynccontextmanager
        async def get_mysql_conn():
            yield None

        @asynccontextmanager
        async def get_mongodb_collection(collection_name):
            yield None

        context_module.DatabaseManager = DatabaseManager
        context_module.get_mysql_conn = get_mysql_conn
        context_module.get_mongodb_collection = get_mongodb_collection
        sys.modules["server.app.db.context"] = context_module


_install_fake_aiomysql()
_install_fake_motor()
_install_fake_db_modules()
