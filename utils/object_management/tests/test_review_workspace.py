"""Part 7b: review workspace discovery, revision-bound approval, and
safe ``next`` resolution — canonical contract, no staff shortcuts."""

from contextlib import redirect_stderr, redirect_stdout
from datetime import timedelta
from html.parser import HTMLParser
from io import StringIO
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from materials.models import AnalyticalMethod
from utils.object_management.models import (
    ObjectEditorGrant,
    ObjectGroupEditorGrant,
    ReviewAction,
)
from utils.object_management.policy import reviewable_queryset
from utils.object_management.views import ReviewDashboardView
from utils.properties.models import Property, Unit


def _method_ct():
    return ContentType.objects.get_for_model(AnalyticalMethod)


def _events(obj, action=None):
    qs = ReviewAction.objects.filter(
        content_type=ContentType.objects.get_for_model(obj.__class__),
        object_id=obj.pk,
    )
    if action is not None:
        qs = qs.filter(action=action)
    return qs


class _FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.links = []
        self.selects = []
        self._form = None
        self._select = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            attrs["inputs"] = []
            self.forms.append(attrs)
            self._form = attrs
        elif tag == "a":
            self.links.append(attrs)
        elif tag == "input" and self._form is not None:
            self._form["inputs"].append(attrs)
        elif tag == "select":
            attrs["options"] = []
            self.selects.append(attrs)
            self._select = attrs
        elif tag == "option" and self._select is not None:
            self._select["options"].append(attrs)

    def handle_endtag(self, tag):
        if tag == "form":
            self._form = None
        elif tag == "select":
            self._select = None


def _parse(response):
    parser = _FormParser()
    parser.feed(response.content.decode())
    return parser


def _form_data(response, action):
    forms = [form for form in _parse(response).forms if form.get("action") == action]
    if len(forms) != 1:
        raise AssertionError(f"Expected one form for {action}, got {len(forms)}")
    return {
        field["name"]: field.get("value", "")
        for field in forms[0]["inputs"]
        if field.get("name")
    }


class ReviewWorkspaceFixture(TestCase):
    """Personas: registered owner/recipient (auto contributor role via
    ``sync_roles``), explicit model moderator, non-staff app admin
    (``administer_objects``), plain staff, inactive user, editor."""

    @classmethod
    def setUpTestData(cls):
        cls._role_output = StringIO()
        with redirect_stdout(cls._role_output), redirect_stderr(cls._role_output):
            call_command("sync_roles", "--apply", stdout=cls._role_output)

    def setUp(self):
        self.owner = User.objects.create_user(username="rw-owner")
        self.moderator = User.objects.create_user(username="rw-moderator")
        self.moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_analyticalmethod",
                content_type=_method_ct(),
            )
        )
        self.admin = User.objects.create_user(username="rw-appadmin")
        self.admin.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )
        self.staff = User.objects.create_user(username="rw-staff", is_staff=True)
        self.editor = User.objects.create_user(username="rw-editor")
        self.inactive = User.objects.create_user(
            username="rw-inactive", is_active=False
        )
        self.ct = _method_ct()
        self.in_review = AnalyticalMethod.objects.create(
            owner=self.owner, name="RW review", publication_status="review"
        )
        self.declined = AnalyticalMethod.objects.create(
            owner=self.owner, name="RW declined", publication_status="declined"
        )
        self.private = AnalyticalMethod.objects.create(
            owner=self.owner, name="RW private", publication_status="private"
        )
        self.published = AnalyticalMethod.objects.create(
            owner=self.owner, name="RW published", publication_status="published"
        )
        self.foreign_review = AnalyticalMethod.objects.create(
            owner=self.staff, name="Foreign review", publication_status="review"
        )

    def _dashboard(self, params=""):
        return self.client.get(
            reverse("object_management:review_dashboard") + params, follow=True
        )

    def _queue(self, params=""):
        return self.client.get(reverse("object_management:api_review_queue") + params)

    def _trans_url(self, name, obj):
        return reverse(
            f"object_management:{name}",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(obj.__class__).pk,
                "object_id": obj.pk,
            },
        )

    def _review_url(self, obj):
        return reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(obj.__class__).pk,
                "object_id": obj.pk,
            },
        )

    def _edit(self, actor, obj, name):
        self.client.force_login(actor)
        response = self.client.post(
            obj.update_url,
            {"name": name, "description": obj.description or ""},
        )
        self.assertEqual(response.status_code, 302)
        obj.refresh_from_db()
        self.assertEqual(obj.name, name)
        self.assertEqual(obj.publication_status, "review")


