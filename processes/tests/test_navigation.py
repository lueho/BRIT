"""Tests for the Processes discovery navigation (Processes | Categories)."""

import re
from urllib.parse import quote

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from ..models import Process, ProcessCategory


class ProcessDiscoveryNavigationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="nav-owner")
        cls.moderator = User.objects.create_user(username="nav-moderator")
        cls.moderator.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="processes",
                codename="can_moderate_process",
            )
        )
        cls.category = ProcessCategory.objects.create(
            name="Thermochemical",
            owner=cls.owner,
            publication_status="published",
            description="Thermal conversion.",
        )
        cls.other_category = ProcessCategory.objects.create(
            name="Biochemical",
            owner=cls.owner,
            publication_status="published",
        )
        cls.process = Process.objects.create(
            name="Pyrolysis",
            owner=cls.owner,
            publication_status="published",
        )
        cls.process.categories.add(cls.category, cls.other_category)

    def test_process_lists_show_discovery_nav_without_explorer(self):
        for url_name, params in (
            ("processes:process-list", {"scope": "published"}),
            ("processes:process-list-owned", {"scope": "private"}),
        ):
            with self.subTest(url_name=url_name):
                self.client.force_login(self.owner)
                response = self.client.get(reverse(url_name), params)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "process-discovery-nav")
                self.assertContains(
                    response,
                    f'href="{reverse("processes:processcategory-list")}'
                    f'?scope={params["scope"]}"',
                )
                self.assertNotContains(response, "Explorer")

        self.client.force_login(self.moderator)
        response = self.client.get(
            reverse("processes:process-list-review"), {"scope": "review"}
        )
        self.assertContains(response, "process-discovery-nav")
        self.assertContains(
            response,
            f'href="{reverse("processes:processcategory-list")}?scope=review"',
        )
        self.assertNotContains(response, "Explorer")

    def test_anonymous_nav_has_no_review_or_mine_links(self):
        response = self.client.get(reverse("processes:processcategory-list"))
        self.assertNotContains(response, "process-list-review")
        self.assertNotContains(response, ">Mine</a>")

    def test_member_without_process_moderation_has_no_review_link(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("processes:processcategory-list"))
        self.assertNotContains(response, "process-list-review")
        self.assertNotContains(response, "scope=review")

    def test_process_moderator_sees_review_scope_on_catalogue(self):
        """Process moderation rights unlock the review scope on the
        category catalogue, even without category moderation rights."""
        self.assertFalse(
            self.moderator.has_perm("processes.can_moderate_processcategory")
        )
        self.client.force_login(self.moderator)
        response = self.client.get(
            reverse("processes:processcategory-list"), {"scope": "review"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Thermochemical")
        self.assertContains(
            response,
            f'href="{reverse("processes:processcategory-list")}?scope=published"',
        )

    def test_anonymous_supplied_private_scope_normalizes_to_published(self):
        response = self.client.get(
            reverse("processes:processcategory-list"), {"scope": "private"}
        )
        self.assertNotContains(response, "scope=private")
        self.assertNotContains(response, "scope=review")
        self.assertContains(
            response,
            f'href="{reverse("processes:processcategory-list")}?scope=published"',
        )

    def test_anonymous_supplied_review_scope_normalizes_to_published(self):
        response = self.client.get(
            reverse("processes:processcategory-list"), {"scope": "review"}
        )
        self.assertNotContains(response, "scope=review")
        self.assertNotContains(response, "scope=private")
        view_processes = f"{reverse('processes:process-list')}?"
        self.assertContains(response, view_processes)
        self.assertNotContains(response, reverse("processes:process-list-review"))

    def test_non_moderator_supplied_review_scope_normalizes_to_published(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("processes:processcategory-list"), {"scope": "review"}
        )
        self.assertNotContains(response, "scope=review")
        self.assertNotContains(response, reverse("processes:process-list-review"))

    def test_anonymous_return_context_scope_is_normalized(self):
        url = reverse("processes:process-detail", kwargs={"pk": self.process.pk})
        back = f"{reverse('processes:process-list-review')}?scope=review"
        response = self.client.get(url, {"back": back})
        self.assertNotContains(response, "process-list-review")

    def test_catalogue_is_alphabetical_and_has_card_actions(self):
        ProcessCategory.objects.create(
            name="Aardvark category",
            owner=self.owner,
            publication_status="published",
        )
        response = self.client.get(reverse("processes:processcategory-list"))
        self.assertEqual(response.status_code, 200)
        names = [c.name for c in response.context["categories"]]
        self.assertEqual(names, sorted(names))
        content = response.content.decode()
        self.assertLess(
            content.index("Aardvark category"), content.index("Biochemical")
        )
        self.assertContains(response, "View processes")
        self.assertContains(response, "About this category")
        self.assertNotContains(response, "process_count")
        self.assertNotContains(response, "Explorer")

    def test_catalogue_search_filters_by_name_only(self):
        response = self.client.get(
            reverse("processes:processcategory-list"), {"category_q": "Thermo"}
        )
        self.assertContains(response, "Thermochemical")
        self.assertNotContains(response, "Biochemical")
        response = self.client.get(
            reverse("processes:processcategory-list"), {"category_q": "x"}
        )
        for url in self._hrefs(response):
            if "processes/list" in url or re.search(r"categories/\d+/", url):
                self.assertNotIn("category_q", url)

    def test_catalogue_search_form_preserves_process_filters(self):
        params = {
            "scope": "published",
            "category_q": "Thermo",
            "name": "dig",
            "categories": [str(self.category.pk), str(self.other_category.pk)],
            "input_material": "5",
            "output_material": "7",
        }
        response = self.client.get(reverse("processes:processcategory-list"), params)
        self.assertEqual(response.status_code, 200)
        for key, value in (
            ("name", "dig"),
            ("categories", str(self.category.pk)),
            ("categories", str(self.other_category.pk)),
            ("input_material", "5"),
            ("output_material", "7"),
        ):
            self.assertContains(response, f'name="{key}" value="{value}"')
        self.assertContains(response, 'name="scope" value="published"')
        self.assertContains(response, 'name="category_q"')
        self.assertContains(response, 'value="Thermo"')

    def test_catalogue_scope_links_keep_search_and_filters(self):
        self.client.force_login(self.owner)
        params = {
            "scope": "published",
            "category_q": "Thermo",
            "categories": [str(self.category.pk), str(self.other_category.pk)],
            "page": "1",
        }
        response = self.client.get(reverse("processes:processcategory-list"), params)
        self.assertEqual(response.status_code, 200)
        private_url = (
            f"{reverse('processes:processcategory-list')}"
            f"?categories={self.category.pk}&amp;categories={self.other_category.pk}"
            f"&amp;scope=private&amp;category_q=Thermo"
        )
        self.assertContains(response, f'href="{private_url}"')
        self.assertNotContains(response, "page=1")

    def test_catalogue_reset_search_keeps_process_filters(self):
        params = {
            "scope": "private",
            "category_q": "Thermo",
            "name": "dig",
        }
        self.client.force_login(self.owner)
        response = self.client.get(reverse("processes:processcategory-list"), params)
        reset = (
            f"{reverse('processes:processcategory-list')}?name=dig&amp;scope=private"
        )
        self.assertContains(response, f'href="{reset}"')
        self.assertNotIn("category_q", reset)

    def test_catalogue_view_processes_links_to_scoped_filtered_list(self):
        self.client.force_login(self.moderator)
        response = self.client.get(
            reverse("processes:processcategory-list"),
            {"scope": "review", "name": "dig"},
        )
        expected = (
            f"{reverse('processes:process-list-review')}"
            f"?name=dig&categories={self.category.pk}&scope=review"
        )
        self.assertContains(response, f'href="{expected.replace("&", "&amp;")}"')

    def test_catalogue_ignores_process_scope_and_name_filters(self):
        """Process discovery params (review scope, process name) must not
        restrict the published category cards."""
        self.client.force_login(self.moderator)
        response = self.client.get(
            reverse("processes:processcategory-list"),
            {"scope": "review", "name": "dig"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {self.category, self.other_category}, set(response.context["categories"])
        )

    def test_catalogue_about_link_replaces_category_selection(self):
        """About this category must scope to the clicked category, not carry
        a previously selected category into the detail gallery."""
        params = {"scope": "published", "categories": [str(self.category.pk)]}
        response = self.client.get(reverse("processes:processcategory-list"), params)
        expected = (
            reverse(
                "processes:processcategory-detail",
                kwargs={"pk": self.other_category.pk},
            )
            + f"?categories={self.other_category.pk}&scope=published"
        )
        self.assertContains(response, f'href="{expected.replace("&", "&amp;")}"')

    def test_about_journey_shows_clicked_category_processes(self):
        """Browsing a list filtered to category A then opening About B must
        display B's process rather than an empty A-filtered gallery."""
        process_a = Process.objects.create(
            name="Process A", owner=self.owner, publication_status="published"
        )
        process_a.categories.add(self.category)
        process_b = Process.objects.create(
            name="Process B", owner=self.owner, publication_status="published"
        )
        process_b.categories.add(self.other_category)
        response = self.client.get(
            reverse("processes:processcategory-list"),
            {"categories": [str(self.category.pk)]},
        )
        about_b = (
            reverse(
                "processes:processcategory-detail",
                kwargs={"pk": self.other_category.pk},
            )
            + f"?categories={self.other_category.pk}&scope=published"
        )
        self.assertContains(response, f'href="{about_b.replace("&", "&amp;")}"')
        response = self.client.get(about_b)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Process B")
        self.assertNotContains(response, "Process A")

    def test_catalogue_secondary_management_links(self):
        response = self.client.get(reverse("processes:processcategory-list"))
        self.assertNotContains(
            response, reverse("processes:processcategory-list-owned")
        )
        self.assertNotContains(response, reverse("processes:processcategory-create"))
        self.client.force_login(self.owner)
        response = self.client.get(reverse("processes:processcategory-list"))
        self.assertContains(response, reverse("processes:processcategory-list-owned"))
        self.assertNotContains(response, reverse("processes:processcategory-create"))
        self.owner.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="processes",
                codename="add_processcategory",
            )
        )
        response = self.client.get(reverse("processes:processcategory-list"))
        self.assertContains(response, reverse("processes:processcategory-create"))

    def test_category_management_lists_show_compact_discovery_nav(self):
        self.client.force_login(self.owner)
        for url_name, params in (
            ("processes:processcategory-list-owned", {"scope": "private"}),
        ):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name), params)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "process-discovery-nav")
                self.assertContains(
                    response,
                    f'href="{reverse("processes:process-list-owned")}?scope=private"',
                )
                self.assertNotContains(response, "process-list-review")

    def test_category_chip_is_independent_anchor_filtering_current_list(self):
        response = self.client.get(
            reverse("processes:process-list"),
            {"scope": "published", "name": "Pyro", "page": "1"},
        )
        self.assertEqual(response.status_code, 200)
        expected = (
            f"{reverse('processes:process-list')}"
            f"?name=Pyro&categories={self.category.pk}&scope=published"
        )
        expected_html = expected.replace("&", "&amp;")
        self.assertContains(response, f'href="{expected_html}"')
        content = response.content.decode()
        detail_link = content.index('aria-label="View details of Pyrolysis"')
        chip = content.index(f'href="{expected_html}"')
        self.assertGreater(chip, detail_link)
        chip_open = content.rindex("<a", 0, chip)
        chip_tag = content[chip_open : content.index(">", chip)]
        self.assertIn("stopPropagation", chip_tag)
        self.assertNotIn("preventDefault", chip_tag)

    def test_scope_switch_links_keep_repeated_categories(self):
        """Published/Mine/Review scope links must carry every repeated
        category parameter, not just the last one."""
        self.client.force_login(self.moderator)
        response = self.client.get(
            reverse("processes:process-list"),
            {
                "scope": "published",
                "categories": [str(self.category.pk), str(self.other_category.pk)],
                "publication_status": "declined",
            },
        )
        self.assertEqual(response.status_code, 200)
        toggle = re.search(
            r'<div class="btn-group btn-group-sm" role="group" aria-label="Scope toggle">(.*?)'
            r"</div>",
            response.content.decode(),
            re.DOTALL,
        )
        self.assertIsNotNone(toggle)
        hrefs = re.findall(r'href="([^"]+)"', toggle.group(1))
        self.assertEqual(len(hrefs), 3)
        for href in hrefs:
            self.assertIn(f"categories={self.category.pk}", href)
            self.assertIn(f"categories={self.other_category.pk}", href)
            self.assertNotIn("publication_status", href)

    def test_repeated_category_params_survive_scope_tab_navigation(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("processes:process-list"),
            {
                "scope": "published",
                "categories": [str(self.category.pk), str(self.other_category.pk)],
            },
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(
            f"categories={self.category.pk}&amp;categories={self.other_category.pk}",
            content,
        )

    def test_external_back_url_does_not_alter_generated_links(self):
        url = reverse("processes:process-detail", kwargs={"pk": self.process.pk})
        response = self.client.get(
            url, {"back": "https://evil.example/phish?scope=review"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "evil.example")
        self.assertNotContains(response, "scope=review")
        self.assertContains(
            response,
            f'href="{reverse("processes:process-list")}?scope=published"',
        )

    def test_nested_return_url_is_ignored(self):
        inner = quote(
            f"{reverse('processes:process-list')}?back=https://evil.example", safe=""
        )
        url = reverse("processes:process-detail", kwargs={"pk": self.process.pk})
        response = self.client.get(url, {"back": inner})
        self.assertContains(
            response,
            f'href="{reverse("processes:process-list")}?scope=published"',
        )
        self.assertNotContains(response, "process-list-review")
        self.assertNotContains(response, "scope=review")

    def test_local_back_url_restores_scope_and_filters(self):
        url = reverse("processes:process-detail", kwargs={"pk": self.process.pk})
        back = (
            f"{reverse('processes:process-list-owned')}"
            f"?scope=private&name=dig&categories={self.category.pk}"
        )
        self.client.force_login(self.owner)
        response = self.client.get(url, {"back": back})
        self.assertContains(response, f'href="{back.replace("&", "&amp;")}"')
        self.assertContains(
            response,
            f'href="{reverse("processes:process-list-owned")}'
            f'?name=dig&amp;categories={self.category.pk}&amp;scope=private"',
        )

    def test_unknown_return_route_is_ignored(self):
        url = reverse("processes:process-detail", kwargs={"pk": self.process.pk})
        response = self.client.get(url, {"back": "/admin/?scope=review"})
        self.assertContains(
            response,
            f'href="{reverse("processes:process-list")}?scope=published"',
        )
        self.assertNotContains(response, "process-list-review")

    def test_category_detail_shows_nav_and_no_counts(self):
        url = reverse(
            "processes:processcategory-detail", kwargs={"pk": self.category.pk}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "process-discovery-nav")
        self.assertContains(response, "Processes in This Category")
        self.assertNotContains(response, "process_count")
        self.assertNotContains(response, "Related Categories (")
        self.assertContains(response, "Pyrolysis")

    def test_category_detail_explicit_review_scope_shows_review_gallery(self):
        review_process = Process.objects.create(
            name="Review Process", owner=self.owner, publication_status="review"
        )
        review_process.categories.add(self.category)
        private_process = Process.objects.create(
            name="Private Process", owner=self.owner, publication_status="private"
        )
        private_process.categories.add(self.category)
        url = reverse(
            "processes:processcategory-detail", kwargs={"pk": self.category.pk}
        )
        self.client.force_login(self.moderator)
        response = self.client.get(url, {"scope": "review"})
        self.assertContains(response, "Review Process")
        self.assertNotContains(response, "Private Process")
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertContains(response, "Private Process")
        self.assertContains(response, "Review Process")

    def test_review_detail_next_context_is_preserved(self):
        review_process = Process.objects.create(
            name="Moderated Process", owner=self.owner, publication_status="review"
        )
        review_url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(Process).pk,
                "object_id": review_process.pk,
            },
        )
        next_url = f"{reverse('processes:process-list-review')}?scope=review&name=Mod"
        self.client.force_login(self.moderator)
        response = self.client.get(review_url, {"next": next_url})
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'href="{reverse("processes:process-list-review")}'
            '?name=Mod&amp;scope=review"',
        )

    def test_category_detail_next_back_returns_to_category_page(self):
        """A gallery link into the review context must keep the category
        page as the 'Back to results' target and restore its context."""
        review_process = Process.objects.create(
            name="Moderated Process", owner=self.owner, publication_status="review"
        )
        review_process.categories.add(self.category)
        category_url = (
            reverse(
                "processes:processcategory-detail",
                kwargs={"pk": self.category.pk},
            )
            + f"?categories={self.category.pk}&scope=review"
        )
        self.client.force_login(self.moderator)
        response = self.client.get(category_url)
        self.assertEqual(response.status_code, 200)
        gallery_link = re.search(
            r'href="([^"]*review[^"]*)"[^>]*class="card[^"]*"',
            response.content.decode(),
        )
        self.assertIsNotNone(gallery_link)
        target = gallery_link.group(1).replace("&amp;", "&")
        self.assertIn("next=", target)
        response = self.client.get(target)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{category_url.replace("&", "&amp;")}"')
        self.assertContains(response, "scope=review")
        self.assertContains(response, f"categories={self.category.pk}")

    def test_public_detail_back_returns_to_category_page(self):
        category_url = (
            reverse(
                "processes:processcategory-detail",
                kwargs={"pk": self.category.pk},
            )
            + f"?categories={self.category.pk}&scope=published"
        )
        response = self.client.get(category_url)
        self.assertEqual(response.status_code, 200)
        gallery_link = re.search(
            r'href="([^"]*processes/\d+/[^"]*)"[^>]*class="card[^"]*"',
            response.content.decode(),
        )
        self.assertIsNotNone(gallery_link)
        target = gallery_link.group(1).replace("&amp;", "&")
        self.assertIn("back=", target)
        response = self.client.get(target)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{category_url.replace("&", "&amp;")}"')
        self.assertContains(response, "scope=published")

    def test_nested_return_url_does_not_render_back_link(self):
        inner = quote(
            f"{reverse('processes:process-list')}?back=/processes/list/", safe=""
        )
        url = reverse("processes:process-detail", kwargs={"pk": self.process.pk})
        response = self.client.get(url, {"back": inner})
        self.assertNotContains(response, "Back to results")

    def test_external_next_url_renders_no_back_link(self):
        url = reverse("processes:process-detail", kwargs={"pk": self.process.pk})
        response = self.client.get(url, {"next": "https://evil.example/"})
        self.assertNotContains(response, "Back to results")
        self.assertNotContains(response, "evil.example")

    def test_empty_published_list_offers_review_link_to_process_moderator(self):
        Process.objects.all().delete()
        self.client.force_login(self.moderator)
        response = self.client.get(
            reverse("processes:process-list"), {"scope": "published"}
        )
        self.assertContains(response, "No published processes yet.")
        self.assertContains(response, "Browse processes in review")
        self.assertContains(
            response, f'href="{reverse("processes:process-list-review")}?scope=review"'
        )
        self.assertNotContains(response, "Nothing here yet")

    def test_empty_published_list_hides_review_link_for_regular_users(self):
        Process.objects.all().delete()
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("processes:process-list"), {"scope": "published"}
        )
        self.assertContains(response, "No published processes yet.")
        self.assertNotContains(response, "Browse processes in review")

    def test_filtered_empty_list_shows_filter_message_and_reset(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("processes:process-list"),
            {"scope": "published", "name": "no-such-process"},
        )
        self.assertContains(response, "No processes match your current filters.")
        self.assertContains(
            response,
            f'href="{reverse("processes:process-list")}?scope=published"',
        )
        self.assertNotContains(response, "No published processes yet.")

    @staticmethod
    def _hrefs(response):
        return re.findall(r'href="([^"]+)"', response.content.decode())
