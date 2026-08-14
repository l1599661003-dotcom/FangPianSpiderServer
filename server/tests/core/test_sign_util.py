import importlib
import hashlib
import hmac
import os
import sys
import types
import uuid
import tempfile
from pathlib import Path
import unittest
from unittest import mock


def _install_fake_crypto():
    if "Crypto" in sys.modules:
        return

    crypto_module = types.ModuleType("Crypto")
    cipher_module = types.ModuleType("Crypto.Cipher")
    util_module = types.ModuleType("Crypto.Util")
    padding_module = types.ModuleType("Crypto.Util.Padding")

    class FakeCipher:
        def encrypt(self, data):
            return data

        def decrypt(self, data):
            return data

    class FakeDES3:
        MODE_ECB = object()

        @staticmethod
        def new(key, mode):
            return FakeCipher()

    def fake_pad(data, block_size):
        return data

    cipher_module.DES3 = FakeDES3
    padding_module.pad = fake_pad
    util_module.Padding = padding_module
    crypto_module.Cipher = cipher_module
    crypto_module.Util = util_module

    sys.modules["Crypto"] = crypto_module
    sys.modules["Crypto.Cipher"] = cipher_module
    sys.modules["Crypto.Util"] = util_module
    sys.modules["Crypto.Util.Padding"] = padding_module


_install_fake_crypto()
SignUtil = importlib.import_module("server.app.core.sign_util").SignUtil


class SignUtilTests(unittest.TestCase):
    def setUp(self):
        self._nonce_tmp = tempfile.TemporaryDirectory()
        self._nonce_env = mock.patch.dict(
            os.environ,
            {"SPIDER_SIGN_NONCE_STORE_PATH": str(Path(self._nonce_tmp.name) / "nonce.sqlite3")},
            clear=False,
        )
        self._nonce_env.start()
        SignUtil.clear_nonce_cache()
        SignUtil.clear_nonce_store()

    def tearDown(self):
        self._nonce_env.stop()
        self._nonce_tmp.cleanup()

    def test_verify_sign_does_not_mutate_input(self):
        payload = {"clientId": "client-1", "foo": "bar", "sign": "expected"}
        snapshot = dict(payload)

        with mock.patch.object(SignUtil, "get_sign", return_value="expected") as mocked:
            self.assertTrue(SignUtil.verify_sign(payload))

        self.assertEqual(payload, snapshot)
        mocked.assert_called_once_with({"clientId": "client-1", "foo": "bar"})

    def test_verify_client_id_requires_decryptable_value(self):
        with mock.patch.object(SignUtil, "decrypt_client_id", return_value="valid-client"):
            self.assertTrue(SignUtil.verify_client_id({"clientId": "encoded-value"}))

        with mock.patch.object(SignUtil, "decrypt_client_id", side_effect=ValueError("bad")):
            self.assertFalse(SignUtil.verify_client_id({"clientId": "encoded-value"}))

        self.assertFalse(SignUtil.verify_client_id({}))

    def test_canonicalize_v2_sorts_and_stabilizes_values(self):
        payload = {
            "clientId": "client-1",
            "timestamp": 1700000000,
            "nonce": "nonce-1",
            "active": True,
            "nested": {"z": 1, "a": 2},
            "sign_version": "v2",
        }

        self.assertEqual(
            SignUtil.canonicalize_v2(payload),
            'active=true&clientId=client-1&nested={"a":2,"z":1}&nonce=nonce-1&sign_version=v2&timestamp=1700000000',
        )

    def test_get_sign_v2_uses_hmac_sha256(self):
        payload = {
            "clientId": "client-1",
            "timestamp": 1700000000,
            "nonce": "nonce-2",
            "sign_version": "v2",
        }
        canonical = SignUtil.canonicalize_v2(payload)
        expected = hmac.new(b"secret", canonical.encode("utf-8"), hashlib.sha256).hexdigest()

        self.assertEqual(SignUtil.get_sign_v2(payload, "secret"), expected)

    def test_get_sign_params_v2_returns_signed_copy(self):
        payload = {"clientId": "client-1"}
        snapshot = dict(payload)

        with mock.patch.dict(os.environ, {"APP_ID": "spider-app"}):
            with mock.patch("server.app.core.sign_util.time.time", return_value=1700000000):
                with mock.patch(
                    "server.app.core.sign_util.uuid.uuid4",
                    return_value=uuid.UUID("00000000-0000-0000-0000-000000000123"),
                ):
                    result = SignUtil.get_sign_params_v2(payload, "secret")

        self.assertEqual(payload, snapshot)
        self.assertEqual(result["app_id"], "spider-app")
        self.assertEqual(result["sign_version"], "v2")
        self.assertEqual(result["timestamp"], 1700000000)
        self.assertEqual(result["nonce"], "00000000-0000-0000-0000-000000000123")
        sign = result["sign"]
        signed_payload = dict(result)
        signed_payload.pop("sign")
        self.assertEqual(sign, SignUtil.get_sign_v2(signed_payload, "secret"))

    def test_verify_sign_v2_rejects_replay(self):
        now = 1700000000
        payload = {
            "clientId": "client-1",
            "timestamp": now,
            "nonce": "nonce-3",
            "sign_version": "v2",
        }
        payload["sign"] = SignUtil.get_sign_v2(payload, "secret")

        self.assertTrue(SignUtil.verify_sign_v2(payload, secret="secret", now=now))
        self.assertFalse(SignUtil.verify_sign_v2(payload, secret="secret", now=now))

    def test_verify_sign_v2_rejects_replay_after_memory_cache_clear(self):
        now = 1700000000
        payload = {
            "clientId": "client-1",
            "timestamp": now,
            "nonce": "nonce-4b",
            "sign_version": "v2",
        }
        payload["sign"] = SignUtil.get_sign_v2(payload, "secret")

        self.assertTrue(SignUtil.verify_sign_v2(payload, secret="secret", now=now))
        SignUtil.clear_nonce_cache()
        self.assertFalse(SignUtil.verify_sign_v2(payload, secret="secret", now=now))

    def test_verify_sign_v2_rejects_expired_timestamp(self):
        now = 1700000000
        payload = {
            "clientId": "client-1",
            "timestamp": now - 301,
            "nonce": "nonce-4",
            "sign_version": "v2",
        }
        payload["sign"] = SignUtil.get_sign_v2(payload, "secret")

        self.assertFalse(
            SignUtil.verify_sign_v2(
                payload,
                secret="secret",
                now=now,
                max_skew_seconds=300,
                check_replay=False,
            )
        )

    def test_verify_sign_routes_v2_without_mutating_input(self):
        now = 1700000000
        payload = {
            "app_id": "spider-app",
            "clientId": "client-1",
            "timestamp": now,
            "nonce": "nonce-5",
            "sign_version": "v2",
        }
        payload["sign"] = SignUtil.get_sign_v2(payload, "secret")
        snapshot = dict(payload)

        with mock.patch.dict(os.environ, {"SPIDER_SIGN_SECRET": "secret", "APP_ID": "spider-app"}):
            with mock.patch("server.app.core.sign_util.time.time", return_value=now):
                self.assertTrue(SignUtil.verify_sign(payload))

        self.assertEqual(payload, snapshot)


if __name__ == "__main__":
    unittest.main()
