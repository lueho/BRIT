from collections import OrderedDict

from rest_framework.exceptions import PermissionDenied
from rest_framework.serializers import (
    CharField,
    ChoiceField,
    HyperlinkedModelSerializer,
    IntegerField,
    ModelSerializer,
    SerializerMethodField,
    ValidationError,
)

from .models import Author, Licence, Source, SourceAuthor


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
        else:
            last_names = attrs.get(
                "last_names", getattr(self.instance, "last_names", "")
            )
            if not str(last_names or "").strip():
                raise ValidationError({"last_names": "People need a surname."})
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
        author_type = attrs.get("author_type", "person")
        if (
            attrs.get("id") in (None, "")
            and author_type == "organization"
            and not attrs.get("organization_name", "").strip()
        ):
            raise ValidationError(
                {"organization_name": "This field is required for organizations."}
            )
        if (
            attrs.get("id") in (None, "")
            and author_type == "person"
            and not attrs.get("last_names", "").strip()
        ):
            raise ValidationError(
                {"last_names": "This field is required when id is not provided."}
            )
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

    def _resolve_authors(self, owner, authors_data):
        authors = []
        author_ids = set()

        for author_data in authors_data:
            raw_author_id = author_data.get("id")
            author = None
            if raw_author_id not in (None, ""):
                try:
                    author = Author.objects.get(pk=int(raw_author_id))
                except (Author.DoesNotExist, TypeError, ValueError) as exc:
                    raise ValidationError(
                        {"authors": [f"Author id {raw_author_id} does not exist."]}
                    ) from exc
            else:
                first_names = " ".join(
                    str(author_data.get("first_names") or "").split()
                )
                last_names = " ".join(str(author_data.get("last_names") or "").split())
                author_type = author_data.get("author_type", "person")
                organization_name = " ".join(
                    str(author_data.get("organization_name") or "").split()
                )
                organization_abbreviation = " ".join(
                    str(author_data.get("organization_abbreviation") or "").split()
                )
                author = Author.objects.filter(
                    author_type=author_type,
                    first_names__iexact=first_names,
                    last_names__iexact=last_names,
                    organization_name__iexact=organization_name,
                ).first()
                if author is None:
                    if not owner.has_perm("bibliography.add_author"):
                        raise PermissionDenied(
                            "You need permission to create authors for source creation."
                        )
                    author = Author.objects.create(
                        owner=owner,
                        first_names=first_names,
                        last_names=last_names,
                        author_type=author_type,
                        organization_name=organization_name,
                        organization_abbreviation=organization_abbreviation,
                    )

            if author.pk not in author_ids:
                authors.append(author)
                author_ids.add(author.pk)

        return authors

    def create(self, validated_data):
        authors_data = validated_data.pop("authors", [])
        owner = getattr(self.context.get("request"), "user", None)
        authors = self._resolve_authors(owner, authors_data)
        source = Source.objects.create(
            owner=owner,
            type=validated_data.pop("type", Source._meta.get_field("type").default),
            **validated_data,
        )
        for position, author in enumerate(authors, start=1):
            SourceAuthor.objects.create(
                source=source,
                author=author,
                position=position,
            )
        return source


class SourceModelSerializer(ModelSerializer):
    authors = AuthorModelSerializer(many=True)
    licence = LicenceModelSerializer()

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

    def create(self, validated_data):
        authors_data = validated_data.pop("authors")
        licence_data = validated_data.pop("licence")
        licence = Licence.objects.create(**licence_data)
        source = Source.objects.create(licence=licence, **validated_data)
        for position, author_data in enumerate(authors_data):
            author, _ = Author.objects.get_or_create(**author_data)
            SourceAuthor.objects.create(
                source=source, author=author, position=position + 1
            )
        return source

    def update(self, instance, validated_data):
        authors_data = validated_data.pop("authors")
        licence_data = validated_data.pop("licence")

        Licence.objects.filter(id=instance.licence.id).update(**licence_data)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        instance.authors.clear()
        for position, author_data in enumerate(authors_data):
            author, _ = Author.objects.get_or_create(**author_data)
            SourceAuthor.objects.create(
                source=instance, author=author, position=position + 1
            )

        return instance


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
