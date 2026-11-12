"""Source/Author review independence and citation integrity.

Authors linked to a Source are independent reviewable records: Source
lifecycle transitions must not mutate their state or audit history, and the
citation link remains an ordered, readable surface.
"""

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.test import TestCase
from factory.django import mute_signals

from bibliography.models import Author, Source, SourceAuthor
from utils.object_management.models import ReviewAction
from utils.object_management.services import perform_transition


def _perm(model, codename):
    return Permission.objects.get(
        codename=codename, content_type=ContentType.objects.get_for_model(model)
    )


def _actions_for(obj):
    return ReviewAction.objects.filter(
        content_type=ContentType.objects.get_for_model(obj.__class__),
        object_id=obj.pk,
    )


class SourceAuthorReviewCascadeTest(TestCase):
    """A Source's review actions must not cascade to linked Authors."""

    def setUp(self):
        self.owner = User.objects.create_user(username="cascade-owner")
        self.moderator = User.objects.create_user(username="cascade-moderator")
        self.moderator.user_permissions.add(_perm(Source, "can_moderate_source"))

    def _make_source(self, status="private", title="Test Source", owner=None):
        with mute_signals(post_save):
            return Source.objects.create(
                title=title,
                owner=owner or self.owner,
                publication_status=status,
            )

    def _make_author(self, status="private", first="John", last="Doe", owner=None):
        with mute_signals(post_save):
            return Author.objects.create(
                first_names=first,
                last_names=last,
                owner=owner or self.owner,
                publication_status=status,
            )

    def _link(self, source, author, position=1):
        SourceAuthor.objects.create(source=source, author=author, position=position)

    def _assert_authors_untouched(self, authors):
        for author, expected_status in authors:
            author.refresh_from_db()
            self.assertEqual(author.publication_status, expected_status)
            self.assertFalse(_actions_for(author).exists())

    def _submit(self, source):
        perform_transition(self.owner, source, "submit")
        source.refresh_from_db()

    def _approve(self, source):
        perform_transition(
            self.moderator,
            source,
            "approve",
            expected_revision=source.content_revision,
        )
        source.refresh_from_db()

    def _reject(self, source):
        perform_transition(self.moderator, source, "reject")
        source.refresh_from_db()

    def _withdraw(self, source):
        perform_transition(self.owner, source, "withdraw")
        source.refresh_from_db()

    def test_submit_does_not_touch_linked_authors(self):
        source = self._make_source()
        authors = [
            (self._make_author(status="private"), "private"),
            (self._make_author(status="declined", first="A", last="One"), "declined"),
            (self._make_author(status="review", first="B", last="Two"), "review"),
            (
                self._make_author(status="published", first="C", last="Three"),
                "published",
            ),
        ]
        for position, (author, _) in enumerate(authors, start=1):
            self._link(source, author, position=position)
        self._submit(source)
        self.assertEqual(source.publication_status, "review")
        self._assert_authors_untouched(authors)

    def test_approve_does_not_touch_linked_authors(self):
        source = self._make_source(status="review")
        authors = [
            (self._make_author(status="private"), "private"),
            (self._make_author(status="review", first="B", last="Two"), "review"),
            (
                self._make_author(status="published", first="C", last="Three"),
                "published",
            ),
        ]
        for position, (author, _) in enumerate(authors, start=1):
            self._link(source, author, position=position)
        # Records saved directly with a published status carry owner approval
        # metadata; the source's approve must leave each author's approver as-is.
        expected_approvers = {author.pk: author.approved_by_id for author, _ in authors}
        self._approve(source)
        self.assertEqual(source.publication_status, "published")
        for author, _ in authors:
            author.refresh_from_db()
            self.assertEqual(author.approved_by_id, expected_approvers[author.pk])
        self._assert_authors_untouched(authors)

    def test_reject_does_not_touch_linked_authors(self):
        source = self._make_source(status="review")
        authors = [
            (self._make_author(status="review", first="B", last="Two"), "review"),
            (self._make_author(status="private"), "private"),
        ]
        for position, (author, _) in enumerate(authors, start=1):
            self._link(source, author, position=position)
        self._reject(source)
        self.assertEqual(source.publication_status, "declined")
        self._assert_authors_untouched(authors)

    def test_withdraw_does_not_touch_linked_authors(self):
        source = self._make_source(status="review")
        authors = [
            (self._make_author(status="review", first="B", last="Two"), "review"),
            (
                self._make_author(status="published", first="C", last="Three"),
                "published",
            ),
        ]
        for position, (author, _) in enumerate(authors, start=1):
            self._link(source, author, position=position)
        self._withdraw(source)
        self.assertEqual(source.publication_status, "private")
        self._assert_authors_untouched(authors)

    def test_transitions_are_noop_when_no_authors(self):
        source = self._make_source()
        self._submit(source)
        self._approve(source)
        archived_or_published = source.publication_status
        self.assertEqual(archived_or_published, "published")


class SourceAuthorCitationTest(TestCase):
    """Citation links stay ordered and independently readable."""

    def setUp(self):
        self.owner = User.objects.create_user(username="citation-owner")

    def _make_source(self, title="Test Source"):
        with mute_signals(post_save):
            return Source.objects.create(
                title=title, owner=self.owner, publication_status="private"
            )

    def _make_author(self, first="John", last="Doe"):
        with mute_signals(post_save):
            return Author.objects.create(
                first_names=first,
                last_names=last,
                owner=self.owner,
                publication_status="private",
            )

    def _link(self, source, author, position=1):
        SourceAuthor.objects.create(source=source, author=author, position=position)

    def test_ordered_authors_follow_positions(self):
        source = self._make_source()
        a1 = self._make_author(first="B", last="One")
        a2 = self._make_author(first="A", last="Two")
        self._link(source, a1, position=2)
        self._link(source, a2, position=1)
        self.assertEqual(source.authors_ordered, [a2, a1])

    def test_author_count_matches_links(self):
        source = self._make_source()
        self.assertEqual(source.authors.count(), 0)
        self._link(source, self._make_author(first="A", last="One"), position=1)
        self._link(source, self._make_author(first="B", last="Two"), position=2)
        self.assertEqual(source.authors.count(), 2)
        self.assertEqual(source.sourceauthors.count(), 2)
