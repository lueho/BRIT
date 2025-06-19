from extra_views import InlineFormSetFactory

from .models import SourceAuthor


class SourceAuthorInline(InlineFormSetFactory):
    model = SourceAuthor
    fields = ("author",)
    factory_kwargs = {
        "extra": 0,
        "min_num": 0,  # Allow Sources without authors (was 1)
        "can_delete": True,
    }

    @property
    def form_class(self):
        """Lazy import to avoid circular dependency during Django app initialization."""
        from .forms import SourceAuthorForm

        return SourceAuthorForm

    @property
    def formset_class(self):
        """Lazy import to avoid circular dependency during Django app initialization."""
        from .forms import SourceAuthorFormSet

        return SourceAuthorFormSet
