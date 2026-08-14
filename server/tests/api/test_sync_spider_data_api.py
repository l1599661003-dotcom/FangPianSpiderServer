import unittest
from unittest import mock

from fastapi import HTTPException

from server.app.api.v1 import sync_spider_data_api


class DummyRequest:
    def __init__(self, headers):
        self.headers = headers


class SyncSpiderDataApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_require_plugin_instance_accepts_valid_headers(self):
        client = {"id": 7, "status": 1, "admin_id": 3, "computer_id": 8}
        request = DummyRequest({
            "X-Plugin-Device-Id": "device-123",
            "X-Plugin-Client-Token": "token-abc",
        })

        with mock.patch.object(
            sync_spider_data_api.plugin_remote_service,
            "authenticate",
            new=mock.AsyncMock(return_value=client),
        ) as mocked:
            result = await sync_spider_data_api.require_plugin_instance(request)

        self.assertEqual(result, client)
        mocked.assert_awaited_once_with("device-123", "token-abc")

    async def test_require_plugin_instance_rejects_disabled_client(self):
        client = {"id": 7, "status": 0, "admin_id": 3, "computer_id": 8}
        request = DummyRequest({
            "X-Plugin-Device-Id": "device-123",
            "X-Plugin-Client-Token": "token-abc",
        })

        with mock.patch.object(
            sync_spider_data_api.plugin_remote_service,
            "authenticate",
            new=mock.AsyncMock(return_value=client),
        ):
            with self.assertRaises(HTTPException) as ctx:
                await sync_spider_data_api.require_plugin_instance(request)

        self.assertEqual(ctx.exception.status_code, 403)

    async def test_require_plugin_instance_rejects_missing_headers(self):
        with self.assertRaises(HTTPException) as ctx:
            await sync_spider_data_api.require_plugin_instance(DummyRequest({}))

        self.assertEqual(ctx.exception.status_code, 401)

    async def test_require_plugin_instance_rejects_invalid_token(self):
        request = DummyRequest({
            "X-Plugin-Device-Id": "device-123",
            "X-Plugin-Client-Token": "bad-token",
        })

        with mock.patch.object(
            sync_spider_data_api.plugin_remote_service,
            "authenticate",
            new=mock.AsyncMock(return_value=None),
        ):
            with self.assertRaises(HTTPException) as ctx:
                await sync_spider_data_api.require_plugin_instance(request)

        self.assertEqual(ctx.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
