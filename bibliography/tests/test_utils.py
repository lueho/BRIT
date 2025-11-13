from unittest.mock import patch

from django.test import SimpleTestCase

from ..utils import check_url


@patch("requests.get")
@patch("requests.head")
class SourceCheckUrlTestCase(SimpleTestCase):
    def setUp(self):
        self.url = "https://www.flyer-test-url.org"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:84.0) Gecko/20200101 Firefox/84.0",
            "Accept-Language": "en-GB,en;q=0.5",
            "Referer": "https://www.wikipedia.org",
            "DNT": "1",
        }

    def test_request_with_http_status_200_returns_true(self, mock_head, mock_get):
        mock_head.return_value.status_code = 200
        self.assertTrue(check_url(self.url))
        self.assertFalse(mock_get.called)

    def test_request_with_http_status_404_returns_false(self, mock_head, mock_get):
        mock_head.return_value.status_code = 404
        self.assertFalse(check_url(self.url))
        self.assertFalse(mock_get.called)

    def test_returns_false_if_no_url_exists(self, mock_head, mock_get):
        self.assertFalse(check_url(None))
        self.assertFalse(mock_get.called)

    def test_uses_get_method_if_head_returns_http_405(self, mock_head, mock_get):
        mock_head.return_value.status_code = 405
        mock_get.return_value.status_code = 200
        self.assertTrue(check_url(self.url))
        mock_get.assert_called_once_with(
            self.url, headers=self.headers, allow_redirects=True
        )
