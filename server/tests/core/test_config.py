import unittest

from server.app.core.config import Settings


class ConfigTests(unittest.TestCase):
    def test_cors_origins_strip_wildcard_and_keep_explicit_hosts(self):
        settings = Settings(
            CORS_ORIGINS="*, https://admin.example.com , http://localhost:3000, *",
        )

        self.assertEqual(
            settings.get_cors_origins(),
            ["https://admin.example.com", "http://localhost:3000"],
        )

    def test_cors_origins_fall_back_when_only_wildcard_is_configured(self):
        settings = Settings(CORS_ORIGINS="*")

        self.assertEqual(settings.get_cors_origins(), ["https://tianji.fangpian999.com"])

    def test_cors_credentials_default_is_disabled(self):
        fields = getattr(Settings, "model_fields", None) or getattr(Settings, "__fields__", {})
        self.assertFalse(fields["CORS_ALLOW_CREDENTIALS"].default)


if __name__ == "__main__":
    unittest.main()
