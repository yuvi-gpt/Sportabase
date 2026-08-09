import sys
import unittest

from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app import main


class SafeArticleUrlTests(unittest.TestCase):
    def test_public_https_url_is_allowed(self):
        with patch.object(
            main.socket,
            "getaddrinfo",
            return_value=[
                (
                    main.socket.AF_INET,
                    main.socket.SOCK_STREAM,
                    6,
                    "",
                    ("93.184.216.34", 443),
                )
            ],
        ):
            result = main.validate_safe_remote_url(
                "https://example.com/sports/story"
            )

        self.assertEqual(
            result,
            "https://example.com/sports/story",
        )

    def test_localhost_is_blocked(self):
        with self.assertRaises(ValueError):
            main.validate_safe_remote_url(
                "http://localhost:8000/private"
            )

    def test_loopback_ip_is_blocked(self):
        with self.assertRaises(ValueError):
            main.validate_safe_remote_url(
                "http://127.0.0.1/private"
            )

    def test_private_ip_is_blocked(self):
        with self.assertRaises(ValueError):
            main.validate_safe_remote_url(
                "http://192.168.1.20/private"
            )

    def test_link_local_ip_is_blocked(self):
        with self.assertRaises(ValueError):
            main.validate_safe_remote_url(
                "http://169.254.169.254/latest/meta-data"
            )

    def test_hostname_resolving_to_private_ip_is_blocked(self):
        with patch.object(
            main.socket,
            "getaddrinfo",
            return_value=[
                (
                    main.socket.AF_INET,
                    main.socket.SOCK_STREAM,
                    6,
                    "",
                    ("10.0.0.8", 443),
                )
            ],
        ):
            with self.assertRaises(ValueError):
                main.validate_safe_remote_url(
                    "https://example.com/story"
                )

    def test_credentials_in_url_are_blocked(self):
        with self.assertRaises(ValueError):
            main.validate_safe_remote_url(
                "https://user:password@example.com/story"
            )

    def test_non_http_protocol_is_blocked(self):
        with self.assertRaises(ValueError):
            main.validate_safe_remote_url(
                "file:///etc/passwd"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
