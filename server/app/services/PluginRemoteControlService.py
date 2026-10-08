import asyncio
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse

import httpx
from loguru import logger

from server.app.core.PluginWebSocketManager import PluginWebSocketManager
from server.app.db.base import MySQLBaseDAO


ACTION_TASK_TYPES = {
    "pgy_cookie_upload": 90,
    "catalog_fetch": 91,
    "catalog_update": 92,
    "catalog_update_by_uid": 97,
    "catalog_retry_failed": 93,
    "catalog_update_signed": 94,
    "pgy_invitation_messages": 95,
    "pgy_invitation_wechat": 96,
    "pgy_invitation_send": 98,
    "pgy_invitation_wechat_by_ids": 106,
    "pgy_outreach_due_fetch": 107,
    "xingtu_catalog_fetch": 101,
    "xingtu_catalog_update": 102,
    "xingtu_catalog_update_by_uid": 105,
    "xingtu_catalog_retry_failed": 103,
    "xingtu_catalog_update_signed": 104,
    "viral_xhs_note_list": 108,
    "viral_douyin_item_list": 109,
    "pgy_creator_out_sign": 110,
    "xingtu_creator_out_sign": 111,
}
GENERIC_ACTION_TASK_TYPE = 99

ACTION_ALIASES = {
    "pgy.cookie_upload": "pgy_cookie_upload",
    "pgy.catalog_fetch": "catalog_fetch",
    "pgy.catalog_update": "catalog_update",
    "pgy.catalog_update_by_uid": "catalog_update_by_uid",
    "pgy.catalog_retry_failed": "catalog_retry_failed",
    "pgy.catalog_update_signed": "catalog_update_signed",
    "pgy.invitation_messages": "pgy_invitation_messages",
    "pgy.invitation_wechat": "pgy_invitation_wechat",
    "pgy.invitation_send": "pgy_invitation_send",
    "pgy.invitation_wechat_by_ids": "pgy_invitation_wechat_by_ids",
    "pgy.outreach_due_fetch": "pgy_outreach_due_fetch",
    "xingtu.catalog_fetch": "xingtu_catalog_fetch",
    "xingtu.catalog_update": "xingtu_catalog_update",
    "xingtu.catalog_update_by_uid": "xingtu_catalog_update_by_uid",
    "xingtu.catalog_retry_failed": "xingtu_catalog_retry_failed",
    "xingtu.catalog_update_signed": "xingtu_catalog_update_signed",
    "viral.xhs.note_list": "viral_xhs_note_list",
    "viral.douyin.item_list": "viral_douyin_item_list",
    "pgy.creator_out_sign": "pgy_creator_out_sign",
    "xingtu.creator_out_sign": "xingtu_creator_out_sign",
}

FINAL_EXECUTION_STATUSES = {"success", "partial_failed", "failed", "stopped", "timeout"}
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_UPGRADE_CONFIG_PATH = PROJECT_ROOT / "data" / "plugin_upgrade.json"
DEFAULT_UPGRADE_CONFIG = {
    "enabled": False,
    "latest_version": "",
    "title": "天选插件发现新版本",
    "changelog": [],
    "package_url": "",
    "package_name": "",
    "package_sha256": "",
    "target_folder_name": "tianxuan",
    "silent_update": False,
    "changed_files": [],
    "force": False,
}
UPGRADE_NOTIFY_CONCURRENCY = 20
MAX_UPGRADE_PACKAGE_BYTES = 200 * 1024 * 1024


