from django.db.models.signals import post_save
from django.test import RequestFactory, TestCase
from django.urls import reverse
from factory.django import mute_signals

from utils.object_management.models import User

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
                type="misc",
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
                type="misc", title="EEA Report", abbreviation="EEA1"
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


class SourceFilterFreeTextSearchTestCase(TestCase):
    """The ``q`` free-text filter searches across key source fields."""

    @classmethod
    def setUpTestData(cls):
        cls.author = Author.objects.create(
            first_names="Sara",
            last_names="Searchable",
            publication_status="published",
        )
        with mute_signals(post_save):
            cls.source = Source.objects.create(
                type="article",
                title="A Unique Published Piece",
                citation_key="UNIQ2024",
                journal="Journal of Filtering",
                doi="10.1234/unique.doi",
                publication_status="published",
            )
            cls.other = Source.objects.create(
                type="misc",
                title="Unrelated Record",
                citation_key="OTHER1",
                publication_status="published",
            )
        SourceAuthor.objects.create(source=cls.source, author=cls.author, position=1)

    def filter_qs(self, params):
        factory = RequestFactory()
        request = factory.get(reverse("source-list"), params)
        return SourceFilter(request.GET, Source.objects.all()).qs

    def test_q_matches_title(self):
        qs = self.filter_qs({"q": "Unique Published"})
        self.assertIn(self.source, qs)
        self.assertNotIn(self.other, qs)

    def test_q_matches_citation_key(self):
        qs = self.filter_qs({"q": "UNIQ2024"})
        self.assertIn(self.source, qs)
        self.assertNotIn(self.other, qs)

    def test_q_matches_author_name(self):
        qs = self.filter_qs({"q": "Searchable"})
        self.assertIn(self.source, qs)
        self.assertNotIn(self.other, qs)

    def test_q_matches_journal(self):
        qs = self.filter_qs({"q": "Journal of Filtering"})
        self.assertIn(self.source, qs)
        self.assertNotIn(self.other, qs)

    def test_q_matches_doi(self):
        qs = self.filter_qs({"q": "unique.doi"})
        self.assertIn(self.source, qs)
        self.assertNotIn(self.other, qs)

    def test_q_blank_returns_unfiltered(self):
        qs = self.filter_qs({"q": "   "})
        self.assertEqual(Source.objects.count(), qs.count())

    def test_q_without_match_returns_empty(self):
        qs = self.filter_qs({"q": "no-such-needle"})
        self.assertEqual(0, qs.count())

    def test_q_combines_with_other_filters(self):
        qs = self.filter_qs({"q": "Unique", "type": "book"})
        self.assertEqual(0, qs.count())
        qs = self.filter_qs({"q": "Unique", "type": "article"})
        self.assertIn(self.source, qs)


class SourceFilterScopeTestCase(TestCase):
    """Autocomplete-backed choice filters must be limited to the active scope
    and to objects the request user may see."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(username="filter-owner")
        cls.other = User.objects.create(username="filter-other")
        cls.author = Author.objects.create(
            first_names="Scoped",
            last_names="Author",
            owner=cls.other,
            publication_status="published",
        )
        cls.other_private_author = Author.objects.create(
            first_names="Hidden",
            last_names="Privateauthor",
            owner=cls.other,
            publication_status="private",
        )
        cls.licence = Licence.objects.create(
            name="Scoped Licence",
            owner=cls.other,
            publication_status="published",
        )
        with mute_signals(post_save):
            cls.published_source = Source.objects.create(
                type="misc",
                title="Published Source",
                citation_key="PUB",
                owner=cls.other,
                publication_status="published",
                licence=cls.licence,
            )
            cls.own_private_source = Source.objects.create(
                type="misc",
                title="Own Private Source",
                citation_key="OWNPRIV",
                owner=cls.owner,
                publication_status="private",
            )
            cls.other_private_source = Source.objects.create(
                type="misc",
                title="Foreign Private Source",
                citation_key="FORPRIV",
                owner=cls.other,
                publication_status="private",
            )

    def filterset(self, params, user=None):
        factory = RequestFactory()
        request = factory.get(reverse("source-list"), params)
        request.user = user if user is not None else self.owner
        return SourceFilter(request.GET, Source.objects.all(), request=request)

    def test_title_choices_respect_private_scope(self):
        fs = self.filterset({"scope": "private"})
        choices = fs.filters["title"].queryset
        self.assertIn(self.own_private_source, choices)
        self.assertNotIn(self.other_private_source, choices)
        self.assertNotIn(self.published_source, choices)

    def test_title_choices_respect_published_scope(self):
        fs = self.filterset({"scope": "published"})
        choices = fs.filters["title"].queryset
        self.assertIn(self.published_source, choices)
        self.assertNotIn(self.own_private_source, choices)
        self.assertNotIn(self.other_private_source, choices)

    def test_author_choices_exclude_foreign_private_objects(self):
        fs = self.filterset({"scope": "published"})
        choices = fs.filters["author"].queryset
        self.assertIn(self.author, choices)
        self.assertNotIn(self.other_private_author, choices)

    def test_licence_choices_are_scoped(self):
        fs = self.filterset({"scope": "published"})
        choices = fs.filters["licence"].queryset
        self.assertIn(self.licence, choices)
        self.assertNotIn(
            Licence.objects.create(
                name="Hidden Licence",
                owner=self.other,
                publication_status="private",
            ),
            choices,
        )

    def test_widgets_send_scope_to_autocomplete(self):
        fs = SourceFilter(queryset=Source.objects.none())
        for name in ("title", "author", "licence"):
            self.assertEqual(
                fs.filters[name].field.widget.filter_by,
                ("scope", "name"),
            )
