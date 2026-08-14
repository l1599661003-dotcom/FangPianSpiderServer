import hashlib
import hmac
import json
import sqlite3
import time
import uuid
import base64
import os
import threading
from pathlib import Path
from contextlib import closing
from typing import Any, Optional

from loguru import logger

# 签名工具类
from Crypto.Cipher import DES3
from Crypto.Util.Padding import pad

class SignUtil:
    _nonce_cache = {}
    _nonce_lock = threading.Lock()

    # 获取签名参数
    @staticmethod
    def get_sign_params(params: dict) -> dict:
        payload = dict(params or {})
        payload["app_id"] = os.getenv("APP_ID")
        payload["timestamp"] = int(time.time())
        payload["nonce"] = str(uuid.uuid4())
        return payload

    @staticmethod
    def get_sign_params_v2(params: dict, secret: Optional[str] = None) -> dict:
        payload = dict(params or {})
        app_id = os.getenv("APP_ID")
        if app_id:
            payload["app_id"] = app_id
        payload["sign_version"] = "v2"
        payload["timestamp"] = int(time.time())
        payload["nonce"] = str(uuid.uuid4())
        payload["sign"] = SignUtil.get_sign_v2(payload, secret)
        return payload

    # 生成clientId
    # 1. 读取环境变量中的密钥
    # 2. 用3DES加密方法，根据密钥生成clientId，生成的内容可逆向解析
    @staticmethod
    def generate_client_id(content: str) -> str:
        key = os.getenv("KEY", '1234567890abcdefghijklmn')
        cipher = DES3.new(key.encode('utf-8'), DES3.MODE_ECB)
        ciphertext = cipher.encrypt(pad(content.encode('utf-8'), DES3.block_size))
        return base64.b64encode(ciphertext).decode()

    # 解密clientId
    @staticmethod
    def decrypt_client_id(client_id: str) -> str:
        key = os.getenv("KEY", '1234567890abcdefghijklmn')
        cipher = DES3.new(key.encode('utf-8'), DES3.MODE_ECB)
        plaintext = cipher.decrypt(base64.b64decode(client_id))
        return plaintext.decode()
    
    # 生成clientSecret
    # 1. 用3DES加密方法，通过clientId为密钥，生成clientSecret
    @staticmethod
    def generate_client_secret(client_id: str) -> str:
        key = SignUtil.decrypt_client_id(client_id)
        # 截取key的前8位
        key = key[:16]
        cipher = DES3.new(key.encode('utf-8'), DES3.MODE_ECB)
        ciphertext = cipher.encrypt(pad(client_id.encode('utf-8'), DES3.block_size))
        return base64.b64encode(ciphertext).decode()

    # 获取签名
    @staticmethod
    def get_sign(params: dict) -> str:
        sign_str = ""
        client_secret = SignUtil.generate_client_secret(params["clientId"])

        for key, value in params.items():
            if key == "sign":
                continue
            sign_str += f"{key}={value}&"
        sign_str += f"clientSecret={client_secret}"
        return hashlib.md5(sign_str.encode()).hexdigest()

    @staticmethod
    def _canonical_value(value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def canonicalize_v2(params: dict) -> str:
        payload = dict(params or {})
        payload.pop("sign", None)
        return "&".join(
            f"{key}={SignUtil._canonical_value(payload[key])}"
            for key in sorted(payload.keys())
        )

    @staticmethod
    def get_sign_v2(params: dict, secret: Optional[str] = None) -> str:
        secret_value = secret or os.getenv("SPIDER_SIGN_SECRET", "")
        if not secret_value:
            raise ValueError("SPIDER_SIGN_SECRET is required for v2 signing")
        canonical = SignUtil.canonicalize_v2(params)
        return hmac.new(
            secret_value.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _timestamp_seconds(value: Any) -> Optional[int]:
        try:
            timestamp = int(float(value))
        except (TypeError, ValueError):
            return None
        if timestamp > 10_000_000_000:
            timestamp = int(timestamp / 1000)
        return timestamp

    @classmethod
    def _nonce_store_path(cls) -> Path:
        configured = str(os.getenv("SPIDER_SIGN_NONCE_STORE_PATH", "") or "").strip()
        if configured:
            return Path(configured)
        return Path(__file__).resolve().parents[3] / "data" / "spider_sign_nonce_cache.sqlite3"

    @classmethod
    def _open_nonce_store(cls) -> sqlite3.Connection:
        path = cls._nonce_store_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=1.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=1000")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS spider_sign_nonce (
                nonce_key TEXT PRIMARY KEY,
                expires_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_spider_sign_nonce_expires_at "
            "ON spider_sign_nonce(expires_at)"
        )
        return conn

    @classmethod
    def _prune_nonce_cache(cls, now: int) -> None:
        cls._nonce_cache = {
            key: expires_at
            for key, expires_at in cls._nonce_cache.items()
            if expires_at >= now
        }

    @classmethod
    def _remember_nonce(cls, nonce_key: str, now: int, ttl: int) -> bool:
        expires_at = now + ttl
        with cls._nonce_lock:
            cls._prune_nonce_cache(now)
            if nonce_key in cls._nonce_cache:
                return False

            try:
                with closing(cls._open_nonce_store()) as conn:
                    conn.execute("DELETE FROM spider_sign_nonce WHERE expires_at < ?", (now,))
                    result = conn.execute(
                        "INSERT OR IGNORE INTO spider_sign_nonce (nonce_key, expires_at) VALUES (?, ?)",
                        (nonce_key, expires_at),
                    )
                    if result.rowcount != 1:
                        return False
            except Exception as exc:
                logger.warning("Nonce store unavailable, falling back to in-memory replay protection: {}", exc)

            cls._nonce_cache[nonce_key] = expires_at
            return True

    @classmethod
    def clear_nonce_cache(cls):
        with cls._nonce_lock:
            cls._nonce_cache = {}

    @classmethod
    def clear_nonce_store(cls):
        with cls._nonce_lock:
            path = cls._nonce_store_path()
            for candidate in (
                path,
                Path(f"{path}-wal"),
                Path(f"{path}-shm"),
            ):
                try:
                    candidate.unlink()
                except FileNotFoundError:
                    continue
                except OSError:
                    continue

    @staticmethod
    def verify_sign_v2(
        params: dict,
        secret: Optional[str] = None,
        now: Optional[int] = None,
        max_skew_seconds: Optional[int] = None,
        check_replay: bool = True,
    ) -> bool:
        payload = dict(params or {})
        sign = str(payload.pop("sign", "") or "").strip()
        client_id = str(payload.get("clientId") or "").strip()
        nonce = str(payload.get("nonce") or "").strip()
        timestamp = SignUtil._timestamp_seconds(payload.get("timestamp"))
        if not sign or not client_id or not nonce or timestamp is None:
            return False

        now_seconds = int(now if now is not None else time.time())
        skew = int(max_skew_seconds if max_skew_seconds is not None else os.getenv("SPIDER_SIGN_MAX_SKEW_SECONDS", "300"))
        if abs(now_seconds - timestamp) > skew:
            return False

        expected_app_id = os.getenv("APP_ID", "")
        if expected_app_id and str(payload.get("app_id") or "") != expected_app_id:
            return False

        try:
            expected = SignUtil.get_sign_v2(payload, secret)
        except Exception:
            return False
        if not hmac.compare_digest(sign, expected):
            return False

        if check_replay and not SignUtil._remember_nonce(f"{client_id}:{nonce}", now_seconds, skew):
            return False
        return True

    # 验证签名
    @staticmethod
    def verify_sign(params: dict) -> bool:
        payload = dict(params or {})
        sign_version = str(
            payload.get("sign_version")
            or payload.get("signVersion")
            or payload.get("signature_version")
            or ""
        ).lower()
        if sign_version in {"2", "v2", "hmac-sha256"}:
            return SignUtil.verify_sign_v2(payload)
        sign = payload.pop("sign", None)
        if not sign:
            return False
        if "clientId" not in payload:
            return False
        try:
            return sign == SignUtil.get_sign(payload)
        except Exception:
            return False

    @staticmethod
    def verify_client_id(params) -> bool:
        client_id = str((params or {}).get("clientId") or "").strip()
        if not client_id:
            return False
        try:
            return bool(SignUtil.decrypt_client_id(client_id).strip())
        except Exception:
            return False

if __name__ == "__main__":
    params = {
        "clientId": "4UQUZJwwrY+BJCkiGDgUPA==",
        "timestamp": 1716230400,
        "nonce": "1234567890"
    }
    client_id = SignUtil.generate_client_id("牛哥密钥")
    print(client_id)
    print(SignUtil.generate_client_secret(client_id))

    print(SignUtil.get_sign(params))
    params["sign"] = SignUtil.get_sign(params)
    print(SignUtil.verify_sign(params))
