from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from ..helpers import create_review_action
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
