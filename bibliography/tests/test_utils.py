import os
import socket
from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase

from ..utils import (
    _NO_PROXIES,
    _REQUEST_HEADERS,
    _REQUEST_TIMEOUT,
    check_url,
    find_wayback_snapshot_for_year,
)


def _addrinfo(*addresses):
    return [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (a, 0))
        for a in addresses
    ]


def _resolve_public(host, *args, **kwargs):
    return _addrinfo("93.184.216.34")


@patch("bibliography.utils.socket.getaddrinfo", _resolve_public)
@patch("requests.get")
@patch("requests.head")
class SourceCheckUrlTestCase(SimpleTestCase):
    def setUp(self):
        self.url = "https://www.flyer-test-url.org"
        self.headers = _REQUEST_HEADERS

    def test_request_with_http_status_200_returns_true(self, mock_head, mock_get):
        mock_head.return_value.status_code = 200
        self.assertTrue(check_url(self.url))
        self.assertFalse(mock_get.called)
        mock_head.assert_called_once_with(
            self.url,
            headers=self.headers,
            allow_redirects=False,
            timeout=_REQUEST_TIMEOUT,
            proxies=_NO_PROXIES,
        )

    def test_request_with_http_status_404_falls_back_to_get(self, mock_head, mock_get):
        mock_head.return_value.status_code = 404
        mock_get.return_value.status_code = 200

        self.assertTrue(check_url(self.url))
        mock_get.assert_called_once_with(
            self.url,
            headers=self.headers,
            allow_redirects=False,
            timeout=_REQUEST_TIMEOUT,
            proxies=_NO_PROXIES,
            stream=True,
        )

    def test_returns_false_if_no_url_exists(self, mock_head, mock_get):
        self.assertFalse(check_url(None))
        self.assertFalse(mock_head.called)
        self.assertFalse(mock_get.called)

    def test_uses_get_method_if_head_returns_http_405(self, mock_head, mock_get):
        mock_head.return_value.status_code = 405
        mock_get.return_value.status_code = 200
        self.assertTrue(check_url(self.url))
        mock_get.assert_called_once_with(
            self.url,
            headers=self.headers,
            allow_redirects=False,
            timeout=_REQUEST_TIMEOUT,
            proxies=_NO_PROXIES,
            stream=True,
        )

    def test_uses_get_method_if_head_request_fails(self, mock_head, mock_get):
        mock_head.side_effect = requests.exceptions.RequestException("boom")
        mock_get.return_value.status_code = 200

        self.assertTrue(check_url(self.url))
        mock_get.assert_called_once_with(
            self.url,
            headers=self.headers,
            allow_redirects=False,
            timeout=_REQUEST_TIMEOUT,
            proxies=_NO_PROXIES,
            stream=True,
        )

    def test_returns_false_if_head_and_get_fail(self, mock_head, mock_get):
        mock_head.return_value.status_code = 403
        mock_get.side_effect = requests.exceptions.RequestException("boom")

        self.assertFalse(check_url(self.url))


def _redirect(location, status_code=302):
    response = MagicMock(status_code=status_code)
    response.headers = {"Location": location}
    return response


