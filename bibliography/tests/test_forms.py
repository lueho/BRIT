from datetime import date

from django.db.models.signals import post_save
from django.forms.models import inlineformset_factory
from django.test import TestCase
from factory.django import mute_signals

from sources.waste_collection.models import WasteFlyer

from ..forms import AuthorModelForm, SourceAuthorFormSet, SourceModelForm
from ..models import Source, SourceAuthor


class AuthorModelFormTestCase(TestCase):
    def test_form_exposes_contact_detail_fields(self):
        form = AuthorModelForm()

        self.assertIn("institution", form.fields)
        self.assertIn("contact_email", form.fields)


class SourceAuthorFormSetRegressionTestCase(TestCase):
    """Regression tests for SourceAuthorFormSet edge cases."""

    def test_normalize_positions_skips_unsaved_wasteflyer_instance(self):
        """It should not access reverse relations before the parent instance is saved."""
        source_author_formset_class = inlineformset_factory(
            Source,
            SourceAuthor,
            formset=SourceAuthorFormSet,
            fields=("author",),
            extra=0,
            can_delete=True,
        )
        formset = source_author_formset_class(instance=WasteFlyer())

        formset._normalize_positions()


class SourceModelFormTestCase(TestCase):
    def test_form_exposes_article_metadata_fields(self):
        form = SourceModelForm()

        self.assertIn("volume", form.fields)
        self.assertIn("eid", form.fields)
        self.assertIn("number", form.fields)
        self.assertIn("pages", form.fields)
        self.assertIn("month", form.fields)


class SourceModelFormLastAccessedTestCase(TestCase):
    """Tests for automatic last_accessed population when a URL is present."""

    def test_create_with_url_sets_last_accessed_to_today(self):
        form = SourceModelForm(
            data={
                "title": "Test Source",
                "type": "custom",
                "url": "https://example.com",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        source = form.save()
        source.refresh_from_db()
        self.assertEqual(source.last_accessed, date.today())

    def test_create_without_url_leaves_last_accessed_null(self):
        form = SourceModelForm(data={"title": "Test Source", "type": "custom"})
        self.assertTrue(form.is_valid(), form.errors)
        source = form.save()
        source.refresh_from_db()
        self.assertIsNone(source.last_accessed)

    def test_create_with_url_and_manual_last_accessed_preserved(self):
        manual_date = date(2024, 1, 15)
        form = SourceModelForm(
            data={
                "title": "Test Source",
                "type": "custom",
                "url": "https://example.com",
                "last_accessed": manual_date.isoformat(),
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        source = form.save()
        source.refresh_from_db()
        self.assertEqual(source.last_accessed, manual_date)

    def test_update_url_changes_resets_last_accessed_to_today(self):
        with mute_signals(post_save):
            source = Source.objects.create(
                title="Test Source",
                type="custom",
                url="https://old.example.com",
                last_accessed=date(2024, 1, 15),
            )
        form = SourceModelForm(
            instance=source,
            data={
                "title": "Test Source",
                "type": "custom",
                "url": "https://new.example.com",
                "last_accessed": "2024-01-15",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        source.refresh_from_db()
        self.assertEqual(source.last_accessed, date.today())

    def test_update_url_unchanged_preserves_existing_last_accessed(self):
        with mute_signals(post_save):
            source = Source.objects.create(
                title="Test Source",
                type="custom",
                url="https://example.com",
                last_accessed=date(2024, 1, 15),
            )
        form = SourceModelForm(
            instance=source,
            data={
                "title": "Updated Title",
                "type": "custom",
                "url": "https://example.com",
                "last_accessed": "2024-01-15",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        source.refresh_from_db()
        self.assertEqual(source.last_accessed, date(2024, 1, 15))

    def test_update_url_unchanged_null_last_accessed_sets_to_today(self):
        with mute_signals(post_save):
            source = Source.objects.create(
                title="Test Source",
                type="custom",
                url="https://example.com",
            )
        form = SourceModelForm(
            instance=source,
            data={
                "title": "Updated Title",
                "type": "custom",
                "url": "https://example.com",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        source.refresh_from_db()
        self.assertEqual(source.last_accessed, date.today())
