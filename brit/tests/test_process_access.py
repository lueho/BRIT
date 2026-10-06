from django.contrib.auth.models import Group, Permission, User
from django.test import TestCase
from django.urls import reverse


class ProcessNavigationPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="navigation-participant")
        cls.group = Group.objects.create(name="workshop-navigation")
        cls.permission = Permission.objects.get(
            content_type__app_label="processes", codename="access_app_feature"
        )
        cls.group.permissions.add(cls.permission)

    def test_group_permission_shows_sidebar_and_home_card(self):
        self.user.groups.add(self.group)
        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "processes_cover_card.png")
        self.assertContains(
            response, f'href="{reverse("processes:process-list")}"', count=3
        )

    def test_direct_permission_shows_module(self):
        self.user.user_permissions.add(self.permission)
        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))
        self.assertContains(response, "processes_cover_card.png")

    def test_group_name_alone_does_not_show_module(self):
        self.user.groups.add(Group.objects.get_or_create(name="process-team")[0])
        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "processes_cover_card.png")

    def test_anonymous_user_does_not_see_module(self):
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, "processes_cover_card.png")

    def test_removing_membership_hides_module_on_next_request(self):
        self.user.groups.add(self.group)
        self.client.force_login(self.user)
        self.client.get(reverse("home"))
        self.user.groups.remove(self.group)
        self.assertNotContains(
            self.client.get(reverse("home")), "processes_cover_card.png"
        )
