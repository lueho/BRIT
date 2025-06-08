from extra_views import InlineFormSetFactory

from .models import SourceAuthor


class SourceAuthorInline(InlineFormSetFactory):
    model = SourceAuthor
    form_class = 'bibliography.forms.SourceAuthorForm'
    formset_class = 'bibliography.forms.SourceAuthorFormSet'
    fields = ("author",)
    factory_kwargs = {
        "extra": 0,
        "min_num": 1,
        "can_delete": True,
    }