class ReviewQueueScopeTests(ReviewWorkspaceFixture):
    """reviewable_queryset scope + dashboard/queue state selection."""

    def test_policy_default_review_only(self):
        self.assertCountEqual(
            reviewable_queryset(self.moderator, AnalyticalMethod.objects.all()),
            [self.in_review, self.foreign_review],
        )

    def test_policy_declined_scope(self):
        self.assertEqual(
            list(
                reviewable_queryset(
                    self.moderator,
                    AnalyticalMethod.objects.all(),
                    scope="declined",
                )
            ),
            [self.declined],
        )

    def test_policy_unknown_and_blank_scope_fail_closed(self):
        for scope in ("bogus", "", None, 1, [], {}):
            self.assertFalse(
                reviewable_queryset(
                    self.moderator, AnalyticalMethod.objects.all(), scope=scope
                ).exists(),
                scope,
            )

    def test_policy_inactive_actor_empty(self):
        self.assertFalse(
            reviewable_queryset(self.inactive, AnalyticalMethod.objects.all()).exists()
        )
        self.assertFalse(
            reviewable_queryset(
                self.inactive, AnalyticalMethod.objects.all(), scope="declined"
            ).exists()
        )

    def test_policy_four_eyes_owner_with_moderation(self):
        # Owner holding model moderation STILL cannot see own submissions.
        self.owner.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_analyticalmethod",
                content_type=_method_ct(),
            )
        )
        self.assertFalse(
            reviewable_queryset(
                self.owner,
                AnalyticalMethod.objects.filter(pk=self.in_review.pk),
            ).exists()
        )
        self.assertFalse(
            reviewable_queryset(
                self.owner,
                AnalyticalMethod.objects.filter(pk=self.declined.pk),
                scope="declined",
            ).exists()
        )
        # A foreign candidate IS visible to the same owner.
        self.assertTrue(
            reviewable_queryset(
                self.owner,
                AnalyticalMethod.objects.filter(pk=self.foreign_review.pk),
            ).exists()
        )

    def test_policy_excludes_nonmoderator_and_wrong_model(self):
        self.assertFalse(
            reviewable_queryset(self.editor, AnalyticalMethod.objects.all()).exists()
        )
        # Staff-only is not moderator.
        self.assertFalse(
            reviewable_queryset(self.staff, AnalyticalMethod.objects.all()).exists()
        )
        # Unit moderation never unlocks AnalyticalMethod.
        unit_moderator = User.objects.create_user(username="unit-mod")
        unit_moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_unit",
                content_type=ContentType.objects.get_for_model(Unit),
            )
        )
        self.assertFalse(
            reviewable_queryset(unit_moderator, AnalyticalMethod.objects.all()).exists()
        )

    def test_declined_scope_multi_model_and_filters(self):
        """Declined scope honors model_type/search/owner/date filters."""
        self.moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_unit",
                content_type=ContentType.objects.get_for_model(Unit),
            )
        )
        Unit.objects.create(
            owner=self.editor, name="declined-unit", publication_status="declined"
        )
        self.client.force_login(self.moderator)
        # both declined models present
        response = self._dashboard("?scope=declined")
        names = {item.name for item in response.context["review_items"]}
        self.assertEqual(names, {"RW declined", "declined-unit"})
        # model_type narrows to one
        unit_ct = ContentType.objects.get_for_model(Unit)
        response = self._dashboard(f"?scope=declined&model_type={unit_ct.pk}")
        names = {item.name for item in response.context["review_items"]}
        self.assertEqual(names, {"declined-unit"})
        # search narrows
        response = self._dashboard("?scope=declined&search=RW")
        names = {item.name for item in response.context["review_items"]}
        self.assertEqual(names, {"RW declined"})
        # owner filter narrows to the selected owner only
        response = self._dashboard(f"?scope=declined&owner={self.owner.pk}")
        names = {item.name for item in response.context["review_items"]}
        self.assertEqual(names, {"RW declined"})
        response = self._dashboard(f"?scope=declined&owner={self.editor.pk}")
        names = {item.name for item in response.context["review_items"]}
        self.assertEqual(names, {"declined-unit"})

    def test_dashboard_default_shows_only_review(self):
        self.client.force_login(self.moderator)
        response = self._dashboard()
        self.assertEqual(response.status_code, 200)
        names = {item.name for item in response.context["review_items"]}
        self.assertIn("RW review", names)
        self.assertIn("Foreign review", names)
        self.assertNotIn("RW declined", names)
        self.assertNotIn("RW private", names)
        self.assertNotIn("RW published", names)

    def test_dashboard_form_only_filters_return_200_for_moderator(self):
        """ordering/owner/model_type/search/date fields are form-only filters
        rendered for the collector; a real moderator GET must not error."""
        self.client.force_login(self.moderator)
        response = self._dashboard(
            f"?ordering=-submitted_at&owner={self.owner.pk}"
            f"&model_type={self.ct.pk}&search=RW"
        )
        self.assertEqual(response.status_code, 200)
        names = {item.name for item in response.context["review_items"]}
        self.assertIn("RW review", names)
        self.assertNotIn("Foreign review", names)
        self.assertNotIn("RW declined", names)

        response = self._dashboard(
            "?ordering=name&submitted_after=2000-01-01&submitted_before=2100-01-01"
        )
        self.assertEqual(response.status_code, 200)

    def test_dashboard_declined_scope_shows_only_declined(self):
        self.client.force_login(self.moderator)
        response = self._dashboard("?scope=declined")
        self.assertEqual(response.status_code, 200)
        names = {item.name for item in response.context["review_items"]}
        self.assertEqual(names, {"RW declined"})

    def test_dashboard_unknown_scope_fails_closed(self):
        self.client.force_login(self.moderator)
        response = self._dashboard("?scope=bogus")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["review_items"]), 0)

    def test_queue_api_declined_scope(self):
        self.client.force_login(self.moderator)
        response = self._queue("?scope=declined")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_queue_api_default_no_declined(self):
        self.client.force_login(self.moderator)
        response = self._queue()
        self.assertEqual(response.status_code, 200)
        names = {item["name"] for item in response.json()["results"]}
        self.assertNotIn("RW declined", names)

    def test_declined_only_model_discoverable_in_scope(self):
        self.moderator.user_permissions.add(
            Permission.objects.get(
                codename="can_moderate_unit",
                content_type=ContentType.objects.get_for_model(Unit),
            )
        )
        Unit.objects.create(
            owner=self.owner, name="declined-unit", publication_status="declined"
        )
        self.client.force_login(self.moderator)
        response = self._dashboard("?scope=declined")
        self.assertEqual(response.status_code, 200)
        names = {item.name for item in response.context["review_items"]}
        self.assertIn("declined-unit", names)

    def test_pending_badge_ignores_declined(self):
        """``has_review_items`` stays pending-only: a declined-only world
        must NOT light the badge even under ``?scope=declined``."""
        AnalyticalMethod.objects.filter(pk=self.in_review.pk).delete()
        AnalyticalMethod.objects.filter(pk=self.foreign_review.pk).delete()
        self.client.force_login(self.moderator)
        for params in ("", "?scope=declined"):
            response = self._dashboard(params)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.context["view"].has_review_items(), params)

    def test_dashboard_scope_select_is_rendered(self):
        """The filter form must actually render a ``scope`` select with the
        two canonical choices and the current value selected."""
        self.client.force_login(self.moderator)
        for params, expect in (("", "review"), ("?scope=declined", "declined")):
            with self.subTest(params=params):
                response = self._dashboard(params)
                self.assertEqual(response.status_code, 200)
                select = next(
                    field
                    for field in _parse(response).selects
                    if field.get("name") == "scope"
                )
                options = select["options"]
                self.assertEqual(
                    [field["value"] for field in options], ["review", "declined"]
                )
                selected = [field["value"] for field in options if "selected" in field]
                self.assertEqual(selected or [options[0]["value"]], [expect])

    def test_dashboard_header_and_removable_filters_show_selected_scope(self):
        self.client.force_login(self.moderator)
        response = self._dashboard("?scope=declined&search=RW&ordering=name")
        self.assertContains(response, 'data-review-scope="declined"')
        self.assertContains(response, "Active filters:")
        self.assertNotContains(response, "{#")
        self.assertNotContains(response, "None?scope=")
        links = _parse(response).links
        dashboard = reverse("object_management:review_dashboard")
        self.assertTrue(any(link.get("href") == dashboard for link in links))
        self.assertTrue(
            any(
                urlsplit(link.get("href", "")).path == dashboard
                and parse_qs(urlsplit(link.get("href", "")).query)
                == {"scope": ["declined"], "ordering": ["name"]}
                for link in links
            )
        )

    def test_declined_date_order_pagination_and_repeated_model_filters(self):
        now = timezone.now().replace(microsecond=0)
        self.declined.submitted_at = now
        self.declined.save(update_fields=["submitted_at"])
        unit_ct = ContentType.objects.get_for_model(Unit)
        self.moderator.user_permissions.add(
            Permission.objects.get(content_type=unit_ct, codename="can_moderate_unit")
        )
        unit = Unit.objects.create(
            owner=self.owner,
            name="RW unit",
            publication_status="declined",
            submitted_at=now,
        )
        AnalyticalMethod.objects.create(
            owner=self.owner,
            name="RW too old",
            publication_status="declined",
            submitted_at=now - timedelta(days=10),
        )
        self.client.force_login(self.moderator)
        params = {
            "scope": "declined",
            "owner": self.owner.pk,
            "search": "RW",
            "model_type": [self.ct.pk, unit_ct.pk],
            "ordering": "-name",
            "submitted_after": (now - timedelta(days=1)).date().isoformat(),
            "submitted_before": (now + timedelta(days=1)).date().isoformat(),
        }
        with patch.object(ReviewDashboardView, "paginate_by", 1):
            response = self.client.get(
                reverse("object_management:review_dashboard"), params
            )
            self.assertEqual(response.context["paginator"].count, 2)
            self.assertEqual(list(response.context["review_items"]), [unit])
            params["page"] = 2
            second = self.client.get(
                reverse("object_management:review_dashboard"), params
            )
            self.assertEqual(list(second.context["review_items"]), [self.declined])
        payload = self.client.get(
            reverse("object_management:api_review_queue"), params
        ).json()
        self.assertEqual(
            [(item["model"], item["object_id"]) for item in payload["results"]],
            [("unit", unit.pk), ("analyticalmethod", self.declined.pk)],
        )

    def test_requests_exclude_own_candidates_even_for_moderator_owner(self):
        self.owner.user_permissions.add(
            Permission.objects.get(
                content_type=self.ct, codename="can_moderate_analyticalmethod"
            )
        )
        self.client.force_login(self.owner)
        self.assertEqual(
            list(self._dashboard().context["review_items"]), [self.foreign_review]
        )
        self.assertEqual(self._queue().json()["count"], 1)
        self.assertEqual(
            list(self._dashboard("?scope=declined").context["review_items"]), []
        )
        self.assertEqual(self._queue("?scope=declined").json()["count"], 0)

    def test_editor_and_staff_requests_never_enter_moderation_queue(self):
        team = Group.objects.create(name="review-workspace-team")
        team.user_set.add(self.editor)
        ObjectEditorGrant.objects.create(
            content_object=self.in_review, editor=self.editor, granted_by=self.owner
        )
        ObjectGroupEditorGrant.objects.create(
            content_object=self.declined, group=team, granted_by=self.owner
        )
        for actor in (self.editor, self.staff):
            self.client.force_login(actor)
            for params in ("", "?scope=declined", "?scope=", "?scope=unknown"):
                with self.subTest(actor=actor.username, scope=params):
                    self.assertEqual(
                        list(self._dashboard(params).context["review_items"]), []
                    )
                    self.assertEqual(self._queue(params).json()["count"], 0)

    def test_inactive_privileged_actor_cannot_use_review_requests(self):
        self.inactive.user_permissions.add(
            Permission.objects.get(codename="administer_objects")
        )
        self.assertFalse(
            reviewable_queryset(
                self.inactive, AnalyticalMethod.objects.all(), scope="declined"
            ).exists()
        )
        self.client.force_login(self.inactive)
        response = self.client.get(reverse("object_management:review_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._queue("?scope=declined").status_code, 401)

    def test_dashboard_empty_copy_is_scope_aware(self):
        """No misleading 'pending' copy when declined/invalid is selected."""
        AnalyticalMethod.objects.all().delete()
        self.client.force_login(self.moderator)
        response = self._dashboard("?scope=declined")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no declined items")
        response = self._dashboard("?scope=bogus")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unknown review state")

    def test_withdraw_declined_disappears_from_declined_queue(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse(
                "object_management:withdraw_from_review",
                kwargs={
                    "content_type_id": self.ct.pk,
                    "object_id": self.declined.pk,
                },
            )
        )
        self.declined.refresh_from_db()
        self.assertEqual(self.declined.publication_status, "private")
        self.client.force_login(self.moderator)
        response = self._dashboard("?scope=declined")
        names = {item.name for item in response.context["review_items"]}
        self.assertNotIn("RW declined", names)


class ReviewTransitionAccessTests(ReviewWorkspaceFixture):
    """App admin sees and executes foreign transitions; editors comment
    but cannot transition; plain staff are not admins."""

    def _post_transition(self, url_name, obj, user):
        self.client.force_login(user)
        return self.client.post(
            reverse(
                f"object_management:{url_name}",
                kwargs={
                    "content_type_id": self.ct.pk,
                    "object_id": obj.pk,
                },
            )
        )

    def test_app_admin_submits_foreign_private(self):
        foreign_private = AnalyticalMethod.objects.create(
            owner=self.staff, name="Foreign private", publication_status="private"
        )
        self._post_transition("submit_for_review", foreign_private, self.admin)
        foreign_private.refresh_from_db()
        self.assertEqual(foreign_private.publication_status, "review")
        self.assertTrue(_events(foreign_private, "submitted").exists())

    def test_app_admin_foreign_transitions_execute(self):
        """Non-staff app admin drives foreign records through the transitions
        the panel now exposes (owner wrapper removed). Each case: review-page
        GET is clean, POST is a redirect, state + one event change, content
        revision is untouched."""
        cases = (
            ("submit_for_review", "private", "review", "submitted"),
            ("submit_for_review", "declined", "review", "submitted"),
            ("withdraw_from_review", "review", "private", "withdrawn"),
            ("withdraw_from_review", "declined", "private", "withdrawn"),
        )
        self.assertFalse(self.admin.is_staff)
        for model, layout in (
            (AnalyticalMethod, "detail_v2.html"),
            (Property, "detail_with_options.html"),
        ):
            for url_name, start, end, event in cases:
                with self.subTest(model=model.__name__, state=start, action=url_name):
                    obj = model.objects.create(
                        owner=self.staff,
                        name=f"FA-{start}-{end}",
                        publication_status=start,
                    )
                    action = self._trans_url(url_name, obj)
                    self.client.force_login(self.admin)
                    for path in (
                        self._review_url(obj),
                        f"{obj.get_absolute_url()}?review=1",
                    ):
                        page = self.client.get(path)
                        self.assertEqual(page.status_code, 200)
                        self.assertTemplateUsed(page, layout)
                        self.assertIn(
                            action, [form.get("action") for form in _parse(page).forms]
                        )
                    rev_before = obj.content_revision
                    response = self.client.post(action)
                    self.assertEqual(response.status_code, 302)
                    obj.refresh_from_db()
                    self.assertEqual(obj.publication_status, end)
                    self.assertEqual(obj.owner, self.staff)
                    self.assertEqual(obj.content_revision, rev_before)
                    events = _events(obj, event)
                    self.assertEqual(events.count(), 1)
                    self.assertEqual(events.get().user, self.admin)
                    self.assertEqual(events.get().content_revision, rev_before)

    def test_editor_has_no_transition_ui_or_post(self):
        ObjectEditorGrant.objects.create(
            content_object=self.in_review,
            editor=self.editor,
            granted_by=self.owner,
        )
        self.client.force_login(self.editor)
        response = self.client.get(self._review_url(self.in_review))
        self.assertEqual(response.status_code, 200)
        actions = [form.get("action") for form in _parse(response).forms]
        for action in ("submit_for_review", "withdraw_from_review"):
            self.assertNotIn(self._trans_url(action, self.in_review), actions)
            self.assertEqual(
                self._post_transition(action, self.in_review, self.editor).status_code,
                403,
            )

    def test_editor_can_comment_but_not_transition(self):
        ObjectEditorGrant.objects.create(
            content_object=self.in_review,
            editor=self.editor,
            granted_by=self.owner,
        )
        self.client.force_login(self.editor)
        # Comment through the real endpoint on a review-state record.
        response = self.client.post(
            reverse(
                "object_management:add_review_comment",
                kwargs={
                    "content_type_id": self.ct.pk,
                    "object_id": self.in_review.pk,
                },
            ),
            {"message": "editor note"},
        )
        self.assertEqual(response.status_code, 302)
        self.in_review.refresh_from_db()
        self.assertEqual(self.in_review.content_revision, 1)
        comment = _events(self.in_review, "comment").get()
        self.assertEqual(comment.comment, "editor note")
        self.assertEqual(comment.user, self.editor)
        # Transitions remain denied for a non-owner, non-admin editor.
        for action in ("submit_for_review", "withdraw_from_review"):
            response = self._post_transition(action, self.in_review, self.editor)
            self.assertEqual(response.status_code, 403, action)

    def test_plain_staff_cannot_transition_foreign(self):
        foreign_private = AnalyticalMethod.objects.create(
            owner=self.editor, name="EP", publication_status="private"
        )
        response = self._post_transition(
            "submit_for_review", foreign_private, self.staff
        )
        self.assertEqual(response.status_code, 403)
        foreign_private.refresh_from_db()
        self.assertEqual(foreign_private.publication_status, "private")

    def test_lifecycle_history_retained_across_requests(self):
        """Owner comment -> moderator reject -> owner withdraw -> owner
        resubmit: history survives each stage, revision untouched by
        transitions/comments, reviewer loses review access on private."""
        self.in_review.content_revision = 3
        self.in_review.save()
        before_rev = self.in_review.content_revision

        # Owner comment via real request.
        self.client.force_login(self.owner)
        self.client.post(
            self._trans_url("add_review_comment", self.in_review),
            {"message": "owner note"},
        )
        history = list(_events(self.in_review).values_list("pk", "action", "comment"))
        self.assertTrue(any("owner note" in h[2] for h in history))
        self.in_review.refresh_from_db()
        self.assertEqual(self.in_review.content_revision, before_rev)

        # Moderator reject via real request.
        self.client.force_login(self.moderator)
        self.client.post(
            self._trans_url("reject_item", self.in_review),
            {"expected_revision": str(before_rev)},
        )
        self.in_review.refresh_from_db()
        self.assertEqual(self.in_review.publication_status, "declined")
        self.assertEqual(self.in_review.content_revision, before_rev)
        history_after_reject = list(
            _events(self.in_review).values_list("pk", "action", "comment")
        )
        self.assertTrue(len(history_after_reject) > len(history))

        # Owner withdraws (declined -> private) via real request.
        self.client.force_login(self.owner)
        self.client.post(self._trans_url("withdraw_from_review", self.in_review))
        self.in_review.refresh_from_db()
        self.assertEqual(self.in_review.publication_status, "private")

        # Moderator can no longer read the private record's review detail.
        self.client.force_login(self.moderator)
        self.assertEqual(
            self.client.get(self._review_url(self.in_review)).status_code, 403
        )
        # Owner still reads own record.
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(self.in_review.get_absolute_url()).status_code, 200
        )
        page = self.client.get(self._review_url(self.in_review))
        self.assertContains(page, "owner note")
        self.assertCountEqual(
            _events(self.in_review)
            .filter(pk__in=[row[0] for row in history_after_reject])
            .values_list("pk", "action", "comment"),
            history_after_reject,
        )
        response = self.client.post(
            self._trans_url("submit_for_review", self.in_review)
        )
        self.assertEqual(response.status_code, 302)
        self.in_review.refresh_from_db()
        self.assertEqual(self.in_review.publication_status, "review")
        self.assertEqual(self.in_review.content_revision, before_rev)
        self.assertEqual(_events(self.in_review, "submitted").count(), 1)
        self.assertCountEqual(
            _events(self.in_review)
            .filter(pk__in=[row[0] for row in history_after_reject])
            .values_list("pk", "action", "comment"),
            history_after_reject,
        )
        self.client.force_login(self.moderator)
        self.assertContains(
            self.client.get(self._review_url(self.in_review)), "owner note"
        )

    def test_group_editor_edits_and_comments_but_cannot_transition(self):
        group = Group.objects.create(name="review-correction-group")
        group.user_set.add(self.editor)
        ObjectGroupEditorGrant.objects.create(
            content_object=self.in_review, group=group, granted_by=self.owner
        )
        revision = self.in_review.content_revision
        self._edit(self.editor, self.in_review, "Group correction")
        self.assertEqual(self.in_review.content_revision, revision + 1)
        self.assertEqual(_events(self.in_review, "edited").get().user, self.editor)
        page = self.client.get(self._review_url(self.in_review))
        self.assertEqual(page.status_code, 200)
        self.assertNotIn(
            self._trans_url("withdraw_from_review", self.in_review),
            [form.get("action") for form in _parse(page).forms],
        )
        response = self.client.post(
            self._trans_url("add_review_comment", self.in_review),
            {"message": "Group note"},
        )
        self.assertEqual(response.status_code, 302)
        self.in_review.refresh_from_db()
        self.assertEqual(self.in_review.content_revision, revision + 1)
        self.assertEqual(_events(self.in_review, "comment").get().user, self.editor)
        before = list(_events(self.in_review).values_list("pk", flat=True))
        response = self.client.post(
            self._trans_url("withdraw_from_review", self.in_review)
        )
        self.assertEqual(response.status_code, 403)
        self.in_review.refresh_from_db()
        self.assertEqual(self.in_review.publication_status, "review")
        self.assertEqual(self.in_review.content_revision, revision + 1)
        self.assertCountEqual(
            _events(self.in_review).values_list("pk", flat=True), before
        )

    def test_public_readers_cannot_see_review_panel_or_comment(self):
        for actor in (None, self.editor, self.staff):
            with self.subTest(actor=actor):
                self.client.logout()
                if actor is not None:
                    self.client.force_login(actor)
                page = self.client.get(f"{self.published.get_absolute_url()}?review=1")
                self.assertEqual(page.status_code, 200)
                self.assertNotContains(page, 'id="review-panel"')
                before = _events(self.published).count()
                response = self.client.post(
                    self._trans_url("add_review_comment", self.published),
                    {"message": "Must not persist"},
                )
                self.assertEqual(response.status_code, 302 if actor is None else 403)
                self.assertEqual(_events(self.published).count(), before)


class ListApprovalInspectionTests(ReviewWorkspaceFixture):
    """List rows offer an inspection path, never a direct-approve POST."""

    def test_private_list_no_approve_form_for_eligible_moderator(self):
        """A moderator WITH a grant must still see an inspection path, never a
        direct-approve POST form — the vacuous owner case is replaced."""
        ObjectEditorGrant.objects.create(
            content_object=self.in_review,
            editor=self.moderator,
            granted_by=self.owner,
        )
        self.client.force_login(self.moderator)
        response = self.client.get(
            reverse("analyticalmethod-list-owned") + "?scope=shared"
        )
        self.assertEqual(response.status_code, 200)
        parser = _FormParser()
        parser.feed(response.content.decode())
        approve_path = reverse(
            "object_management:approve_item",
            kwargs={
                "content_type_id": self.ct.pk,
                "object_id": self.in_review.pk,
            },
        )
        for form in parser.forms:
            self.assertNotIn(approve_path, form.get("action", ""))
        self.assertContains(response, "Review for approval")

    def test_review_list_no_approve_post_form(self):
        self.client.force_login(self.moderator)
        response = self._dashboard()
        self.assertEqual(response.status_code, 200)
        parser = _FormParser()
        parser.feed(response.content.decode())
        approve_path = self._trans_url("approve_item", self.in_review)
        for form in parser.forms:
            self.assertNotIn(approve_path, form.get("action", ""))
        self.assertContains(response, "Review for approval")
        self.assertTrue(
            any(
                urlsplit(link.get("href", "")).path == self._review_url(self.in_review)
                for link in parser.links
            )
        )

    def test_approver_sees_review_for_approval_link(self):
        ObjectEditorGrant.objects.create(
            content_object=self.in_review,
            editor=self.moderator,
            granted_by=self.owner,
        )
        self.client.force_login(self.moderator)
        response = self.client.get(
            reverse("analyticalmethod-list-owned") + "?scope=shared"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review for approval")

    def test_nonapprover_editor_sees_review_activity_not_approve(self):
        ObjectEditorGrant.objects.create(
            content_object=self.in_review,
            editor=self.editor,
            granted_by=self.owner,
        )
        self.client.force_login(self.editor)
        response = self.client.get(
            reverse("analyticalmethod-list-owned") + "?scope=shared"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Review for approval")
        self.assertContains(response, "Review activity")


class RevisionBoundApprovalTests(ReviewWorkspaceFixture):
    """The review page shows the bound revision; a stale expected
    revision fails closed until the page is reloaded."""

    def _review_detail(self):
        return reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": self.ct.pk,
                "object_id": self.in_review.pk,
            },
        )

    def test_review_page_shows_revision_and_bound_approve_modal(self):
        self.in_review.content_revision = 7
        self.in_review.save()
        self.client.force_login(self.moderator)
        response = self.client.get(self._review_detail())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Content revision")
        self.assertContains(response, "expected_revision=7")

    def test_stale_revision_approve_fails_then_reload_succeeds(self):
        self.client.force_login(self.moderator)
        response = self.client.get(self._review_detail())
        approval = self._trans_url("approve_item", self.in_review)
        modal = self._trans_url("approve_item_modal", self.in_review)
        old_revision = self.in_review.content_revision
        old_link = next(
            link["href"]
            for link in _parse(response).links
            if urlsplit(link.get("href", "")).path == modal
        )
        self.assertEqual(
            parse_qs(urlsplit(old_link).query)["expected_revision"], [str(old_revision)]
        )
        self._edit(self.owner, self.in_review, "Mutated by owner")
        new_rev = self.in_review.content_revision
        self.assertEqual(new_rev, old_revision + 1)
        self.client.force_login(self.moderator)
        stale_form = _form_data(self.client.get(old_link), approval)
        self.assertEqual(stale_form["expected_revision"], str(old_revision))
        before = list(_events(self.in_review).values_list("pk", flat=True))
        response = self.client.post(approval, stale_form)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            any(
                "Reload the review" in str(message)
                for message in response.wsgi_request._messages
            )
        )
        self.in_review.refresh_from_db()
        self.assertEqual(self.in_review.publication_status, "review")
        self.assertEqual(self.in_review.content_revision, new_rev)
        self.assertFalse(_events(self.in_review, "approved").exists())
        self.assertCountEqual(
            _events(self.in_review).values_list("pk", flat=True), before
        )
        response = self.client.get(self._review_detail())
        new_link = next(
            link["href"]
            for link in _parse(response).links
            if urlsplit(link.get("href", "")).path == modal
        )
        fresh_form = _form_data(self.client.get(new_link), approval)
        self.assertEqual(fresh_form["expected_revision"], str(new_rev))
        response = self.client.post(approval, fresh_form)
        self.assertEqual(response.status_code, 302)
        self.in_review.refresh_from_db()
        self.assertEqual(self.in_review.publication_status, "published")
        self.assertEqual(self.in_review.content_revision, new_rev)
        self.assertEqual(
            _events(self.in_review, "approved").get().content_revision, new_rev
        )

    def test_revision_zero_remains_bound_in_the_confirmation_form(self):
        self.in_review.content_revision = 0
        self.in_review.save(update_fields=["content_revision"])
        self.client.force_login(self.moderator)
        page = self.client.get(self._review_detail())
        modal = self._trans_url("approve_item_modal", self.in_review)
        link = next(
            link["href"]
            for link in _parse(page).links
            if urlsplit(link.get("href", "")).path == modal
        )
        self.assertEqual(parse_qs(urlsplit(link).query)["expected_revision"], ["0"])
        data = _form_data(
            self.client.get(link), self._trans_url("approve_item", self.in_review)
        )
        self.assertEqual(data["expected_revision"], "0")

    def test_contributor_cannot_approve_but_can_reject(self):
        """Four-eyes: a real HTTP edit makes the admin a contributor — approve
        is denied, reject stays available. Persisted state asserted exactly."""
        self._edit(self.admin, self.in_review, "Admin edited")
        self.assertEqual(self.in_review.content_revision, 2)
        self.assertTrue(
            _events(self.in_review, "edited").filter(user=self.admin).exists()
        )

        self.client.force_login(self.admin)
        # Review page offers no Approve affordance to the contributor-admin.
        detail = self.client.get(self._review_url(self.in_review))
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(
            detail, self._trans_url("approve_item_modal", self.in_review)
        )

        # POST approve is hard-denied: no event, no state change.
        response = self.client.post(
            self._trans_url("approve_item", self.in_review),
            {"expected_revision": "2"},
        )
        self.assertEqual(response.status_code, 403)
        self.in_review.refresh_from_db()
        self.assertEqual(self.in_review.publication_status, "review")
        self.assertFalse(_events(self.in_review, "approved").exists())

        # Reject remains available and executes exactly once.
        response = self.client.post(
            self._trans_url("reject_item", self.in_review),
            {"expected_revision": "2"},
        )
        self.assertEqual(response.status_code, 302)
        self.in_review.refresh_from_db()
        self.assertEqual(self.in_review.publication_status, "declined")
        self.assertEqual(_events(self.in_review, "rejected").count(), 1)
        self.assertEqual(self.in_review.content_revision, 2)


