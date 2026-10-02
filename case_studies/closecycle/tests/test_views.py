from maps.models import Catchment, Region
from materials.models import Material
from processes.models import Process
from utils.tests.testcases import AbstractTestCases

from ..models import Showcase


class ShowCaseCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    dashboard_view = False
    add_scope_query_param_to_list_urls = True

    model = Showcase

    view_create_name = "showcase-create"
    view_published_list_name = "showcase-list"
    view_private_list_name = "showcase-list-owned"
    view_detail_name = "showcase-detail"
    view_update_name = "showcase-update"
    view_delete_name = "showcase-delete-modal"

    create_object_data = {"name": "Test Showcase"}
    update_object_data = {"name": "Updated Test Showcase"}

    @classmethod
    def create_related_objects(cls):
        return {
            "region": Region.objects.create(
                name="Test Region", publication_status="published"
            )
        }

    def related_objects_post_data(self):
        """Include management form data for the inline formsets."""
        data = super().related_objects_post_data()
        data.update(
            {
                "showcase_materials-TOTAL_FORMS": "0",
                "showcase_materials-INITIAL_FORMS": "0",
                "showcase_materials-MIN_NUM_FORMS": "0",
                "showcase_materials-MAX_NUM_FORMS": "1000",
                "showcase_processes-TOTAL_FORMS": "0",
                "showcase_processes-INITIAL_FORMS": "0",
                "showcase_processes-MIN_NUM_FORMS": "0",
                "showcase_processes-MAX_NUM_FORMS": "1000",
            }
        )
        return data

    def test_create_view_renders_distinct_formset_controls_per_inline(self):
        """Each inline gets its own add button, container and empty-row template."""
        self.client.force_login(self.user_with_add_perm)
        response = self.client.get(self.get_create_url())
        self.assertEqual(response.status_code, 200)
        for prefix in ("showcase_materials", "showcase_processes"):
            for element in ("add-form", "formset-container", "empty-form-row"):
                with self.subTest(prefix=prefix, element=element):
                    self.assertContains(
                        response, f'id="{prefix}_{element}"', count=1, html=False
                    )
            self.assertContains(response, f'data-formset-id="{prefix}"', count=1)

    def test_create_view_post_with_inline_materials_and_processes(self):
        """Creating a showcase can attach material and process links inline."""
        self.client.force_login(self.user_with_add_perm)
        material = Material.objects.create(
            name="Inline Feedstock", publication_status="published"
        )
        process = Process.objects.create(
            name="Inline Process", publication_status="published"
        )
        data = {
            "name": "Chained Showcase",
            "region": self.related_objects["region"].pk,
            "showcase_materials-TOTAL_FORMS": "1",
            "showcase_materials-INITIAL_FORMS": "0",
            "showcase_materials-MIN_NUM_FORMS": "0",
            "showcase_materials-MAX_NUM_FORMS": "1000",
            "showcase_materials-0-material": str(material.pk),
            "showcase_materials-0-role": "input",
            "showcase_materials-0-order": "0",
            "showcase_processes-TOTAL_FORMS": "1",
            "showcase_processes-INITIAL_FORMS": "0",
            "showcase_processes-MIN_NUM_FORMS": "0",
            "showcase_processes-MAX_NUM_FORMS": "1000",
            "showcase_processes-0-process": str(process.pk),
            "showcase_processes-0-order": "0",
        }
        response = self.client.post(self.get_create_url(), data)
        self.assertEqual(response.status_code, 302)
        showcase = Showcase.objects.get(name="Chained Showcase")
        link = showcase.showcase_materials.get()
        self.assertEqual(material, link.material)
        self.assertEqual("input", link.role)
        self.assertEqual([process], showcase.process_chain)

    def test_update_view_post_replaces_inline_links(self):
        """Updating a showcase can reorder the process chain inline."""
        self.client.force_login(self.owner_user)
        process_a = Process.objects.create(
            name="First Process", publication_status="published"
        )
        process_b = Process.objects.create(
            name="Second Process", publication_status="published"
        )
        showcase = self.unpublished_object
        link = showcase.showcase_processes.create(process=process_a, order=1)
        data = {
            "name": "Updated Test Showcase",
            "region": self.related_objects["region"].pk,
            "showcase_materials-TOTAL_FORMS": "0",
            "showcase_materials-INITIAL_FORMS": "0",
            "showcase_materials-MIN_NUM_FORMS": "0",
            "showcase_materials-MAX_NUM_FORMS": "1000",
            "showcase_processes-TOTAL_FORMS": "2",
            "showcase_processes-INITIAL_FORMS": "1",
            "showcase_processes-MIN_NUM_FORMS": "0",
            "showcase_processes-MAX_NUM_FORMS": "1000",
            "showcase_processes-0-id": str(link.pk),
            "showcase_processes-0-process": str(process_a.pk),
            "showcase_processes-0-order": "2",
            "showcase_processes-1-process": str(process_b.pk),
            "showcase_processes-1-order": "1",
        }
        response = self.client.post(self.get_update_url(showcase.pk), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual([process_b, process_a], showcase.process_chain)

    def test_detail_view_hides_private_connections_from_anonymous_users(self):
        owner = self.owner_user
        showcase = self.published_object
        public_material = Material.objects.create(
            name="Public Detail Feedstock", publication_status="published"
        )
        private_material = Material.objects.create(
            name="Private Detail Feedstock", owner=owner
        )
        for material in (public_material, private_material):
            showcase.showcase_materials.create(material=material, role="input")
        showcase.showcase_processes.create(
            process=Process.objects.create(name="Private Detail Step", owner=owner),
            order=1,
        )

        response = self.client.get(self.get_detail_url(showcase.pk))

        self.assertContains(response, "Public Detail Feedstock")
        self.assertNotContains(response, "Private Detail Feedstock")
        self.assertNotContains(response, "Private Detail Step")

        self.client.force_login(owner)
        response = self.client.get(self.get_detail_url(showcase.pk))
        self.assertContains(response, "Private Detail Feedstock")
        self.assertContains(response, "Private Detail Step")

    def test_detail_map_omits_private_catchment_for_anonymous_users(self):
        owner = self.owner_user
        showcase = self.published_object
        showcase.catchment = Catchment.objects.create(
            name="Private Map Catchment", region=showcase.region, owner=owner
        )
        showcase.save()

        response = self.client.get(self.get_detail_url(showcase.pk))
        self.assertIsNone(response.context["view"].get_catchment_feature_id())

        self.client.force_login(owner)
        response = self.client.get(self.get_detail_url(showcase.pk))
        self.assertEqual(
            showcase.catchment.pk, response.context["view"].get_catchment_feature_id()
        )