class PluginRemoteControlService:
    """Remote browser control built on the existing spider task/client/task-log tables."""

    def __init__(self, manager: PluginWebSocketManager):
        self.manager = manager
        self.client_dao = MySQLBaseDAO("fp_spider_client")
        self.task_dao = MySQLBaseDAO("fp_spider_task")
        self.client_task_dao = MySQLBaseDAO("fp_spider_client_task")
        self.task_log_dao = MySQLBaseDAO("fp_spider_client_task_log")
        self.blogger_dao = MySQLBaseDAO("fp_spider_blogger")
        self.client_account_dao = MySQLBaseDAO("fp_plugin_client_account")
        self.employee_dao = MySQLBaseDAO("fp_employee")

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_sha256(value: Any) -> str:
        text = re.sub(r"\s+", "", str(value or "")).lower()
        return text if re.fullmatch(r"[0-9a-f]{64}", text) else ""

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @staticmethod
    def _string_list(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [text for item in value if (text := str(item or "").strip())]

    @staticmethod
    def _is_http_url(value: str) -> bool:
        try:
            parsed = urlparse(value)
            if parsed.scheme == "https" and parsed.netloc:
                return True
            return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        except ValueError:
            return False

    @staticmethod
    def _versioned_package_url(package_url: str, package_sha256: str) -> str:
        if not package_sha256:
            return package_url
        parsed = urlparse(package_url)
        query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key != "tianxuan_sha256"
        ]
        query.append(("tianxuan_sha256", package_sha256))
        return parsed._replace(query=urlencode(query)).geturl()

    @staticmethod
    def _upgrade_config_path() -> Path:
        configured = str(os.getenv("PLUGIN_UPGRADE_CONFIG_PATH") or "").strip()
        if not configured:
            return DEFAULT_UPGRADE_CONFIG_PATH
        path = Path(configured).expanduser()
        return path if path.is_absolute() else PROJECT_ROOT / path

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def _version_tuple(version: str) -> tuple:
        parts = re.findall(r"\d+", str(version or ""))
        return tuple(int(part) for part in parts[:6])

    @staticmethod
    def _is_valid_extension_version(version: str) -> bool:
        text = str(version or "").strip()
        if not re.fullmatch(r"\d+(?:\.\d+){0,3}", text):
            return False
        return all(0 <= int(part) <= 65535 for part in text.split("."))

    @classmethod
    def _version_lt(cls, current: str, latest: str) -> bool:
        current_tuple = cls._version_tuple(current)
        latest_tuple = cls._version_tuple(latest)
        if not latest_tuple:
            return False
        size = max(len(current_tuple), len(latest_tuple))
        return current_tuple + (0,) * (size - len(current_tuple)) < latest_tuple + (0,) * (size - len(latest_tuple))

    @staticmethod
    def normalize_action(action: str) -> str:
        return ACTION_ALIASES.get(action, action)

    @staticmethod
    def _positive_int(value: Any) -> int:
        try:
            number = int(value or 0)
        except (TypeError, ValueError):
            return 0
        return number if number > 0 else 0

    @staticmethod
    def _is_enabled_client(client: Optional[Dict[str, Any]]) -> bool:
        return bool(
            client
            and client.get("status") == 1
            and PluginRemoteControlService._positive_int(client.get("admin_id"))
            and PluginRemoteControlService._positive_int(client.get("computer_id"))
        )

    @staticmethod
    def _apply_logged_in_enable(update: Dict[str, Any], employee_id: int) -> None:
        if employee_id:
            update["admin_id"] = employee_id
            update["status"] = 1

    async def _resolve_tianji_employee_id(self, data: Dict[str, Any]) -> int:
        """Resolve the extension-reported Tianji login into fp_employee.id.

        fp_spider_client.admin_id is historically named, but the model relation
        points to fp_employee.id. The Tianji login payload usually exposes the
        admin account id, so we must translate it before binding.
        """
        employee_id = self._positive_int(data.get("tianji_employee_id"))
        if employee_id:
            employee = await self.employee_dao.fetch_one(
                """
                SELECT id
                FROM fp_employee
                WHERE id = :employee_id
                  AND (delete_time IS NULL OR delete_time = 0)
                LIMIT 1
                """,
                {"employee_id": employee_id},
            )
            if employee:
                return int(employee["id"])

        admin_id = self._positive_int(data.get("tianji_admin_id"))
        if not admin_id:
            return 0

        employee = await self.employee_dao.fetch_one(
            """
            SELECT id
            FROM fp_employee
            WHERE admin_id = :admin_id
              AND (delete_time IS NULL OR delete_time = 0)
            ORDER BY status DESC, id DESC
            LIMIT 1
            """,
            {"admin_id": admin_id},
        )
        return int(employee["id"]) if employee else 0

    async def _find_reinstall_claim_candidate(
        self, data: Dict[str, Any], ip_address: str
    ) -> Optional[Dict[str, Any]]:
        """Find one safe old browser instance to reuse after extension reinstall.

        A reinstall loses extension local storage, so the browser generates a
        new device_id and has no token. To avoid duplicate rows, we only auto
        claim when there is exactly one recently-seen, currently-offline plugin
        instance with the same public IP and browser type.
        """
        browser_type = str(data.get("browser_type") or "Unknown")
        rows = await self.client_dao.fetch_all(
            """
            SELECT *
            FROM fp_spider_client
            WHERE client_token_hash IS NOT NULL
              AND client_token_hash <> ''
              AND browser_type = :browser_type
              AND ip_address = :ip_address
              AND is_online = 0
              AND (last_heartbeat IS NULL OR last_heartbeat >= DATE_SUB(NOW(), INTERVAL 30 DAY))
            ORDER BY
              CASE WHEN status = 1 AND admin_id IS NOT NULL AND admin_id <> 0
                     AND computer_id IS NOT NULL AND computer_id <> 0
                   THEN 0 ELSE 1 END,
              last_heartbeat DESC,
              id DESC
            LIMIT 2
            """,
            {"browser_type": browser_type, "ip_address": ip_address},
        )
        if len(rows) == 1:
            return rows[0]
        if len(rows) > 1:
            logger.info(
                f"Plugin reinstall auto-claim skipped: multiple candidates, "
                f"ip={ip_address}, browser={browser_type}, ids={[row.get('id') for row in rows]}"
            )
        return None

    async def register(self, data: Dict[str, Any], ip_address: str) -> Dict[str, Any]:
        device_id = data["device_id"]
        existing = await self.client_dao.fetch_one(
            "SELECT * FROM fp_spider_client WHERE device_id = :device_id LIMIT 1",
            {"device_id": device_id},
        )
        now = datetime.now()
        raw_token = data.get("client_token") or ""
        if existing:
            stored_hash = existing.get("client_token_hash") or ""
            if not raw_token or not hmac.compare_digest(stored_hash, self._hash_token(raw_token)):
                raise PermissionError("browser instance token is invalid")
            update = {
                "browser_type": data.get("browser_type", "Unknown"),
                "browser_version": data.get("browser_version", ""),
                "extension_version": data.get("extension_version", ""),
                "ip_address": ip_address,
                "last_heartbeat": now,
                "update_time": now,
            }
            employee_id = await self._resolve_tianji_employee_id(data)
            self._apply_logged_in_enable(update, employee_id)
            if not employee_id and not self._positive_int(existing.get("admin_id")):
                update["admin_id"] = None
            await self.client_dao.update(update, {"id": existing["id"]})
            return self._registration_response(await self.get_client(existing["id"]), raw_token, False)

        raw_token = secrets.token_urlsafe(32)
        browser_type = data.get("browser_type", "Unknown")
        employee_id = await self._resolve_tianji_employee_id(data)

        if not (data.get("client_token") or ""):
            candidate = await self._find_reinstall_claim_candidate(data, ip_address)
            if candidate:
                old_device_id = candidate.get("device_id") or ""
                update = {
                    "client_name": candidate.get("client_name") or f"{browser_type}-{device_id[-6:].upper()}",
                    "plugin_instance_name": candidate.get("plugin_instance_name") or f"{browser_type}-{device_id[-6:].upper()}",
                    "device_id": device_id,
                    "ip_address": ip_address,
                    "is_online": 0,
                    "browser_type": browser_type,
                    "browser_version": data.get("browser_version", ""),
                    "extension_version": data.get("extension_version", ""),
                    "client_token_hash": self._hash_token(raw_token),
                    "last_heartbeat": now,
                    "update_time": now,
                }
                self._apply_logged_in_enable(update, employee_id)
                if not employee_id and not self._positive_int(candidate.get("admin_id")):
                    update["admin_id"] = None
                await self.client_dao.update(update, {"id": candidate["id"]})
                logger.info(
                    f"Plugin reinstall auto-claimed old instance: "
                    f"client={candidate['id']}, old_device={old_device_id}, new_device={device_id}, ip={ip_address}"
                )
                return self._registration_response(await self.get_client(candidate["id"]), raw_token, False)

        instance_name = f"{browser_type}-{device_id[-6:].upper()}"
        client_id = await self.client_dao.insert({
            "client_name": instance_name,
            "plugin_instance_name": instance_name,
            "device_id": device_id,
            "ip_address": ip_address,
            "admin_id": employee_id or None,
            "status": 1 if employee_id else 0,
            "is_online": 0,
            "computer_id": None,
            "browser_type": browser_type,
            "browser_version": data.get("browser_version", ""),
            "extension_version": data.get("extension_version", ""),
            "client_token_hash": self._hash_token(raw_token),
            "last_heartbeat": now,
            "create_time": now,
            "update_time": now,
        })
        return self._registration_response(await self.get_client(client_id), raw_token, True)

    def _registration_response(self, client: Dict[str, Any], token: str, created: bool) -> Dict[str, Any]:
        return {
            "ok": True,
            "created": created,
            "client_id": client["id"],
            "client_token": token,
            "enabled": self._is_enabled_client(client),
            "client_name": client.get("plugin_instance_name") or client.get("client_name"),
        }

    def load_upgrade_config(self) -> Dict[str, Any]:
        path = self._upgrade_config_path()
        try:
            if not path.exists():
                logger.warning(f"插件升级配置不存在，升级通知已关闭: path={path}")
                return dict(DEFAULT_UPGRADE_CONFIG)
            with path.open("r", encoding="utf-8-sig") as file:
                config = json.load(file)
            if not isinstance(config, dict):
                raise ValueError("upgrade config root must be an object")

            merged = {**DEFAULT_UPGRADE_CONFIG, **config}
            merged.update({
                "enabled": self._as_bool(merged.get("enabled")),
                "latest_version": str(merged.get("latest_version") or "").strip(),
                "title": str(merged.get("title") or DEFAULT_UPGRADE_CONFIG["title"]).strip(),
                "changelog": self._string_list(merged.get("changelog")),
                "package_url": str(merged.get("package_url") or "").strip(),
                "package_name": str(merged.get("package_name") or "").strip(),
                "package_sha256": self._normalize_sha256(merged.get("package_sha256")),
                "target_folder_name": str(merged.get("target_folder_name") or "tianxuan").strip(),
                "silent_update": self._as_bool(merged.get("silent_update")),
                "changed_files": self._string_list(merged.get("changed_files")),
                "force": self._as_bool(merged.get("force")),
            })
            if not re.fullmatch(r"[A-Za-z0-9._-]+", merged["target_folder_name"]):
                logger.warning(
                    f"插件升级目录名非法，已使用默认值: value={merged['target_folder_name']!r}"
                )
                merged["target_folder_name"] = "tianxuan"
            return merged
        except Exception as exc:
            logger.warning(f"读取插件升级配置失败: path={path}, error={exc}")
            return dict(DEFAULT_UPGRADE_CONFIG)

    @classmethod
    def _read_package_version(cls, package: bytes) -> str:
        try:
            with zipfile.ZipFile(io.BytesIO(package)) as archive:
                manifest_names = [
                    name
                    for name in archive.namelist()
                    if name == "manifest.json"
                    or re.fullmatch(r"[^/]+/manifest\.json", name)
                ]
                if len(manifest_names) != 1:
                    raise ValueError("升级包必须包含唯一的 manifest.json")
                manifest = json.loads(archive.read(manifest_names[0]).decode("utf-8-sig"))
        except (zipfile.BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"升级包不是有效的天选插件 ZIP: {exc}") from exc
        version = str(manifest.get("version") or "").strip() if isinstance(manifest, dict) else ""
        if not cls._is_valid_extension_version(version):
            raise ValueError(f"升级包 manifest.json 版本无效: {version!r}")
        return version

    def _save_upgrade_config(self, config: Dict[str, Any]) -> None:
        path = self._upgrade_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
        try:
            temporary.write_text(
                json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    async def refresh_upgrade_package_metadata(self, config: Dict[str, Any]) -> Dict[str, Any]:
        package_url = str(config.get("package_url") or "").strip()
        if not self._is_http_url(package_url):
            raise ValueError(f"插件升级包 URL 无效: {package_url!r}")
        parsed_package_url = urlparse(package_url)
        package_query = parse_qsl(parsed_package_url.query, keep_blank_values=True)
        package_query.append(("tianxuan_refresh", str(int(datetime.now().timestamp() * 1000))))
        refresh_url = parsed_package_url._replace(query=urlencode(package_query)).geturl()

        digest = hashlib.sha256()
        package_chunks = []
        package_size = 0
        timeout = httpx.Timeout(120.0, connect=15.0)
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
                async with client.stream(
                    "GET",
                    refresh_url,
                    headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
                ) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        package_size += len(chunk)
                        if package_size > MAX_UPGRADE_PACKAGE_BYTES:
                            raise ValueError("插件升级包超过 200 MB，已停止推送")
                        digest.update(chunk)
                        package_chunks.append(chunk)
        except httpx.HTTPError as exc:
            raise ValueError(f"下载线上插件升级包失败: {exc}") from exc

        if package_size == 0:
            raise ValueError("插件升级包为空")
        package = b"".join(package_chunks)
        package_version = self._read_package_version(package)
        package_sha256 = digest.hexdigest()
        refreshed = {
            **config,
            "latest_version": package_version,
            "package_sha256": package_sha256,
            "silent_update": True,
        }
        self._save_upgrade_config(refreshed)
        logger.info(
            f"插件升级包校验完成: version={package_version}, sha256={package_sha256}, size={package_size}"
        )
        return refreshed

    def build_upgrade_notice(
        self,
        client: Dict[str, Any],
        force: bool = False,
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        config = config if config is not None else self.load_upgrade_config()
        latest_version = str(config.get("latest_version") or "").strip()
        package_url = str(config.get("package_url") or "").strip()
        package_sha256 = self._normalize_sha256(config.get("package_sha256"))
        versioned_package_url = self._versioned_package_url(package_url, package_sha256)
        current_version = str(client.get("extension_version") or "").strip()
        if not self._as_bool(config.get("enabled")) or not self._is_valid_extension_version(latest_version):
            return None
        if not self._is_http_url(package_url):
            logger.warning(f"插件升级包 URL 无效，已跳过通知: url={package_url!r}")
            return None
        current_tuple = self._version_tuple(current_version)
        latest_tuple = self._version_tuple(latest_version)
        size = max(len(current_tuple), len(latest_tuple))
        padded_current = current_tuple + (0,) * (size - len(current_tuple))
        padded_latest = latest_tuple + (0,) * (size - len(latest_tuple))
        if current_tuple and padded_current > padded_latest:
            logger.warning(
                f"拒绝向较新插件下发旧版本: current={current_version}, latest={latest_version}"
            )
            return None
        configured_force = self._as_bool(config.get("force"))
        if not (force or configured_force or self._version_lt(current_version, latest_version)):
            return None
        silent_update = self._as_bool(config.get("silent_update")) and bool(package_sha256)
        if self._as_bool(config.get("silent_update")) and not package_sha256:
            logger.warning("插件升级包缺少有效 SHA-256，已降级为手动更新")
        return {
            "latest_version": latest_version,
            "current_version": current_version,
            "title": str(config.get("title") or "天选插件发现新版本"),
            "changelog": config.get("changelog") if isinstance(config.get("changelog"), list) else [],
            "package_url": versioned_package_url,
            "package_name": str(config.get("package_name") or f"tianxuan-{latest_version}.zip"),
            "package_sha256": package_sha256,
            "target_folder_name": str(config.get("target_folder_name") or "tianxuan"),
            "silent_update": silent_update,
            "changed_files": config.get("changed_files") if isinstance(config.get("changed_files"), list) else [],
            "force": bool(force or configured_force),
        }

    async def send_upgrade_notice(
        self,
        client_id: int,
        force: bool = False,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        client = await self.get_client(client_id)
        if not client:
            return {"client_id": client_id, "sent": False, "message": "browser instance not found"}
        notice = self.build_upgrade_notice(client, force=force, config=config)
        if not notice:
            return {"client_id": client_id, "sent": False, "message": "no upgrade notice matched"}
        if not self.manager.is_connected(client_id):
            return {"client_id": client_id, "sent": False, "message": "browser instance is offline"}
        sent = await self.manager.send(client_id, {
            "cmd": "plugin_upgrade_notice",
            "data": notice,
            "timestamp": datetime.now().timestamp(),
        })
        return {"client_id": client_id, "sent": sent, "message": "sent" if sent else "send failed"}

    async def notify_upgrade(self, client_ids: List[int], force: bool = False) -> Dict[str, Any]:
        semaphore = asyncio.Semaphore(UPGRADE_NOTIFY_CONCURRENCY)
        config = await self.refresh_upgrade_package_metadata(self.load_upgrade_config())

        async def send(client_id: int) -> Dict[str, Any]:
            async with semaphore:
                try:
                    return await self.send_upgrade_notice(int(client_id), force=force, config=config)
                except Exception as exc:
                    logger.exception(f"推送插件升级通知失败: client={client_id}, error={exc}")
                    return {
                        "client_id": int(client_id),
                        "sent": False,
                        "message": "internal send error",
                    }

        results = await asyncio.gather(*(send(client_id) for client_id in client_ids))
        return {
            "total": len(results),
            "sent": sum(1 for item in results if item.get("sent")),
            "results": results,
        }

    async def authenticate(self, device_id: str, token: str) -> Optional[Dict[str, Any]]:
        client = await self.client_dao.fetch_one(
            "SELECT * FROM fp_spider_client WHERE device_id = :device_id LIMIT 1",
            {"device_id": device_id},
        )
        if not client or not token:
            return None
        expected = client.get("client_token_hash") or ""
        return client if hmac.compare_digest(expected, self._hash_token(token)) else None

    async def get_client(self, client_id: int) -> Optional[Dict[str, Any]]:
        return await self.client_dao.fetch_one(
            "SELECT * FROM fp_spider_client WHERE id = :id LIMIT 1", {"id": client_id}
        )

    async def set_online(self, client_id: int, online: bool):
        now = datetime.now()
        await self.client_dao.update({
            "is_online": 1 if online else 0,
            "last_heartbeat": now,
            "update_time": now,
        }, {"id": client_id})

    async def reset_online_state(self):
        """A restarted process has no live sockets, so persisted online flags are stale."""
        await self.client_dao.execute(
            """
            UPDATE fp_spider_client
            SET is_online = 0, update_time = :now
            WHERE client_token_hash IS NOT NULL AND client_token_hash <> ''
            """,
            {"now": datetime.now()},
        )

    async def recover_stale_executions(self):
        """Finish plugin executions left active by a previous Python process."""
        await asyncio.sleep(30)
        rows = await self.client_task_dao.fetch_all(
            """
            SELECT e.id, e.client_id, e.task_id, e.progress,
                   l.total_num, l.succ_num, l.fail_num
            FROM fp_spider_client_task e
            INNER JOIN fp_spider_task t ON t.id = e.task_id
            LEFT JOIN fp_spider_client_task_log l ON l.id = e.task_log_id
            WHERE t.control_action IS NOT NULL AND e.status IN (0, 1)
            """
        )
        task_ids = set()
        for row in rows:
            await self._finish_execution(
                int(row["id"]),
                3,
                "Python 服务重启，未收到插件完成结果",
                int(row.get("total_num") or 0),
                int(row.get("succ_num") or 0),
                int(row.get("fail_num") or 0),
                float(row.get("progress") or 0),
            )
            self.manager.release_execution(int(row["client_id"]), int(row["id"]))
            task_ids.add(int(row["task_id"]))
        for task_id in task_ids:
            await self.refresh_task_status(task_id)

    async def update_account_context(self, client_id: int, data: Dict[str, Any]):
        now = datetime.now()
        update = {"last_heartbeat": now, "update_time": now}
        employee_id = await self._resolve_tianji_employee_id(data)
        self._apply_logged_in_enable(update, employee_id)
        if "pgy_company_name" in data:
            update["pgy_company_name"] = str(data.get("pgy_company_name") or "")[:128]
        if "pgy_account" in data:
            update["pgy_account"] = str(data.get("pgy_account") or "")[:128]
        if data.get("cookie_uploaded"):
            update["cookie_uploaded_at"] = now
        await self.client_dao.update(update, {"id": client_id})
        await self._upsert_platform_account(client_id, data, now)

    async def _upsert_platform_account(self, client_id: int, data: Dict[str, Any], now: datetime):
        platform = str(data.get("platform") or "pgy")[:32]
        account_name = str(data.get("pgy_account") or data.get("account_name") or "")[:128]
        company_name = str(data.get("pgy_company_name") or data.get("company_name") or "")[:128]
        platform_user_id = str(data.get("pgy_user_id") or data.get("platform_user_id") or account_name)[:64]
        platform_red_id = str(data.get("pgy_red_id") or data.get("platform_red_id") or "")[:64]
        platform_nickname = str(data.get("pgy_nickname") or data.get("platform_nickname") or company_name)[:128]
        if platform != "pgy" and not account_name and not company_name:
            account_name = "已连接"
        platform_name = {
            "douyin": "抖音",
            "pgy": "蒲公英",
            "xingtu": "星图/抖音",
            "channels": "视频号",
        }.get(platform, platform)
        cookie_uploaded_at = now if data.get("cookie_uploaded") else None
        context_json = self._json(data)
        try:
            existing = await self.client_account_dao.fetch_one(
                """
                SELECT id, cookie_uploaded_at
                FROM fp_plugin_client_account
                WHERE client_id = :client_id AND platform = :platform
                LIMIT 1
                """,
                {"client_id": client_id, "platform": platform},
            )
            row = {
                "platform_name": platform_name,
                "account_name": account_name,
                "company_name": company_name,
                "platform_user_id": platform_user_id,
                "platform_red_id": platform_red_id,
                "platform_nickname": platform_nickname,
                "last_verified_at": now if platform_user_id else None,
                "context_json": context_json,
                "update_time": now,
            }
            if cookie_uploaded_at:
                row["cookie_uploaded_at"] = cookie_uploaded_at
            if existing:
                await self.client_account_dao.update(row, {"id": existing["id"]})
            else:
                await self.client_account_dao.insert({
                    **row,
                    "client_id": client_id,
                    "platform": platform,
                    "cookie_uploaded_at": cookie_uploaded_at,
                    "create_time": now,
                })
        except Exception as exc:
            logger.warning(f"同步插件平台账号上下文失败: client={client_id}, platform={platform}, error={exc}")

    async def create_batch(self, request: Dict[str, Any]) -> Dict[str, Any]:
        action = self.normalize_action(str(request["action"]))
        params = request.get("params") or {}
        client_ids = request["client_ids"]
        now = datetime.now()
        task_id = await self.task_dao.insert({
            "spider_task_title": request.get("title") or action,
            "platform_id": 0,
            "period_type": 3,
            "task_type": ACTION_TASK_TYPES.get(action, GENERIC_ACTION_TASK_TYPE),
            "status": 1,
            "start_time": now,
            "end_time": now,
            "head_users": str(request.get("operator_id", 0)),
            "create_user": request.get("operator_id", 0),
            "create_time": now,
            "update_user": request.get("operator_id", 0),
            "update_time": now,
            "control_action": action,
            "control_params": self._json(params),
            "stop_requested": 0,
            "trigger_source": request.get("trigger_source", "manual"),
            "trigger_rule_id": request.get("trigger_rule_id"),
        })

        executions = []
        for client_id in client_ids:
            client = await self.get_client(client_id)
            eligible, reason = await self._client_eligibility(client_id, client)
            client_task_id = await self.client_task_dao.insert({
                "task_id": task_id,
                "client_id": client_id,
                "task_process": 0,
                "status": 0 if eligible else 3,
                "start_time": now,
                "end_time": None if eligible else now,
                "result": "" if eligible else reason[:256],
                "create_time": now,
                "update_time": now,
                "create_user": request.get("operator_id", 0),
                "update_user": request.get("operator_id", 0),
                "task_log_id": None,
                "progress": 0,
            })
            log_id = await self.task_log_dao.insert({
                "client_task_id": client_task_id,
                "client_id": client_id,
                "task_id": task_id,
                "start_time": now,
                "completed_time": None if eligible else now,
                "result": "" if eligible else reason[:128],
                "total_num": 0,
                "fail_num": 0 if eligible else 1,
                "succ_num": 0,
                "status": 0 if eligible else 3,
                "create_time": now,
                "update_time": now,
                "progress": 0,
            })
            await self.client_task_dao.update({"task_log_id": log_id}, {"id": client_task_id})

            sent = False
            if eligible:
                if not self.manager.claim_execution(client_id, client_task_id):
                    reason = "浏览器实例已有任务正在执行"
                    await self._finish_execution(client_task_id, 3, reason, 0, 0, 1, 0)
                else:
                    sent = await self.manager.send(client_id, {
                        "cmd": "plugin_command",
                        "batch_id": task_id,
                        "execution_id": client_task_id,
                        "action": action,
                        "params": params,
                        "timestamp": now.timestamp(),
                    })
                    if sent:
                        await self.client_task_dao.update({"status": 1, "update_time": now}, {"id": client_task_id})
                        await self.task_log_dao.update({"status": 1, "update_time": now}, {"id": log_id})
                        asyncio.create_task(self._fail_execution_after_timeout(client_task_id, client_id, task_id))
                    else:
                        reason = "浏览器实例已离线"
                        self.manager.release_execution(client_id, client_task_id)
                        await self._finish_execution(client_task_id, 3, reason, 0, 0, 1, 0)
            executions.append({"execution_id": client_task_id, "client_id": client_id, "sent": sent, "message": reason})

        await self.refresh_task_status(task_id)
        return {"batch_id": task_id, "executions": executions}

    async def _client_eligibility(self, client_id: int, client: Optional[Dict[str, Any]]) -> tuple[bool, str]:
        if not client:
            return False, "浏览器实例不存在"
        if not (client.get("status") == 1 and client.get("admin_id") and client.get("computer_id")):
            return False, "浏览器实例尚未绑定员工、电脑分组或未启用"
        if not self.manager.is_connected(client_id):
            return False, "浏览器实例已离线"
        running = await self.client_task_dao.fetch_one(
            "SELECT id FROM fp_spider_client_task WHERE client_id = :client_id AND status = 1 LIMIT 1",
            {"client_id": client_id},
        )
        if running:
            return False, "浏览器实例已有任务正在执行"
        return True, ""

    async def handle_event(self, client_id: int, event: Dict[str, Any]):
        cmd = event.get("cmd")
        data = event.get("data") or {}
        execution_id = event.get("execution_id")
        self.manager.touch(client_id)
        if cmd in {"heartbeat_response", "client_context"}:
            await self.update_account_context(client_id, data)
            return
        if not execution_id:
            return
        execution = await self.client_task_dao.fetch_one(
            "SELECT * FROM fp_spider_client_task WHERE id = :id AND client_id = :client_id LIMIT 1",
            {"id": execution_id, "client_id": client_id},
        )
        if not execution:
            logger.warning(f"忽略未知插件执行事件: client={client_id}, execution={execution_id}")
            return
        if int(execution.get("status") or 0) in {2, 3, 4}:
            logger.info(f"忽略已结束的插件执行事件: client={client_id}, execution={execution_id}, cmd={cmd}")
            return
        now = datetime.now()
        log_id = execution.get("task_log_id")
        if cmd == "command_ack":
            await self.client_task_dao.update({"status": 1, "start_time": now, "update_time": now}, {"id": execution_id})
        elif cmd == "command_progress":
            total = int(data.get("total", 0) or 0)
            success = int(data.get("success", 0) or 0)
            failed = int(data.get("failed", 0) or 0)
            progress = float(data.get("progress", 0) or 0)
            await self.client_task_dao.update({
                "status": 1, "task_process": progress, "progress": progress,
                "result": str(data.get("message") or "")[:256], "update_time": now,
            }, {"id": execution_id})
            if log_id:
                await self.task_log_dao.update({
                    "status": 1, "total_num": total, "succ_num": success,
                    "fail_num": failed, "progress": progress, "update_time": now,
                }, {"id": log_id})
        elif cmd == "command_item_result":
            try:
                await self._save_blogger_result(execution["task_id"], client_id, data)
            except Exception as exc:
                # Item details are useful for retry, but must not block the final task result.
                logger.exception(
                    f"保存插件执行明细失败: client={client_id}, execution={execution_id}: {exc}"
                )
        elif cmd == "command_complete":
            status_name = str(data.get("status") or "failed")
            if status_name not in FINAL_EXECUTION_STATUSES:
                status_name = "failed"
            status = 2 if status_name == "success" else (4 if status_name == "stopped" else 3)
            message = str(data.get("error") or data.get("message") or status_name)
            if isinstance(data.get("failed_items"), list):
                for item in data.get("failed_items")[:1000]:
                    if isinstance(item, dict):
                        try:
                            await self._save_blogger_result(execution["task_id"], client_id, {
                                "item_key": item.get("platform_user_id") or item.get("star_id") or item.get("creator_id"),
                                "item_name": item.get("creator_nickname") or item.get("nickname") or item.get("name"),
                                "success": False,
                                "error": item.get("reason") or message,
                                "payload": item,
                            })
                        except Exception as exc:
                            logger.warning(f"保存插件失败项明细失败: task={execution['task_id']}, client={client_id}, error={exc}")
            await self._finish_execution(
                execution_id, status, message,
                int(data.get("total", 0) or 0),
                int(data.get("success", 0) or 0),
                int(data.get("failed", 0) or 0),
                float(data.get("progress", 100 if status == 2 else 0) or 0),
            )
            self.manager.release_execution(client_id, execution_id)
            if data.get("cookie_uploaded"):
                await self.update_account_context(client_id, data)
        await self.refresh_task_status(execution["task_id"])

    async def _finish_execution(self, execution_id: int, status: int, message: str, total: int, success: int, failed: int, progress: float):
        execution = await self.client_task_dao.fetch_one(
            "SELECT * FROM fp_spider_client_task WHERE id = :id LIMIT 1", {"id": execution_id}
        )
        if not execution:
            return
        now = datetime.now()
        await self.client_task_dao.update({
            "status": status, "task_process": progress, "progress": progress,
            "result": message[:256], "end_time": now, "update_time": now,
        }, {"id": execution_id})
        if execution.get("task_log_id"):
            await self.task_log_dao.update({
                "status": status, "total_num": total, "succ_num": success,
                "fail_num": failed, "progress": progress,
                "result": message[:128], "completed_time": now, "update_time": now,
            }, {"id": execution["task_log_id"]})

    async def _fail_execution_after_timeout(self, execution_id: int, client_id: int, task_id: int):
        timeout = max(60, int(os.getenv("PLUGIN_COMMAND_TIMEOUT", "1800")))
        await asyncio.sleep(timeout)
        execution = await self.client_task_dao.fetch_one(
            """
            SELECT e.status, e.progress, l.total_num, l.succ_num, l.fail_num
            FROM fp_spider_client_task e
            LEFT JOIN fp_spider_client_task_log l ON l.id = e.task_log_id
            WHERE e.id = :id LIMIT 1
            """,
            {"id": execution_id},
        )
        if not execution or int(execution.get("status") or 0) != 1:
            return
        await self._finish_execution(
            execution_id, 3, f"插件执行超过 {timeout} 秒，任务已超时",
            int(execution.get("total_num") or 0),
            int(execution.get("succ_num") or 0),
            int(execution.get("fail_num") or 0),
            float(execution.get("progress") or 0),
        )
        self.manager.release_execution(client_id, execution_id)
        await self.refresh_task_status(task_id)

    async def finish_disconnected_executions(self, client_id: int):
        await asyncio.sleep(30)
        if self.manager.is_connected(client_id):
            return
        rows = await self.client_task_dao.fetch_all(
            """
            SELECT e.id, e.task_id, e.progress, l.total_num, l.succ_num, l.fail_num
            FROM fp_spider_client_task e
            INNER JOIN fp_spider_task t ON t.id = e.task_id
            LEFT JOIN fp_spider_client_task_log l ON l.id = e.task_log_id
            WHERE e.client_id = :client_id
              AND e.status = 1
              AND t.control_action IS NOT NULL
            """,
            {"client_id": client_id},
        )
        task_ids = set()
        for row in rows:
            await self._finish_execution(
                int(row["id"]), 3, "浏览器连接中断，未收到任务完成结果",
                int(row.get("total_num") or 0),
                int(row.get("succ_num") or 0),
                int(row.get("fail_num") or 0),
                float(row.get("progress") or 0),
            )
            self.manager.release_execution(client_id, int(row["id"]))
            task_ids.add(int(row["task_id"]))
        for task_id in task_ids:
            await self.refresh_task_status(task_id)

    async def _save_blogger_result(self, task_id: int, client_id: int, data: Dict[str, Any]):
        user_id = str(data.get("item_key") or data.get("blogger_id") or "")[:64]
        if not user_id:
            return
        existing = await self.blogger_dao.fetch_one(
            "SELECT id FROM fp_spider_blogger WHERE task_id = :task_id AND client_id = :client_id AND user_id = :user_id LIMIT 1",
            {"task_id": task_id, "client_id": client_id, "user_id": user_id},
        )
        payload = data.get("payload") or {}
        row = {
            "pgy_url": str(payload.get("pgy_link") or payload.get("pgy_url") or "")[:100],
            "user_id": user_id,
            "nickname": str(data.get("item_name") or payload.get("creator_nickname") or "")[:100],
            "status": 1 if data.get("success") else 2,
            "type": 5,
            "error_message": str(data.get("error") or "")[:1000],
            "payload_json": self._json(payload),
            "update_time": datetime.now(),
        }
        if existing:
            await self.blogger_dao.update(row, {"id": existing["id"]})
        else:
            await self.blogger_dao.insert({
                **row, "task_id": task_id, "client_id": client_id, "create_time": datetime.now()
            })

    async def stop_batch(self, batch_id: int) -> Dict[str, Any]:
        task = await self.task_dao.fetch_one("SELECT * FROM fp_spider_task WHERE id = :id LIMIT 1", {"id": batch_id})
        if not task or not task.get("control_action"):
            raise ValueError("批量任务不存在")
        now = datetime.now()
        await self.task_dao.update({"stop_requested": 1, "update_time": now}, {"id": batch_id})
        executions = await self.client_task_dao.fetch_all(
            "SELECT * FROM fp_spider_client_task WHERE task_id = :task_id AND status = 1",
            {"task_id": batch_id},
        )
        sent = 0
        pending_stop_ids = []
        for execution in executions:
            ok = await self.manager.send(execution["client_id"], {
                "cmd": "plugin_command_stop", "batch_id": batch_id,
                "execution_id": execution["id"], "timestamp": now.timestamp(),
            })
            if ok:
                sent += 1
                pending_stop_ids.append(int(execution["id"]))
            else:
                self.manager.release_execution(execution["client_id"], execution["id"])
                await self._finish_execution(execution["id"], 4, "浏览器离线，任务已停止", 0, 0, 0, float(execution.get("progress") or 0))
        if pending_stop_ids:
            asyncio.create_task(self._force_stop_after_delay(batch_id, pending_stop_ids))
        await self.refresh_task_status(batch_id)
        return {"batch_id": batch_id, "stop_sent": sent}

    async def _force_stop_after_delay(self, batch_id: int, execution_ids: List[int]):
        await asyncio.sleep(10)
        for execution_id in execution_ids:
            execution = await self.client_task_dao.fetch_one(
                """
                SELECT e.client_id, e.status, e.progress,
                       l.total_num, l.succ_num, l.fail_num
                FROM fp_spider_client_task e
                LEFT JOIN fp_spider_client_task_log l ON l.id = e.task_log_id
                WHERE e.id = :id LIMIT 1
                """,
                {"id": execution_id},
            )
            if not execution or int(execution.get("status") or 0) != 1:
                continue
            await self._finish_execution(
                execution_id, 4, "停止指令超时，后台已强制结束任务",
                int(execution.get("total_num") or 0),
                int(execution.get("succ_num") or 0),
                int(execution.get("fail_num") or 0),
                float(execution.get("progress") or 0),
            )
            self.manager.release_execution(int(execution["client_id"]), execution_id)
        await self.refresh_task_status(batch_id)

    async def retry_failed(self, batch_id: int, client_ids: Optional[List[int]], operator_id: int) -> Dict[str, Any]:
        task = await self.task_dao.fetch_one(
            "SELECT control_action FROM fp_spider_task WHERE id = :id LIMIT 1",
            {"id": batch_id},
        )
        retry_action = "xingtu_catalog_retry_failed" if str(task.get("control_action") if task else "").startswith("xingtu_") else "catalog_retry_failed"
        executions = await self.client_task_dao.fetch_all(
            "SELECT * FROM fp_spider_client_task WHERE task_id = :task_id AND status IN (3,4)",
            {"task_id": batch_id},
        )
        if client_ids:
            allowed = set(client_ids)
            executions = [item for item in executions if item["client_id"] in allowed]
        if not executions:
            raise ValueError("没有可重试的失败实例")
        items_by_client: Dict[str, List[Dict[str, Any]]] = {}
        retry_clients = []
        for execution in executions:
            rows = await self.blogger_dao.fetch_all(
                "SELECT payload_json FROM fp_spider_blogger WHERE task_id = :task_id AND client_id = :client_id AND status = 2",
                {"task_id": batch_id, "client_id": execution["client_id"]},
            )
            items_by_client[str(execution["client_id"])] = [
                json.loads(row.get("payload_json") or "{}") for row in rows
            ]
            retry_clients.append(execution["client_id"])
        return await self.create_batch({
            "action": retry_action,
            "client_ids": retry_clients,
            "params": {"source_task_id": batch_id, "items_by_client": items_by_client},
            "operator_id": operator_id,
            "title": f"重试任务 #{batch_id} 失败项",
        })

    async def refresh_task_status(self, task_id: int):
        rows = await self.client_task_dao.fetch_all(
            "SELECT status, COUNT(*) AS count FROM fp_spider_client_task WHERE task_id = :task_id GROUP BY status",
            {"task_id": task_id},
        )
        counts = {int(row["status"]): int(row["count"]) for row in rows}
        running = counts.get(0, 0) + counts.get(1, 0)
        await self.task_dao.update({
            "status": 1 if running else 0,
            "end_time": datetime.now(),
            "update_time": datetime.now(),
        }, {"id": task_id})
