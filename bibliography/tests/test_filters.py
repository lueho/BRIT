from django.db.models.signals import post_save
from django.test import RequestFactory, TestCase
from django.urls import reverse
from factory.django import mute_signals

from ..filters import AuthorFilterSet, SourceFilter
from ..models import Author, Licence, Source, SourceAuthor


class SourceFilterTestCase(TestCase):
    author1 = None
    source = None

    @classmethod
    def setUpTestData(cls):
        cls.author1 = Author.objects.create(first_names="One", last_names="Test Author")
        cls.author2 = Author.objects.create(first_names="Two", last_names="Test Author")
        cls.licence = Licence.objects.create(
            name="Test Licence", reference_url="https://www.test-licence.org"
        )
        licence2 = Licence.objects.create(
            name="Other Licence", reference_url="https://www.other-licence.org"
        )
        with mute_signals(post_save):
            cls.source = Source.objects.create(
                type="custom",
                title="Test Custom Source",
                abbreviation="TS1",
                licence=cls.licence,
            )
        SourceAuthor.objects.create(source=cls.source, author=cls.author1, position=1)
        SourceAuthor.objects.create(source=cls.source, author=cls.author2, position=2)
        with mute_signals(post_save):
            cls.source2 = Source.objects.create(
                type="book",
                title="Test Book",
                abbreviation="TS2",
                licence=licence2,
            )
        SourceAuthor.objects.create(source=cls.source2, author=cls.author2, position=1)

    def test_title_filter_by_source_pk(self):
        factory = RequestFactory()
        filter_params = {"title": self.source.pk}
        request = factory.get(
            reverse("source-detail", kwargs={"pk": self.source.pk}), filter_params
        )
        qs = SourceFilter(request.GET, Source.objects.all()).qs
        self.assertEqual(1, qs.count())
        self.assertEqual(self.source, qs.first())

    def test_author_filter_by_pk(self):
        factory = RequestFactory()
        filter_params = {"author": self.author1.pk}
        request = factory.get(
            reverse("source-detail", kwargs={"pk": self.source.pk}), filter_params
        )
        qs = SourceFilter(request.GET, Source.objects.all()).qs
        self.assertEqual(1, qs.count())
        self.assertEqual(self.source, qs.first())

    def test_author_filter_shared_author_returns_both(self):
        factory = RequestFactory()
        filter_params = {"author": self.author2.pk}
        request = factory.get(
            reverse("source-detail", kwargs={"pk": self.source.pk}), filter_params
        )
        qs = SourceFilter(request.GET, Source.objects.all()).qs
        self.assertEqual(2, qs.count())

    def test_type_filter(self):
        factory = RequestFactory()
        filter_params = {"type": "book"}
        request = factory.get(
            reverse("source-detail", kwargs={"pk": self.source.pk}), filter_params
        )
        qs = SourceFilter(request.GET, Source.objects.all()).qs
        self.assertEqual(1, qs.count())
        self.assertEqual(self.source2, qs.first())

    def test_year_filter(self):
        with mute_signals(post_save):
            Source.objects.create(title="Dated Source", abbreviation="DS", year=2021)
        factory = RequestFactory()
        filter_params = {"year": 2021}
        request = factory.get(
            reverse("source-detail", kwargs={"pk": self.source.pk}), filter_params
        )
        qs = SourceFilter(request.GET, Source.objects.all()).qs
        self.assertEqual(1, qs.count())
        self.assertEqual(2021, qs.first().year)

    def test_licence_filter(self):
        factory = RequestFactory()
        filter_params = {"licence": self.licence.pk}
        request = factory.get(
            reverse("source-detail", kwargs={"pk": self.source.pk}), filter_params
        )
        qs = SourceFilter(request.GET, Source.objects.all()).qs
        self.assertEqual(1, qs.count())
        self.assertEqual(self.source, qs.first())

    def test_filter_form_has_no_formtags(self):
        filtr = SourceFilter(queryset=Source.objects.all())
        self.assertFalse(filtr.form.helper.form_tag)


class AuthorFilterSetTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.person = Author.objects.create(
            first_names="Ada",
            last_names="Lovelace",
            publication_status="published",
        )
        cls.organization = Author.objects.create(
            author_type="organization",
            organization_name="European Environment Agency",
            publication_status="published",
        )

    def test_filter_by_organization_name(self):
        factory = RequestFactory()
        request = factory.get("/", {"organization_name": "Environment"})
        qs = AuthorFilterSet(request.GET, Author.objects.all()).qs
        self.assertIn(self.organization, qs)
        self.assertNotIn(self.person, qs)

    def test_filter_by_last_names_still_works_for_persons(self):
        factory = RequestFactory()
        request = factory.get("/", {"last_names": "Lovelace"})
        qs = AuthorFilterSet(request.GET, Author.objects.all()).qs
        self.assertIn(self.person, qs)
        self.assertNotIn(self.organization, qs)


class SourceModelFilterSetOrganizationTestCase(TestCase):
    """SourceModelFilterSet should find sources by organization author names."""

    @classmethod
    def setUpTestData(cls):
        cls.org_author = Author.objects.create(
            author_type="organization",
            organization_name="European Environment Agency",
            publication_status="published",
        )
        with mute_signals(post_save):
            cls.source = Source.objects.create(
                type="custom", title="EEA Report", abbreviation="EEA1"
            )
        SourceAuthor.objects.create(
            source=cls.source, author=cls.org_author, position=1
        )

    def test_author_text_filter_finds_source_by_organization_name(self):
        from ..filters import SourceModelFilterSet

        factory = RequestFactory()
        request = factory.get("/", {"authors": "Environment"})
        qs = SourceModelFilterSet(request.GET, Source.objects.all()).qs
        self.assertEqual(1, qs.count())
        self.assertEqual(self.source, qs.first())
