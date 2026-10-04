from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from ..helpers import (
    create_review_action,
    create_review_action_safely,
    invoke_cascade_handler,
)
from ..models import ReviewAction


class CreateReviewActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="reviewer")
        cls.obj = User.objects.create_user(username="target")

    def test_creates_review_action_for_object(self):
        action = create_review_action(
            self.obj, self.user, ReviewAction.ACTION_COMMENT, "Looks good"
        )

        self.assertEqual(action.content_type, ContentType.objects.get_for_model(User))
        self.assertEqual(action.object_id, self.obj.pk)
        self.assertEqual(action.user, self.user)
        self.assertEqual(action.action, ReviewAction.ACTION_COMMENT)
        self.assertEqual(action.comment, "Looks good")

    def test_safely_returns_created_action(self):
        action = create_review_action_safely(
            self.obj, self.user, ReviewAction.ACTION_COMMENT
        )

        self.assertIsNotNone(action)
        self.assertEqual(action.comment, "")

    def test_safely_swallows_errors_and_logs(self):
        with (
            patch.object(ReviewAction.objects, "create", side_effect=Exception("boom")),
            self.assertLogs("utils.object_management.helpers", level="WARNING") as logs,
        ):
            result = create_review_action_safely(
                self.obj, self.user, ReviewAction.ACTION_COMMENT
            )

        self.assertIsNone(result)
        self.assertIn("Failed to create ReviewAction", logs.output[0])


class InvokeCascadeHandlerTests(TestCase):
    def test_invokes_handler_with_action_details(self):
        handler = Mock()
        obj = Mock(spec=["cascade_review_action"], cascade_review_action=handler)

        invoke_cascade_handler(obj, "approve", actor="user", previous_status="review")

        handler.assert_called_once_with(
            action_name="approve", actor="user", previous_status="review"
        )

    def test_noop_without_callable_handler(self):
        invoke_cascade_handler(object(), "approve", actor="user")
        invoke_cascade_handler(
            Mock(spec=["cascade_review_action"], cascade_review_action="not callable"),
            "approve",
            actor="user",
        )

    def test_swallows_handler_errors_and_logs(self):
        handler = Mock(side_effect=Exception("boom"))
        obj = Mock(spec=["cascade_review_action"], cascade_review_action=handler)

        with self.assertLogs(
            "utils.object_management.helpers", level="WARNING"
        ) as logs:
            invoke_cascade_handler(obj, "approve", actor="user")

        self.assertIn("Review action cascade failed", logs.output[0])
