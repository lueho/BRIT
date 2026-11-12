"""Parent edit access never implies read access to independent evidence."""

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase
from django.urls import reverse

from materials.forms import SAMPLE_SECTIONS, SampleSectionFormSet
from materials.models import (
    ComponentMeasurement,
    Material,
    MaterialComponent,
    MaterialComponentGroup,
    MaterialProperty,
    MaterialPropertyValue,
    Sample,
)
from utils.forms import workspace_section_formsets
from utils.object_management.policy import decide
from utils.properties.models import Unit


class WorkspaceEvidenceVisibilityTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("workspace-evidence-owner")
        cls.author = User.objects.create_user("workspace-evidence-author")
        for actor in (cls.owner, cls.author):
            actor.groups.clear()
            actor.user_permissions.clear()
            for model, actions in (
                (Sample, ("change",)),
                (ComponentMeasurement, ("add", "change")),
                (MaterialPropertyValue, ("add", "change")),
            ):
                actor.user_permissions.add(
                    *Permission.objects.filter(
                        content_type=ContentType.objects.get_for_model(model),
                        codename__in=[
                            f"{action}_{model._meta.model_name}" for action in actions
                        ],
                    )
                )
        material = Material.objects.create(
            name="Workspace evidence material",
            owner=cls.owner,
            publication_status="published",
        )
        cls.sample = Sample.objects.create(
            name="Workspace evidence sample",
            material=material,
            owner=cls.owner,
            publication_status="private",
            standalone=True,
        )
        cls.sample.add_editor(cls.author)
        group = MaterialComponentGroup.objects.create(
            name="Workspace evidence group", publication_status="published"
        )
        component = MaterialComponent.objects.create(
            name="Workspace evidence component", publication_status="published"
        )
        unit = Unit.objects.create(
            name="%", symbol="percent", publication_status="published"
        )
        prop = MaterialProperty.objects.create(
            name="Workspace evidence property", publication_status="published"
        )
        cls.configs = (
            (
                "measurements",
                "component_measurements",
                ComponentMeasurement,
                {"group": group.pk, "component": component.pk, "unit": unit.pk},
            ),
            (
                "properties",
                "property_values",
                MaterialPropertyValue,
                {"property": prop.pk, "unit": unit.pk},
            ),
        )
        cls.rows = {}
        for section, _, model, references in cls.configs:
            reference_ids = {f"{key}_id": value for key, value in references.items()}
            cls.rows[section] = {}
            for label, owner, status, average in (
                ("secret", cls.author, "private", 91.234567),
                ("own", cls.owner, "private", 2),
                ("public", cls.author, "published", 3),
            ):
                cls.rows[section][label] = model.objects.create(
                    sample=cls.sample,
                    owner=owner,
                    publication_status=status,
                    average=average,
                    comment=f"{section}-{label}-workspace-marker",
                    **reference_ids,
                )

    def setUp(self):
        self.client.force_login(self.owner)

    def _url(self, section):
        return (
            reverse("sample-update", kwargs={"pk": self.sample.pk})
            + f"?section={section}"
        )

    def _snapshot(self):
        return {
            section: list(
                model.objects.filter(sample=self.sample).order_by("pk").values()
            )
            for section, _, model, _ in self.configs
        }

    def _forged_payload(self, section, prefix, references, *, delete=False):
        return {
            f"{prefix}-TOTAL_FORMS": "1",
            f"{prefix}-INITIAL_FORMS": "1",
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
            f"{prefix}-0-id": self.rows[section]["secret"].pk,
            f"{prefix}-0-average": "99",
            f"{prefix}-0-comment": "Attacker-supplied value",
            **{f"{prefix}-0-{key}": value for key, value in references.items()},
            **({f"{prefix}-0-DELETE": "on"} if delete else {}),
        }

    def test_ajax_section_hides_unreadable_but_keeps_readable_evidence(self):
        before = self._snapshot()
        for section, _, _, _ in self.configs:
            with self.subTest(section=section):
                rows = self.rows[section]
                self.assertFalse(decide(self.owner, "read", rows["secret"]).allowed)
                self.assertTrue(decide(self.owner, "read", rows["own"]).allowed)
                self.assertTrue(decide(self.owner, "read", rows["public"]).allowed)
                response = self.client.get(
                    self._url(section), HTTP_X_REQUESTED_WITH="XMLHttpRequest"
                )
                self.assertEqual(response.status_code, 200)
                html = response.json()["html"]
                self.assertNotIn(rows["secret"].comment, html)
                self.assertIn(rows["own"].comment, html)
                self.assertIn(rows["public"].comment, html)
        self.assertEqual(self._snapshot(), before)

    def test_formset_and_id_choices_contain_only_readable_rows(self):
        request = RequestFactory().get(self._url("measurements"))
        request.user = self.owner
        for section, _, _, _ in self.configs:
            with self.subTest(section=section):
                formsets = workspace_section_formsets(
                    self.sample,
                    SAMPLE_SECTIONS[section],
                    request,
                    formset_class=SampleSectionFormSet,
                )
                self.assertEqual(len(formsets), 1)
                expected = {
                    self.rows[section]["own"].pk,
                    self.rows[section]["public"].pk,
                }
                formset = formsets[0]
                self.assertEqual(
                    set(formset.get_queryset().values_list("pk", flat=True)), expected
                )
                self.assertEqual(
                    set(
                        formset.forms[0]
                        .fields["id"]
                        .queryset.values_list("pk", flat=True)
                    ),
                    expected,
                )

    def test_forged_private_id_update_is_invalid_and_changes_nothing(self):
        before = self._snapshot()
        for section, prefix, _, references in self.configs:
            with self.subTest(section=section):
                response = self.client.post(
                    self._url(section),
                    self._forged_payload(section, prefix, references),
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )
                self.assertEqual(response.status_code, 422)
                self.assertNotIn(
                    self.rows[section]["secret"].comment, response.json()["html"]
                )
                self.assertEqual(self._snapshot(), before)

    def test_forged_private_id_delete_cannot_remove_or_disclose_the_row(self):
        before = self._snapshot()
        for section, prefix, _, references in self.configs:
            with self.subTest(section=section):
                response = self.client.post(
                    self._url(section),
                    self._forged_payload(section, prefix, references, delete=True),
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )
                self.assertIn(response.status_code, (200, 422))
                self.assertNotIn(
                    self.rows[section]["secret"].comment, response.json()["html"]
                )
                self.assertEqual(self._snapshot(), before)