@patch("requests.get")
@patch("requests.head")
class SourceCheckUrlDestinationTestCase(SimpleTestCase):
    """Server-side URL checks must not reach internal services (SSRF)."""

    def _resolve(self, mapping):
        def resolve(host, *args, **kwargs):
            if host not in mapping:
                raise socket.gaierror("unknown host")
            return _addrinfo(*mapping[host])

        return patch("bibliography.utils.socket.getaddrinfo", side_effect=resolve)

    def test_rejects_loopback_and_private_ip_literals(self, mock_head, mock_get):
        for url in (
            "http://127.0.0.1/",
            "http://10.0.0.5/admin",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]:8000/",
            "http://0.0.0.0/",
        ):
            with self.subTest(url=url):
                self.assertFalse(check_url(url))
        self.assertFalse(mock_head.called)
        self.assertFalse(mock_get.called)

    def test_rejects_hostname_resolving_to_private_address(self, mock_head, mock_get):
        with self._resolve({"intranet.example.org": ["192.168.1.10"]}):
            self.assertFalse(check_url("https://intranet.example.org/"))
        self.assertFalse(mock_head.called)
        self.assertFalse(mock_get.called)

    def test_rejects_hostname_with_any_private_address(self, mock_head, mock_get):
        with self._resolve({"mixed.example.org": ["93.184.216.34", "10.1.2.3"]}):
            self.assertFalse(check_url("https://mixed.example.org/"))
        self.assertFalse(mock_head.called)

    def test_rejects_non_http_schemes(self, mock_head, mock_get):
        for url in ("ftp://example.org/file", "file:///etc/passwd", "gopher://x/"):
            with self.subTest(url=url):
                self.assertFalse(check_url(url))
        self.assertFalse(mock_head.called)
        self.assertFalse(mock_get.called)

    def test_does_not_follow_redirect_to_internal_address(self, mock_head, mock_get):
        mock_head.return_value = _redirect("http://169.254.169.254/latest/")
        mock_get.return_value = _redirect("http://169.254.169.254/latest/")
        with self._resolve({"example.org": ["93.184.216.34"]}):
            self.assertFalse(check_url("https://example.org/doc"))
        mock_head.assert_called_once()
        mock_get.assert_called_once()
        self.assertEqual(mock_head.call_args[0][0], "https://example.org/doc")

    def test_follows_redirect_to_public_address(self, mock_head, mock_get):
        mock_head.side_effect = [
            _redirect("/moved", status_code=301),
            MagicMock(status_code=200),
        ]
        with self._resolve({"example.org": ["93.184.216.34"]}):
            self.assertTrue(check_url("https://example.org/doc"))
        self.assertEqual(
            [c[0][0] for c in mock_head.call_args_list],
            ["https://example.org/doc", "https://example.org/moved"],
        )
        self.assertFalse(mock_get.called)

    def test_gives_up_after_too_many_redirects(self, mock_head, mock_get):
        mock_head.return_value = _redirect("https://example.org/loop")
        mock_get.return_value = _redirect("https://example.org/loop")
        with self._resolve({"example.org": ["93.184.216.34"]}):
            self.assertFalse(check_url("https://example.org/loop"))

    def test_malformed_redirect_location_is_invalid(self, mock_head, mock_get):
        mock_head.return_value = _redirect("http://[")
        mock_get.return_value = _redirect("http://[")
        with self._resolve({"example.org": ["93.184.216.34"]}):
            self.assertFalse(check_url("https://example.org/doc"))

    def test_unresolvable_host_is_invalid(self, mock_head, mock_get):
        with self._resolve({}):
            self.assertFalse(check_url("https://does-not-exist.invalid/"))
        self.assertFalse(mock_head.called)


class SourceCheckUrlProxyTestCase(SimpleTestCase):
    """A proxy would resolve hosts itself and bypass the destination check."""

    @patch("bibliography.utils.socket.getaddrinfo", _resolve_public)
    @patch("requests.adapters.HTTPAdapter.send")
    def test_ignores_environment_proxies(self, mock_send):
        response = requests.Response()
        response.status_code = 200
        response._content = b""
        mock_send.return_value = response
        env = {
            "HTTP_PROXY": "http://10.0.0.1:3128",
            "HTTPS_PROXY": "http://10.0.0.1:3128",
            "ALL_PROXY": "http://10.0.0.1:3128",
            "NO_PROXY": "",
        }
        with patch.dict(os.environ, env):
            self.assertTrue(check_url("https://example.org/doc"))
        proxies = mock_send.call_args.kwargs["proxies"]
        self.assertFalse(any(proxies.values()), proxies)


@patch("requests.get")
class FindWaybackSnapshotForYearTestCase(SimpleTestCase):
    def setUp(self):
        self.url = "https://example.com/flyer"

    def test_returns_latest_snapshot_in_requested_year(self, mock_get):
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = [
            ["timestamp", "original", "statuscode"],
            ["20210101120000", self.url, "200"],
            ["20211230153000", self.url, "200"],
            ["20210615101010", self.url, "200"],
        ]

        result = find_wayback_snapshot_for_year(self.url, 2021)

        self.assertEqual(
            result,
            "https://web.archive.org/web/20211230153000/https://example.com/flyer",
        )
        mock_get.assert_called_once_with(
            "https://web.archive.org/cdx/search/cdx",
            params={
                "url": self.url,
                "from": "20210101",
                "to": "20211231",
                "output": "json",
                "fl": "timestamp,original,statuscode",
                "filter": "statuscode:200",
            },
            headers=_REQUEST_HEADERS,
            timeout=10,
        )

    def test_returns_none_when_year_has_no_snapshots(self, mock_get):
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = [
            ["timestamp", "original", "statuscode"]
        ]

        result = find_wayback_snapshot_for_year(self.url, 2021)

        self.assertIsNone(result)
