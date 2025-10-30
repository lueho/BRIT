from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from utils.object_management.models import ReviewAction
from utils.object_management.redirects import ReviewActionRedirectResolver


class ReviewActionRedirectResolverTests(SimpleTestCase):
    def setUp(self):
        self.request = Mock()
        self.request.user = Mock()
        self.obj = Mock()
        self.obj.get_absolute_url.return_value = "/objects/1/"
        self.resolver = ReviewActionRedirectResolver(self.request, self.obj)

    def test_resolve_withdraw_redirect_without_next_url_returns_default(self):
        default_url = "/objects/1/"

        result = self.resolver.resolve_withdraw_redirect(None, default_url)

        self.assertEqual(result, default_url)

    @patch(
        "utils.object_management.redirects.ReviewActionRedirectResolver._get_review_detail_path"
    )
    @patch("utils.object_management.redirects.get_object_policy")
    def test_resolve_withdraw_redirect_returns_next_url_when_policy_allows_review(
        self, mock_get_policy, mock_review_path
    ):
        mock_get_policy.return_value = {
            "is_owner": True,
            "is_in_review": True,
            "is_declined": False,
        }
        mock_review_path.return_value = "/review/1/"
        next_url = "https://example.com/review/1/?tab=review"

        result = self.resolver.resolve_withdraw_redirect(next_url, "/objects/1/")

        self.assertEqual(result, next_url)

    @patch(
        "utils.object_management.redirects.ReviewActionRedirectResolver._get_review_detail_path"
    )
    @patch("utils.object_management.redirects.get_object_policy")
    def test_resolve_withdraw_redirect_keeps_next_url_for_non_owner(
        self, mock_get_policy, mock_review_path
    ):
        mock_get_policy.return_value = {
            "is_owner": False,
            "is_in_review": False,
            "is_declined": False,
        }
        mock_review_path.return_value = "/review/1/"
        next_url = "https://example.com/review/1/"

        result = self.resolver.resolve_withdraw_redirect(next_url, "/objects/1/")

        self.assertEqual(result, next_url)

    @patch(
        "utils.object_management.redirects.ReviewActionRedirectResolver.resolve_withdraw_redirect"
    )
    def test_resolve_action_redirect_delegates_to_withdraw_handler(
        self, mock_withdraw_redirect
    ):
        mock_withdraw_redirect.return_value = "/objects/1/"

        result = self.resolver.resolve_action_redirect(
            ReviewAction.ACTION_WITHDRAWN, "/next/", "/default/"
        )

        mock_withdraw_redirect.assert_called_once_with("/next/", "/default/")
        self.assertEqual(result, "/objects/1/")

    def test_resolve_action_redirect_defaults_to_next_url_for_other_actions(self):
        result = self.resolver.resolve_action_redirect(
            ReviewAction.ACTION_APPROVED, "/next/", "/default/"
        )

        self.assertEqual(result, "/next/")

    def test_resolve_action_redirect_defaults_to_object_url_when_no_next(self):
        result = self.resolver.resolve_action_redirect(
            ReviewAction.ACTION_APPROVED, None, "/default/"
        )

        self.assertEqual(result, "/default/")

    def test_resolve_action_redirect_returns_default_when_handler_missing(self):
        result = self.resolver.resolve_action_redirect("unknown", "/next/", "/default/")

        self.assertEqual(result, "/next/")

    def test_resolve_action_redirect_uses_custom_handler_callable(self):
        def custom_handler(next_url, default_url):
            return "custom"

        resolver = ReviewActionRedirectResolver(
            self.request, self.obj, action_handlers={"custom": custom_handler}
        )

        self.assertEqual(
            resolver.resolve_action_redirect("custom", "/next/", "/default/"),
            "custom",
        )

    def test_resolve_action_redirect_uses_custom_handler_attribute(self):
        resolver = ReviewActionRedirectResolver(
            self.request,
            self.obj,
            action_handlers={"custom": "resolve_withdraw_redirect"},
        )

        with patch.object(
            resolver, "resolve_withdraw_redirect", return_value="from_attr"
        ) as mock_handler:
            result = resolver.resolve_action_redirect("custom", "/next/", "/default/")

        mock_handler.assert_called_once_with("/next/", "/default/")
        self.assertEqual(result, "from_attr")

    def test_resolve_action_redirect_raises_for_unknown_handler_attribute(self):
        resolver = ReviewActionRedirectResolver(
            self.request,
            self.obj,
            action_handlers={"custom": "missing_handler"},
        )

        with self.assertRaises(AttributeError):
            resolver.resolve_action_redirect("custom", "/next/", "/default/")

    @patch(
        "utils.object_management.redirects.ReviewActionRedirectResolver._get_review_detail_path"
    )
    @patch("utils.object_management.redirects.get_object_policy")
    def test_resolve_withdraw_redirect_redirects_owner_away_from_review_detail(
        self, mock_get_policy, mock_review_path
    ):
        mock_get_policy.return_value = {
            "is_owner": True,
            "is_in_review": False,
            "is_declined": False,
        }
        mock_review_path.return_value = "/review/1/"
        next_url = "https://example.com/review/1/?tab=review"

        result = self.resolver.resolve_withdraw_redirect(next_url, "/default/")

        self.assertEqual(result, "/objects/1/")

    @patch("utils.object_management.redirects.get_object_policy")
    def test_resolve_withdraw_redirect_returns_next_url_on_policy_error(
        self, mock_get_policy
    ):
        mock_get_policy.side_effect = RuntimeError("policy failed")
        next_url = "https://example.com/review/1/"

        with patch.object(
            ReviewActionRedirectResolver,
            "_get_review_detail_path",
            return_value="/review/1/",
        ):
            result = self.resolver.resolve_withdraw_redirect(next_url, "/default/")

        self.assertEqual(result, next_url)

    def test_custom_handlers_do_not_mutate_default_mapping(self):
        ReviewActionRedirectResolver(
            self.request,
            self.obj,
            action_handlers={"custom": lambda *_: "custom"},
        )

        new_resolver = ReviewActionRedirectResolver(self.request, self.obj)

        self.assertIn(
            ReviewAction.ACTION_WITHDRAWN,
            new_resolver.action_handlers,
        )
