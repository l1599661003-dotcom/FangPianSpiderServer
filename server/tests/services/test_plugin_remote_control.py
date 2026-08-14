import asyncio
import hashlib
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import httpx

from server.app.services.PluginRemoteControlService import PluginRemoteControlService


class FakeClientDao:
    def __init__(self):
        self.inserted = None
        self.rows_by_id = {}

    async def fetch_one(self, query, params=None):
        params = params or {}
        if "WHERE device_id = :device_id" in query:
            return None
        if "WHERE id = :id" in query:
            return self.rows_by_id.get(params.get("id"))
        return None

    async def fetch_all(self, query, params=None):
        return []

    async def insert(self, row):
        self.inserted = dict(row)
        row_id = 99
        self.rows_by_id[row_id] = {**row, "id": row_id}
        return row_id


class FakeUpgradeManager:
    def is_connected(self, client_id):
        return True

    async def send(self, client_id, message):
        return True


class PluginRemoteControlServiceTests(unittest.TestCase):
    def _service(self):
        return object.__new__(PluginRemoteControlService)

    def test_registration_response_marks_enabled_only_when_bound(self):
        service = self._service()

        enabled = service._registration_response(
            {
                "id": 1,
                "status": 1,
                "admin_id": 12,
                "computer_id": 34,
                "plugin_instance_name": "Instance A",
                "client_name": "Instance A",
            },
            "token",
            True,
        )
        disabled = service._registration_response(
            {
                "id": 2,
                "status": 0,
                "admin_id": 12,
                "computer_id": 34,
                "plugin_instance_name": "Instance B",
                "client_name": "Instance B",
            },
            "token",
            False,
        )

        self.assertTrue(enabled["enabled"])
        self.assertFalse(disabled["enabled"])

        zero_role = service._registration_response(
            {
                "id": 3,
                "status": 1,
                "admin_id": "0",
                "computer_id": 34,
                "plugin_instance_name": "Instance C",
                "client_name": "Instance C",
            },
            "token",
            False,
        )
        self.assertFalse(zero_role["enabled"])

    def test_register_keeps_unbound_admin_id_empty(self):
        service = self._service()
        client_dao = FakeClientDao()
        service.client_dao = client_dao

        result = asyncio.run(
            service.register(
                {
                    "device_id": "device-123456",
                    "browser_type": "Chrome",
                    "browser_version": "1",
                    "extension_version": "0.0.43",
                },
                "127.0.0.1",
            )
        )

        self.assertTrue(result["created"])
        self.assertIsNone(client_dao.inserted["admin_id"])

    def test_build_upgrade_notice_includes_normalized_sha256(self):
        service = self._service()
        client = {"extension_version": "0.0.41"}

        with mock.patch.object(
            PluginRemoteControlService,
            "load_upgrade_config",
            return_value={
                "enabled": True,
                "latest_version": "0.0.42",
                "title": "test",
                "changelog": ["a"],
                "package_url": "https://example.com/tianxuan.zip",
                "package_name": "tianxuan.zip",
                "package_sha256": "  ABCD" + "0" * 60 + "  ",
                "target_folder_name": "tianxuan",
                "silent_update": True,
                "changed_files": ["upgrade.js"],
                "force": False,
            },
        ):
            notice = service.build_upgrade_notice(client)

        self.assertIsNotNone(notice)
        self.assertEqual(notice["package_sha256"], "abcd" + "0" * 60)
        self.assertEqual(notice["latest_version"], "0.0.42")
        self.assertEqual(notice["package_name"], "tianxuan.zip")
        self.assertEqual(notice["target_folder_name"], "tianxuan")
        self.assertTrue(notice["silent_update"])
        self.assertEqual(
            notice["package_url"],
            f"https://example.com/tianxuan.zip?tianxuan_sha256={'abcd' + '0' * 60}",
        )

    def test_versioned_package_url_preserves_existing_query(self):
        url = PluginRemoteControlService._versioned_package_url(
            "https://example.com/tianxuan.zip?download=1&tianxuan_sha256=old",
            "ab" * 32,
        )

        self.assertEqual(
            url,
            f"https://example.com/tianxuan.zip?download=1&tianxuan_sha256={'ab' * 32}",
        )

    def test_load_upgrade_config_uses_explicit_path_and_normalizes_values(self):
        service = self._service()
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "plugin-upgrade.json"
            config_path.write_text(
                json.dumps(
                    {
                        "enabled": "true",
                        "latest_version": " 0.0.44 ",
                        "package_url": "https://example.com/tianxuan.zip",
                        "package_sha256": "AB" * 32,
                        "target_folder_name": "../invalid",
                        "silent_update": "true",
                        "changelog": [" first ", "", None],
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"PLUGIN_UPGRADE_CONFIG_PATH": str(config_path)}):
                config = service.load_upgrade_config()

        self.assertTrue(config["enabled"])
        self.assertEqual(config["latest_version"], "0.0.44")
        self.assertEqual(config["target_folder_name"], "tianxuan")
        self.assertEqual(config["changelog"], ["first"])
        self.assertEqual(config["package_sha256"], "ab" * 32)

    def test_silent_upgrade_requires_sha256(self):
        service = self._service()
        with mock.patch.object(
            PluginRemoteControlService,
            "load_upgrade_config",
            return_value={
                "enabled": True,
                "latest_version": "0.0.44",
                "package_url": "https://example.com/tianxuan.zip",
                "package_sha256": "",
                "target_folder_name": "tianxuan",
                "silent_update": True,
            },
        ):
            notice = service.build_upgrade_notice({"extension_version": "0.0.43"})

        self.assertIsNotNone(notice)
        self.assertFalse(notice["silent_update"])

    def test_read_package_version_accepts_single_wrapper_folder(self):
        package = io.BytesIO()
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("tianxuan/manifest.json", json.dumps({"version": "0.0.45"}))
            archive.writestr("tianxuan/background-entry.js", "")

        self.assertEqual(
            PluginRemoteControlService._read_package_version(package.getvalue()),
            "0.0.45",
        )

    def test_read_package_version_rejects_missing_manifest(self):
        package = io.BytesIO()
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("tianxuan/background-entry.js", "")

        with self.assertRaisesRegex(ValueError, "manifest.json"):
            PluginRemoteControlService._read_package_version(package.getvalue())

    def test_refresh_upgrade_package_metadata_downloads_and_persists_package(self):
        service = self._service()
        package = io.BytesIO()
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("tianxuan/manifest.json", json.dumps({"version": "0.0.46"}))
            archive.writestr("tianxuan/background-entry.js", "")
        package_bytes = package.getvalue()
        expected_sha256 = hashlib.sha256(package_bytes).hexdigest()
        original_async_client = httpx.AsyncClient

        def build_client(*args, **kwargs):
            def handle_request(request):
                self.assertTrue(request.url.params.get("tianxuan_refresh"))
                return httpx.Response(200, content=package_bytes, request=request)

            return original_async_client(
                *args,
                **kwargs,
                transport=httpx.MockTransport(handle_request),
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "plugin-upgrade.json"
            with (
                mock.patch.dict(os.environ, {"PLUGIN_UPGRADE_CONFIG_PATH": str(config_path)}),
                mock.patch(
                    "server.app.services.PluginRemoteControlService.httpx.AsyncClient",
                    side_effect=build_client,
                ),
            ):
                result = asyncio.run(
                    service.refresh_upgrade_package_metadata(
                        {
                            "enabled": True,
                            "latest_version": "0.0.45",
                            "package_url": "https://example.com/tianxuan.zip",
                            "package_sha256": "ab" * 32,
                            "silent_update": True,
                        }
                    )
                )
            persisted = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertEqual(result["latest_version"], "0.0.46")
        self.assertEqual(result["package_sha256"], expected_sha256)
        self.assertTrue(result["silent_update"])
        self.assertEqual(persisted["latest_version"], "0.0.46")
        self.assertEqual(persisted["package_sha256"], expected_sha256)

    def test_force_does_not_allow_downgrade(self):
        service = self._service()
        with mock.patch.object(
            PluginRemoteControlService,
            "load_upgrade_config",
            return_value={
                "enabled": True,
                "latest_version": "0.0.42",
                "package_url": "https://example.com/tianxuan.zip",
                "package_sha256": "ab" * 32,
                "target_folder_name": "tianxuan",
                "silent_update": True,
            },
        ):
            notice = service.build_upgrade_notice({"extension_version": "0.0.43"}, force=True)

        self.assertIsNone(notice)

    def test_batch_upgrade_loads_config_once(self):
        service = self._service()
        service.manager = FakeUpgradeManager()
        config = {
            "enabled": True,
            "latest_version": "0.0.44",
            "package_url": "https://example.com/tianxuan.zip",
            "package_sha256": "ab" * 32,
            "target_folder_name": "tianxuan",
            "silent_update": True,
        }

        async def get_client(client_id):
            return {"id": client_id, "extension_version": "0.0.43"}

        service.get_client = get_client
        with (
            mock.patch.object(service, "load_upgrade_config", return_value=config) as load_config,
            mock.patch.object(
                service,
                "refresh_upgrade_package_metadata",
                new=mock.AsyncMock(return_value=config),
            ) as refresh_metadata,
        ):
            result = asyncio.run(service.notify_upgrade([1, 2, 3]))

        self.assertEqual(result["sent"], 3)
        load_config.assert_called_once_with()
        refresh_metadata.assert_awaited_once_with(config)


if __name__ == "__main__":
    unittest.main()
