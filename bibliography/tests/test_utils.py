from unittest.mock import patch

import requests
from django.test import SimpleTestCase

from ..utils import (
    _REQUEST_HEADERS,
    _REQUEST_TIMEOUT,
    check_url,
    find_wayback_snapshot_for_year,
)


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
