from collections import OrderedDict

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.serializers import (
    CharField,
    ChoiceField,
    HyperlinkedModelSerializer,
    IntegerField,
    ModelSerializer,
    SerializerMethodField,
    ValidationError,
)

from .models import (
    LETTERLESS_ORGANIZATION_NAME_MESSAGE,
    LETTERLESS_SURNAME_MESSAGE,
    Author,
    Licence,
    Source,
    author_name_has_letter,
)


class AuthorModelSerializer(ModelSerializer):
    def validate(self, attrs):
        author_type = attrs.get(
            "author_type", getattr(self.instance, "author_type", "person")
        )
        if author_type == "organization":
            organization_name = attrs.get(
                "organization_name",
                getattr(self.instance, "organization_name", ""),
            )
            if not str(organization_name or "").strip():
                raise ValidationError(
                    {"organization_name": "Organizations need a name."}
                )
            if not author_name_has_letter(organization_name):
                raise ValidationError(
                    {"organization_name": LETTERLESS_ORGANIZATION_NAME_MESSAGE}
                )
        else:
            last_names = attrs.get(
                "last_names", getattr(self.instance, "last_names", "")
            )
            if not str(last_names or "").strip():
                raise ValidationError({"last_names": "People need a surname."})
            if not author_name_has_letter(last_names):
                raise ValidationError({"last_names": LETTERLESS_SURNAME_MESSAGE})
        return attrs

    class Meta:
        model = Author
        fields = [
            "id",
            "author_type",
            "first_names",
            "middle_names",
            "last_names",
            "suffix",
            "preferred_citation",
            "organization_name",
            "organization_abbreviation",
            "bibtex_name",
            "abbreviated_full_name",
        ]
        read_only_fields = ["bibtex_name", "abbreviated_full_name"]


class LicenceModelSerializer(ModelSerializer):
    class Meta:
        model = Licence
        fields = ["id", "name", "reference_url", "description", "bibtex_entry"]
        read_only_fields = ["bibtex_entry"]


class SourceCreateAuthorSerializer(ModelSerializer):
    id = IntegerField(required=False)
    first_names = CharField(required=False, allow_blank=True)
    last_names = CharField(required=False, allow_blank=True)
    author_type = ChoiceField(
        choices=[("person", "Person"), ("organization", "Organization")], required=False
    )
    organization_name = CharField(required=False, allow_blank=True)
    organization_abbreviation = CharField(required=False, allow_blank=True)

    class Meta:
        model = Author
        fields = [
            "id",
            "author_type",
            "first_names",
            "last_names",
            "organization_name",
            "organization_abbreviation",
        ]

    def validate(self, attrs):
        if attrs.get("id") not in (None, ""):
            return attrs
        author_type = attrs.get("author_type", "person")
        if author_type == "organization":
            organization_name = attrs.get("organization_name", "")
            if not organization_name.strip():
                raise ValidationError(
                    {"organization_name": "This field is required for organizations."}
                )
            if not author_name_has_letter(organization_name):
                raise ValidationError(
                    {"organization_name": LETTERLESS_ORGANIZATION_NAME_MESSAGE}
                )
        if author_type == "person":
            last_names = attrs.get("last_names", "")
            if not last_names.strip():
                raise ValidationError(
                    {"last_names": "This field is required when id is not provided."}
                )
            if not author_name_has_letter(last_names):
                raise ValidationError({"last_names": LETTERLESS_SURNAME_MESSAGE})
        return attrs


class SourceCreateSerializer(ModelSerializer):
    authors = SourceCreateAuthorSerializer(many=True, required=False)
    type = ChoiceField(choices=Source._meta.get_field("type").choices, required=False)
    citation_key = CharField(required=False, allow_blank=True)

    class Meta:
        model = Source
        fields = [
            "id",
            "citation_key",
            "authors",
            "title",
            "type",
            "publisher",
            "journal",
            "volume",
            "number",
            "eid",
            "pages",
            "month",
            "year",
            "abstract",
            "attributions",
            "url",
            "doi",
            "last_accessed",
            "publication_status",
        ]
        read_only_fields = ["id", "publication_status"]

    def create(self, validated_data):
        from .services import create_source_with_authors

        authors_data = validated_data.pop("authors", [])
        actor = getattr(self.context.get("request"), "user", None)
        try:
            return create_source_with_authors(actor, dict(validated_data), authors_data)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc


class SourceModelSerializer(ModelSerializer):
    authors = AuthorModelSerializer(many=True, read_only=True)
    licence = LicenceModelSerializer(read_only=True)

    class Meta:
        model = Source
        fields = [
            "id",
            "citation_key",
            "authors",
            "title",
            "type",
            "licence",
            "publisher",
            "journal",
            "volume",
            "number",
            "eid",
            "pages",
            "month",
            "year",
            "abstract",
            "attributions",
            "url",
            "url_valid",
            "url_checked",
            "doi",
            "last_accessed",
        ]
        read_only_fields = ["url_valid", "url_checked", "doi", "last_accessed"]


class HyperlinkedLicenceSerializer(HyperlinkedModelSerializer):
    class Meta:
        model = Licence
        fields = ("name", "url")


class HyperlinkedAuthorSerializer(HyperlinkedModelSerializer):
    name = SerializerMethodField()

    class Meta:
        model = Author
        fields = ("name", "url")

    @staticmethod
    def get_name(instance):
        return str(instance)


class HyperlinkedSourceSerializer(HyperlinkedModelSerializer):
    authors = SerializerMethodField()
    licence = HyperlinkedLicenceSerializer()
    url_checked = SerializerMethodField()
    doi = SerializerMethodField()
    last_accessed = SerializerMethodField()

    class Meta:
        model = Source
        fields = (
            "citation_key",
            "authors",
            "title",
            "type",
            "licence",
            "publisher",
            "journal",
            "volume",
            "number",
            "eid",
            "pages",
            "month",
            "year",
            "abstract",
            "attributions",
            "url",
            "url_valid",
            "url_checked",
            "doi",
            "last_accessed",
        )

    def get_authors(self, instance):
        return HyperlinkedAuthorSerializer(
            instance.authors_ordered,
            many=True,
            context=self.context,
        ).data

    @staticmethod
    def get_url_checked(instance):
        return (
            None
            if instance.url_checked is None
            else instance.url_checked.strftime("%d.%m.%Y")
        )

    @staticmethod
    def get_last_accessed(instance):
        return (
            None
            if instance.last_accessed is None
            else instance.last_accessed.strftime("%d.%m.%Y")
        )

    @staticmethod
    def get_doi(instance):
        doi = None
        if instance.doi:
            doi = OrderedDict(
                [("name", instance.doi), ("url", f"https://doi.org/{instance.doi}")]
            )
        return doi


class SourceAbbreviationSerializer(ModelSerializer):
    class Meta:
        model = Source
        fields = ("pk", "citation_key")
