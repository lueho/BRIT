import os
import socket
from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase

from ..utils import (
    _MAX_REDIRECTS,
    _REQUEST_HEADERS,
    _REQUEST_TIMEOUT,
    _PublicOnlyHTTPConnection,
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


def _resolver(mapping):
    def resolve(host, *args, **kwargs):
        if host not in mapping:
            raise socket.gaierror("unknown host")
        return _addrinfo(*mapping[host])

    return resolve


def _response(request, status_code=200, location=None):
    response = requests.Response()
    response.status_code = status_code
    response.url = request.url
    response.request = request
    response._content = b""
    response._content_consumed = True
    if location is not None:
        response.headers["Location"] = location
    return response


@patch("bibliography.utils.socket.getaddrinfo", _resolve_public)
@patch("requests.Session.get")
@patch("requests.Session.head")
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
            allow_redirects=True,
            timeout=_REQUEST_TIMEOUT,
        )

    def test_request_with_http_status_404_falls_back_to_get(self, mock_head, mock_get):
        mock_head.return_value.status_code = 404
        mock_get.return_value.status_code = 200

        self.assertTrue(check_url(self.url))
        mock_get.assert_called_once_with(
            self.url,
            headers=self.headers,
            allow_redirects=True,
            timeout=_REQUEST_TIMEOUT,
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
            allow_redirects=True,
            timeout=_REQUEST_TIMEOUT,
            stream=True,
        )

    def test_uses_get_method_if_head_request_fails(self, mock_head, mock_get):
        mock_head.side_effect = requests.exceptions.RequestException("boom")
        mock_get.return_value.status_code = 200

        self.assertTrue(check_url(self.url))
        mock_get.assert_called_once_with(
            self.url,
            headers=self.headers,
            allow_redirects=True,
            timeout=_REQUEST_TIMEOUT,
            stream=True,
        )

    def test_returns_false_if_head_and_get_fail(self, mock_head, mock_get):
        mock_head.return_value.status_code = 403
        mock_get.side_effect = requests.exceptions.RequestException("boom")

        self.assertFalse(check_url(self.url))


@patch("requests.Session.get")
@patch("requests.Session.head")
class SourceCheckUrlDestinationTestCase(SimpleTestCase):
    """Server-side URL checks must not reach internal services (SSRF)."""

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
        resolve = _resolver({"intranet.example.org": ["192.168.1.10"]})
        with patch("bibliography.utils.socket.getaddrinfo", side_effect=resolve):
            self.assertFalse(check_url("https://intranet.example.org/"))
        self.assertFalse(mock_head.called)
        self.assertFalse(mock_get.called)

    def test_rejects_hostname_with_any_private_address(self, mock_head, mock_get):
        resolve = _resolver({"mixed.example.org": ["93.184.216.34", "10.1.2.3"]})
        with patch("bibliography.utils.socket.getaddrinfo", side_effect=resolve):
            self.assertFalse(check_url("https://mixed.example.org/"))
        self.assertFalse(mock_head.called)

    def test_rejects_non_http_schemes(self, mock_head, mock_get):
        for url in ("ftp://example.org/file", "file:///etc/passwd", "gopher://x/"):
            with self.subTest(url=url):
                self.assertFalse(check_url(url))
        self.assertFalse(mock_head.called)
        self.assertFalse(mock_get.called)

    def test_unresolvable_host_is_invalid(self, mock_head, mock_get):
        with patch("bibliography.utils.socket.getaddrinfo", side_effect=_resolver({})):
            self.assertFalse(check_url("https://does-not-exist.invalid/"))
        self.assertFalse(mock_head.called)


@patch(
    "bibliography.utils.socket.getaddrinfo",
    side_effect=_resolver({"example.org": ["93.184.216.34"]}),
)
@patch("requests.adapters.HTTPAdapter.send")
class SourceCheckUrlRedirectTestCase(SimpleTestCase):
    """Redirects are followed by requests, but only to public destinations."""

    def _serve(self, mock_send, routes):
        def send(request, **kwargs):
            return _response(request, *routes[request.url])

        mock_send.side_effect = send

    def _sent_urls(self, mock_send):
        return [c.args[0].url for c in mock_send.call_args_list]

    def test_does_not_follow_redirect_to_internal_address(self, mock_send, _):
        self._serve(
            mock_send,
            {"https://example.org/doc": (302, "http://169.254.169.254/latest/")},
        )
        self.assertFalse(check_url("https://example.org/doc"))
        self.assertNotIn("http://169.254.169.254/latest/", self._sent_urls(mock_send))

    def test_follows_redirect_to_public_address(self, mock_send, _):
        self._serve(
            mock_send,
            {
                "https://example.org/doc": (301, "/moved"),
                "https://example.org/moved": (200,),
            },
        )
        self.assertTrue(check_url("https://example.org/doc"))
        self.assertEqual(
            self._sent_urls(mock_send),
            ["https://example.org/doc", "https://example.org/moved"],
        )

    def test_malformed_redirect_location_is_invalid(self, mock_send, _):
        self._serve(mock_send, {"https://example.org/doc": (302, "http://[")})
        self.assertFalse(check_url("https://example.org/doc"))

    def test_undecodable_redirect_location_is_invalid(self, mock_send, _):
        self._serve(mock_send, {"https://example.org/doc": (302, "/\xff")})
        self.assertFalse(check_url("https://example.org/doc"))

    def test_gives_up_after_too_many_redirects(self, mock_send, _):
        self._serve(mock_send, {"https://example.org/loop": (302, "/loop")})
        self.assertFalse(check_url("https://example.org/loop"))
        # HEAD and the GET fallback each stop at the redirect limit.
        self.assertLessEqual(mock_send.call_count, 2 * (_MAX_REDIRECTS + 1))


@patch("bibliography.utils.socket.getaddrinfo", _resolve_public)
@patch("urllib3.util.connection.create_connection")
class SourceCheckUrlDnsRebindingTestCase(SimpleTestCase):
    """The connected peer is re-checked, so a host re-resolving privately fails."""

    def _socket(self, peer):
        sock = MagicMock()
        sock.getpeername.return_value = (peer, 80)
        return sock

    def test_refuses_connection_when_peer_is_private(self, mock_connect):
        sock = self._socket("127.0.0.1")
        mock_connect.return_value = sock
        self.assertFalse(check_url("http://rebind.example.org/"))
        sock.close.assert_called()
        sock.sendall.assert_not_called()
        sock.send.assert_not_called()

    def test_allows_connection_when_peer_is_public(self, mock_connect):
        sock = self._socket("93.184.216.34")
        mock_connect.return_value = sock
        conn = _PublicOnlyHTTPConnection("example.org", 80)
        self.assertIs(conn._new_conn(), sock)
        sock.close.assert_not_called()


class SourceCheckUrlProxyTestCase(SimpleTestCase):
    """A proxy would resolve hosts itself and bypass the destination check."""

    @patch("bibliography.utils.socket.getaddrinfo", _resolve_public)
    @patch("requests.adapters.HTTPAdapter.send")
    def test_ignores_environment_proxies(self, mock_send):
        mock_send.side_effect = lambda request, **kwargs: _response(request)
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