class SafeNextRedirectTests(ReviewWorkspaceFixture):
    """External next parameters never redirect off-site or persist into
    hidden fields; relative targets are preserved."""

    def _url(self, name, obj):
        return reverse(
            f"object_management:{name}",
            kwargs={
                "content_type_id": self.ct.pk,
                "object_id": obj.pk,
            },
        )

    def test_external_next_not_redirected(self):
        self.client.force_login(self.owner)
        for bad_next in (
            "https://evil.example/x",
            "//evil.example/x",
            "javascript:alert(1)",
        ):
            with self.subTest(next=bad_next):
                response = self.client.post(
                    self._url("submit_for_review", self.private),
                    {"next": bad_next},
                )
                location = response.get("Location", "")
                self.assertNotIn("evil.example", location)
                self.assertFalse(location.startswith("javascript:"), bad_next)
                self.private.refresh_from_db()
                self.private.publication_status = "private"
                self.private.save()

    def test_relative_next_preserved(self):
        self.client.force_login(self.owner)
        target = f"{self.private.get_absolute_url()}?scope=declined"
        response = self.client.post(
            self._url("submit_for_review", self.private), {"next": target}
        )
        self.assertEqual(response.get("Location", ""), target)

    def test_modal_ignores_spoofed_next(self):
        self.client.force_login(self.moderator)
        for bad_next in ("https://evil.example/steal", "//evil.example/x"):
            with self.subTest(next=bad_next):
                response = self.client.get(
                    self._url("approve_item_modal", self.in_review)
                    + f"?next={bad_next}&expected_revision=0"
                )
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "evil.example")

    def test_same_host_insecure_http_next_denied(self):
        """http:// same-host next on an HTTPS request is not safe."""
        self.client.force_login(self.owner)
        bad = "http://testserver/materials/methods/1/"
        response = self.client.post(
            self._url("submit_for_review", self.private), {"next": bad}, secure=True
        )
        self.assertNotEqual(response.get("Location", ""), bad)
        self.private.refresh_from_db()

    def test_failure_redirect_never_leaves_site(self):
        """Exercise the ValidationError redirect, not the advisory 403 path."""
        self.client.force_login(self.moderator)
        for target in (
            "https://evil.example/x",
            "//evil.example/x",
            "http://testserver/x",
            self._review_url(self.in_review),
        ):
            with self.subTest(next=target):
                response = self.client.post(
                    self._url("approve_item", self.in_review),
                    {
                        "expected_revision": self.in_review.content_revision + 1,
                        "next": target,
                    },
                    secure=True,
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(
                    response["Location"], self.in_review.get_absolute_url()
                )
                self.in_review.refresh_from_db()
                self.assertEqual(self.in_review.publication_status, "review")
                self.assertFalse(_events(self.in_review, "approved").exists())

    def test_stale_approval_preserves_safe_declined_queue_return_url(self):
        self.client.force_login(self.moderator)
        target = (
            reverse("object_management:review_dashboard")
            + "?scope=declined&ordering=name"
        )
        response = self.client.post(
            self._url("approve_item", self.in_review),
            {"expected_revision": self.in_review.content_revision + 1, "next": target},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], target)
        self.assertFalse(_events(self.in_review, "approved").exists())
