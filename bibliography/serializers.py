from collections import OrderedDict

from rest_framework.serializers import (ModelSerializer, HyperlinkedModelSerializer,
                                        SerializerMethodField)

from .models import Author, Licence, Source


class AuthorModelSerializer(ModelSerializer):
    class Meta:
        model = Author
        fields = ['id', 'first_names', 'middle_names', 'last_names', 'suffix', 'preferred_citation', 'bibtex_name',
                  'abbreviated_full_name']
        read_only_fields = ['bibtex_name', 'abbreviated_full_name']


class LicenceModelSerializer(ModelSerializer):
    class Meta:
        model = Licence
        fields = ['id', 'name', 'reference_url', 'description', 'bibtex_entry']
        read_only_fields = ['bibtex_entry']


class SourceModelSerializer(ModelSerializer):
    authors = AuthorModelSerializer(many=True)
    licence = LicenceModelSerializer()

    class Meta:
        model = Source
        fields = ['id', 'abbreviation', 'authors', 'title', 'type', 'licence', 'publisher', 'journal', 'issue', 'year',
                  'abstract', 'attributions', 'url', 'url_valid', 'url_checked', 'doi', 'last_accessed']
        read_only_fields = ['url_valid', 'url_checked', 'doi', 'last_accessed']

    def create(self, validated_data):
        authors_data = validated_data.pop('authors')
        licence_data = validated_data.pop('licence')
        licence = Licence.objects.create(**licence_data)
        source = Source.objects.create(licence=licence, **validated_data)
        for author_data in authors_data:
            author, _ = Author.objects.get_or_create(**author_data)
            source.authors.add(author)
        return source

    def update(self, instance, validated_data):
        authors_data = validated_data.pop('authors')
        licence_data = validated_data.pop('licence')

        Licence.objects.filter(id=instance.licence.id).update(**licence_data)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        instance.authors.clear()
        for author_data in authors_data:
            author, _ = Author.objects.get_or_create(**author_data)
            instance.authors.add(author)

        return instance


class HyperlinkedLicenceSerializer(HyperlinkedModelSerializer):
    class Meta:
        model = Licence
        fields = ('name', 'url')


class HyperlinkedAuthorSerializer(HyperlinkedModelSerializer):
    name = SerializerMethodField()

    class Meta:
        model = Author
        fields = ('name', 'url')

    @staticmethod
    def get_name(instance):
        return f'{instance.last_names}, {instance.first_names}'


class HyperlinkedSourceSerializer(HyperlinkedModelSerializer):
    authors = HyperlinkedAuthorSerializer(many=True)
    licence = HyperlinkedLicenceSerializer()
    url_checked = SerializerMethodField()
    doi = SerializerMethodField()
    last_accessed = SerializerMethodField()

    class Meta:
        model = Source
        fields = (
        'abbreviation', 'authors', 'title', 'type', 'licence', 'publisher', 'journal', 'issue', 'year', 'abstract',
        'attributions', 'url', 'url_valid', 'url_checked', 'doi', 'last_accessed')

    @staticmethod
    def get_url_checked(instance):
        return None if instance.url_checked is None else instance.url_checked.strftime('%d.%m.%Y')

    @staticmethod
    def get_last_accessed(instance):
        return None if instance.last_accessed is None else instance.last_accessed.strftime('%d.%m.%Y')

    @staticmethod
    def get_doi(instance):
        doi = None
        if instance.doi:
            doi = OrderedDict([
                ('name', instance.doi),
                ('url', f'https://doi.org/{instance.doi}')
            ])
        return doi


class SourceAbbreviationSerializer(ModelSerializer):
    class Meta:
        model = Source
        fields = ('pk', 'abbreviation')
