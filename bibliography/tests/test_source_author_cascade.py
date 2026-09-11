from django.db.models.signals import post_save
from django.test import TestCase
from factory.django import mute_signals

from bibliography.models import Author, Source, SourceAuthor


class SourceAuthorReviewCascadeTest(TestCase):
    """Ensure Source review actions cascade to linked Authors."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        cls.django_user = User.objects.create_user(username="reviewer")

    def _make_source(self, status="private", title="Test Source"):
        with mute_signals(post_save):
            return Source.objects.create(title=title, publication_status=status)

    def _make_author(self, status="private", first="John", last="Doe"):
        with mute_signals(post_save):
            return Author.objects.create(
                first_names=first, last_names=last, publication_status=status
            )

    def _link(self, source, author, position=1):
        SourceAuthor.objects.create(source=source, author=author, position=position)

    def _run_cascade(self, source, action_name, user=None):
        """Invoke cascade_review_action the same way the view layer does."""
        source.cascade_review_action(
            action_name=action_name,
            actor=user or self.django_user,
            previous_status=None,
        )

    # -- submit_for_review -------------------------------------------------

    def test_submit_cascades_to_private_authors(self):
        source = self._make_source()
        author = self._make_author(status="private")
        self._link(source, author)

        self._run_cascade(source, "submit_for_review")

        author.refresh_from_db()
        self.assertEqual(author.publication_status, "review")

    def test_submit_cascades_to_declined_authors(self):
        source = self._make_source()
        author = self._make_author(status="declined")
        self._link(source, author)

        self._run_cascade(source, "submit_for_review")

        author.refresh_from_db()
        self.assertEqual(author.publication_status, "review")

    def test_submit_does_not_touch_published_authors(self):
        source = self._make_source()
        author = self._make_author(status="published")
        self._link(source, author)

        self._run_cascade(source, "submit_for_review")

        author.refresh_from_db()
        self.assertEqual(author.publication_status, "published")

    def test_submit_does_not_touch_review_authors(self):
        source = self._make_source()
        author = self._make_author(status="review")
        self._link(source, author)

        self._run_cascade(source, "submit_for_review")

        author.refresh_from_db()
        self.assertEqual(author.publication_status, "review")

    # -- approve -----------------------------------------------------------

    def test_approve_cascades_to_review_authors(self):
        source = self._make_source()
        author = self._make_author(status="review")
        self._link(source, author)

        self._run_cascade(source, "approve")

        author.refresh_from_db()
        self.assertEqual(author.publication_status, "published")
        self.assertEqual(author.approved_by, self.django_user)

    def test_approve_does_not_touch_private_authors(self):
        source = self._make_source()
        author = self._make_author(status="private")
        self._link(source, author)

        self._run_cascade(source, "approve")

        author.refresh_from_db()
        self.assertEqual(author.publication_status, "private")

    def test_approve_does_not_touch_published_authors(self):
        source = self._make_source()
        author = self._make_author(status="published")
        self._link(source, author)

        self._run_cascade(source, "approve")

        author.refresh_from_db()
        self.assertEqual(author.publication_status, "published")

    # -- withdraw_from_review ---------------------------------------------

    def test_withdraw_cascades_to_review_authors_when_no_other_source(self):
        source = self._make_source()
        author = self._make_author(status="review")
        self._link(source, author)

        self._run_cascade(source, "withdraw_from_review")

        author.refresh_from_db()
        self.assertEqual(author.publication_status, "private")

    def test_withdraw_does_not_cascade_when_other_source_in_review(self):
        source_a = self._make_source(title="A")
        source_b = self._make_source(status="review", title="B")
        author = self._make_author(status="review")
        self._link(source_a, author, position=1)
        self._link(source_b, author, position=1)

        self._run_cascade(source_a, "withdraw_from_review")

        author.refresh_from_db()
        self.assertEqual(author.publication_status, "review")

    def test_withdraw_does_not_cascade_when_other_source_published(self):
        source_a = self._make_source(title="A")
        source_b = self._make_source(status="published", title="B")
        author = self._make_author(status="review")
        self._link(source_a, author, position=1)
        self._link(source_b, author, position=1)

        self._run_cascade(source_a, "withdraw_from_review")

        author.refresh_from_db()
        self.assertEqual(author.publication_status, "review")

    def test_withdraw_does_not_touch_published_authors(self):
        source = self._make_source()
        author = self._make_author(status="published")
        self._link(source, author)

        self._run_cascade(source, "withdraw_from_review")

        author.refresh_from_db()
        self.assertEqual(author.publication_status, "published")

    # -- reject ------------------------------------------------------------

    def test_reject_cascades_to_review_authors_when_no_other_source(self):
        source = self._make_source()
        author = self._make_author(status="review")
        self._link(source, author)

        self._run_cascade(source, "reject")

        author.refresh_from_db()
        self.assertEqual(author.publication_status, "declined")

    def test_reject_does_not_cascade_when_other_source_in_review(self):
        source_a = self._make_source(title="A")
        source_b = self._make_source(status="review", title="B")
        author = self._make_author(status="review")
        self._link(source_a, author, position=1)
        self._link(source_b, author, position=1)

        self._run_cascade(source_a, "reject")

        author.refresh_from_db()
        self.assertEqual(author.publication_status, "review")

    def test_reject_does_not_touch_published_authors(self):
        source = self._make_source()
        author = self._make_author(status="published")
        self._link(source, author)

        self._run_cascade(source, "reject")

        author.refresh_from_db()
        self.assertEqual(author.publication_status, "published")

    # -- no authors --------------------------------------------------------

    def test_cascade_is_noop_when_no_authors(self):
        source = self._make_source()
        # Should not raise
        self._run_cascade(source, "submit_for_review")
        self._run_cascade(source, "approve")
        self._run_cascade(source, "withdraw_from_review")
        self._run_cascade(source, "reject")

    # -- multiple authors --------------------------------------------------

    def test_submit_cascades_to_multiple_authors(self):
        source = self._make_source()
        a1 = self._make_author(status="private", first="A", last="One")
        a2 = self._make_author(status="declined", first="B", last="Two")
        a3 = self._make_author(status="published", first="C", last="Three")
        self._link(source, a1, position=1)
        self._link(source, a2, position=2)
        self._link(source, a3, position=3)

        self._run_cascade(source, "submit_for_review")

        a1.refresh_from_db()
        a2.refresh_from_db()
        a3.refresh_from_db()
        self.assertEqual(a1.publication_status, "review")
        self.assertEqual(a2.publication_status, "review")
        self.assertEqual(a3.publication_status, "published")

    def test_approve_cascades_to_multiple_review_authors(self):
        source = self._make_source()
        a1 = self._make_author(status="review", first="A", last="One")
        a2 = self._make_author(status="review", first="B", last="Two")
        a3 = self._make_author(status="private", first="C", last="Three")
        self._link(source, a1, position=1)
        self._link(source, a2, position=2)
        self._link(source, a3, position=3)

        self._run_cascade(source, "approve")

        a1.refresh_from_db()
        a2.refresh_from_db()
        a3.refresh_from_db()
        self.assertEqual(a1.publication_status, "published")
        self.assertEqual(a2.publication_status, "published")
        self.assertEqual(a3.publication_status, "private")


class SourceAffectedAuthorCountTest(TestCase):
    """Tests for Source.affected_author_count() used by the UI."""

    def _make_source(self, status="private", title="Test Source"):
        with mute_signals(post_save):
            return Source.objects.create(title=title, publication_status=status)

    def _make_author(self, status="private", first="John", last="Doe"):
        with mute_signals(post_save):
            return Author.objects.create(
                first_names=first, last_names=last, publication_status=status
            )

    def _link(self, source, author, position=1):
        SourceAuthor.objects.create(source=source, author=author, position=position)

    def test_count_for_submit_includes_private_and_declined(self):
        source = self._make_source()
        a1 = self._make_author(status="private", first="A", last="One")
        a2 = self._make_author(status="declined", first="B", last="Two")
        a3 = self._make_author(status="published", first="C", last="Three")
        a4 = self._make_author(status="review", first="D", last="Four")
        self._link(source, a1, position=1)
        self._link(source, a2, position=2)
        self._link(source, a3, position=3)
        self._link(source, a4, position=4)

        self.assertEqual(source.affected_author_count("submit_for_review"), 2)

    def test_count_for_approve_includes_review_only(self):
        source = self._make_source()
        a1 = self._make_author(status="review", first="A", last="One")
        a2 = self._make_author(status="review", first="B", last="Two")
        a3 = self._make_author(status="private", first="C", last="Three")
        a4 = self._make_author(status="published", first="D", last="Four")
        self._link(source, a1, position=1)
        self._link(source, a2, position=2)
        self._link(source, a3, position=3)
        self._link(source, a4, position=4)

        self.assertEqual(source.affected_author_count("approve"), 2)

    def test_count_returns_zero_for_no_authors(self):
        source = self._make_source()
        self.assertEqual(source.affected_author_count("submit_for_review"), 0)
        self.assertEqual(source.affected_author_count("approve"), 0)

    def test_count_returns_zero_for_unsupported_action(self):
        source = self._make_source()
        a1 = self._make_author(status="review", first="A", last="One")
        self._link(source, a1, position=1)
        self.assertEqual(source.affected_author_count("withdraw_from_review"), 0)
        self.assertEqual(source.affected_author_count("reject"), 0)
