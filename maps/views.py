from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.gis.geos import MultiPolygon
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Subquery
from django.forms import formset_factory
from django.http import JsonResponse
from django.urls import NoReverseMatch, reverse, reverse_lazy
from django.views import View
from django.views.generic import TemplateView
from django.views.generic.edit import FormMixin
from django_filters.views import FilterView
from rest_framework.exceptions import NotFound, ParseError
from rest_framework.views import APIView, Response

from maps.serializers import (
    CatchmentGeoFeatureModelSerializer,
    LauRegionOptionSerializer,
    LauRegionSummarySerializer,
    MapConfigurationSerializer,
    NutsRegionCatchmentOptionSerializer,
    NutsRegionOptionSerializer,
    NutsRegionSummarySerializer,
    RegionGeoFeatureModelSerializer,
)
from utils.forms import TomSelectFormsetHelper
from utils.object_management.views import (
    CreateUserObjectMixin,
    OwnedObjectModelSelectOptionsView,
    PrivateObjectFilterView,
    PrivateObjectListView,
    PublishedObjectFilterView,
    PublishedObjectListView,
    ReviewObjectFilterView,
    UserCreatedObjectAutocompleteView,
    UserCreatedObjectCreateView,
    UserCreatedObjectDetailView,
    UserCreatedObjectModalCreateView,
    UserCreatedObjectModalDeleteView,
    UserCreatedObjectModalDetailView,
    UserCreatedObjectModalUpdateView,
    UserCreatedObjectUpdateView,
)

from .filters import (
    CatchmentFilterSet,
    GeoDataSetFilterSet,
    NutsRegionFilterSet,
    RegionFilterSet,
)
from .forms import (
    AttributeModalModelForm,
    AttributeModelForm,
    CatchmentCreateDrawCustomForm,
    CatchmentCreateMergeLauForm,
    CatchmentModelForm,
    GeoDataSetModelForm,
    LocationModelForm,
    RegionAttributeValueModalModelForm,
    RegionAttributeValueModelForm,
    RegionMergeForm,
    RegionMergeFormSet,
    RegionModelForm,
)
from .models import (
    Attribute,
    Catchment,
    GeoDataset,
    GeoPolygon,
    LauRegion,
    Location,
    MapConfiguration,
    ModelMapConfiguration,
    NutsRegion,
    Region,
    RegionAttributeValue,
)
from .signals import clear_geojson_cache_pattern


class MapMixin:
    """
    Mixin to add 'map_config' to the context.
    Retrieves MapConfiguration based on the view type and context.
    """

    map_config_related_name = "map_configuration"
    map_title = None
    model_name = None
    features_layer_api_basename = None
    api_prefix = "api-"
    api_geom_suffix = "-geojson"

    def get_map_title(self):
        """
        Retrieves the title of the map.
        Override this method in child classes for custom retrieval logic.
        """
        return self.map_title

    def get_catchment_feature_id(self):
        """Override to provide a custom catchment ID"""
        if hasattr(self, "object"):
            if hasattr(self.object, "catchment"):
                if isinstance(self.object.catchment, Catchment):
                    return self.object.catchment.id
        return None

    def get_region_feature_id(self):
        """Override to provide a custom region ID"""
        if hasattr(self, "object"):
            if hasattr(self.object, "region"):
                if isinstance(self.object.region, Region):
                    return self.object.region.id
        return None

    def get_features_feature_id(self):
        """Override to provide a custom feature ID"""
        return None

    def get_features_geometries_url(self):
        if self.features_layer_api_basename:
            try:
                return reverse(
                    f"{self.features_layer_api_basename}{self.api_geom_suffix}"
                )
            except NoReverseMatch:
                return None
        return None

    def get_features_layer_details_url_template(self):
        if self.features_layer_api_basename:
            try:
                template = (
                    reverse(
                        f"{self.features_layer_api_basename}-detail",
                        kwargs={"pk": None},
                    )
                    .replace("None", "")
                    .rstrip("/")
                    + "/"
                )
                return template
            except NoReverseMatch:
                return None
        return None

    def get_features_layer_summary_url(self):
        if self.features_layer_api_basename:
            try:
                return reverse(f"{self.features_layer_api_basename}-summaries")
            except NoReverseMatch:
                return None
        return None

    def get_map_configuration(self):
        """
        Retrieves the appropriate MapConfiguration instance.
        Override this method in child classes for custom retrieval logic.
        """

        # If the object has a MapConfiguration assigned to it by attribute, use it
        if hasattr(self, "object") and self.object:
            try:
                return getattr(self.object, self.map_config_related_name)
            except AttributeError:
                pass

        # If a model is given (e.g. in a DetailView), which has a MapConfiguration, use it
        if hasattr(self, "model") and self.model:
            self.model_name = self.model.__name__
            try:
                model_config = ModelMapConfiguration.objects.get(
                    model_name=self.model_name
                )
                return model_config.map_config
            except ModelMapConfiguration.DoesNotExist:
                pass

        # If the model is not explicitly given (e.g. in a FilterView), find the model based on the FilterSet
        if hasattr(self, "filterset_class") and self.filterset_class:
            self.model_name = self.filterset_class.Meta.model.__name__
            try:
                model_config = ModelMapConfiguration.objects.get(
                    model_name=self.model_name
                )
                return model_config.map_config
            except ModelMapConfiguration.DoesNotExist:
                pass

        # Alternatively, determine MapConfiguration based on request or other logic
        # For example, based on query parameters
        map_config_id = self.request.GET.get("map_config_id")
        if map_config_id:
            try:
                return MapConfiguration.objects.get(id=map_config_id)
            except MapConfiguration.DoesNotExist:
                pass

        # If no MapConfiguration is found, fall back to default. While the default has api_basenames for the region
        # and the catchment layer, the api_basename for the features layer is not set and needs to be found.

        # If the api_basename is not found via MapConfiguration instance and is not set explicitly but the view has a
        # model associated with it, try to find the API by naming convention.
        if not self.features_layer_api_basename and self.model_name:
            api_basename_candidate = f"{self.api_prefix}{self.model_name.lower()}"
            try:
                reverse(f"{api_basename_candidate}{self.api_geom_suffix}")
                self.features_layer_api_basename = api_basename_candidate
            except NoReverseMatch:
                pass

        return MapConfiguration.objects.get(name="Default Map Configuration")

    def get_override_params(self):
        params = {}

        # If any filter parameters besides the scope parameter are set, assume that features should be loaded
        if self.request.GET:
            if any(key not in ["scope"] for key in self.request.GET):
                params["load_features"] = True

        # Previous assumption can be overridden by explicitly setting the load_features parameter.
        for key in ["load_region", "load_catchment", "load_features"]:
            value = self.request.GET.get(key)
            if value:
                params[key] = value == "true"

        # In case no filter parameters are set, use the default load_<layer_type> values defined in the layer configurations.

        if self.get_region_feature_id():
            params["region_feature_id"] = self.get_region_feature_id()

        if self.get_catchment_feature_id():
            params["catchment_feature_id"] = self.get_catchment_feature_id()

        if self.get_features_feature_id():
            params["features_feature_id"] = self.get_features_feature_id()

        if self.get_features_geometries_url():
            params["features_geometries_url"] = self.get_features_geometries_url()

        if self.get_features_layer_details_url_template():
            params["features_layer_details_url_template"] = (
                self.get_features_layer_details_url_template()
            )

        if self.get_features_layer_summary_url():
            params["features_layer_summary_url"] = self.get_features_layer_summary_url()

        if hasattr(self, "object"):
            params["features_feature_id"] = getattr(self.object, "pk", None)

        return params

    def get_map_config_serialized(self):
        """
        Serializes the MapConfiguration instance.
        Returns JSON data or None if no MapConfiguration is found.
        """
        map_config = self.get_map_configuration()
        if map_config:
            serializer = MapConfigurationSerializer(
                map_config,
                context={
                    "request": self.request,
                    "override_params": self.get_override_params(),
                },
            )
            return serializer.data
        return None

    def post_process_map_config(self, map_config):
        """
        Override this method to post-process the map configuration before returning it.
        """
        if not map_config.get("regionId") or not map_config.get(
            "regionLayerGeometriesUrl"
        ):
            map_config["loadRegion"] = False
        if not map_config.get("catchmentId") or not map_config.get(
            "catchmentLayerGeometriesUrl"
        ):
            map_config["loadCatchment"] = False
        if not map_config.get("featuresLayerGeometriesUrl"):
            map_config["loadFeatures"] = False
        return map_config

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "map_title": self.get_map_title(),
                "map_config": self.post_process_map_config(
                    self.get_map_config_serialized()
                ),
            }
        )
        return context


class MapsDashboardView(TemplateView):
    template_name = "maps_dashboard.html"


# ----------- GeoDataSet CRUD ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class GeoDataSetPublishedFilterView(PublishedObjectFilterView):
    model = GeoDataset
    filterset_class = GeoDataSetFilterSet
    dashboard_url = reverse_lazy("maps-dashboard")


class GeoDataSetPrivateFilterView(PrivateObjectFilterView):
    model = GeoDataset
    filterset_class = GeoDataSetFilterSet
    dashboard_url = reverse_lazy("maps-dashboard")


class GeoDataSetFormMixin(FormMixin):
    filterset_class = None
    form_class = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "form": self.get_form(),
            }
        )
        return context

    def get_form(self, form_class=None):
        if self.form_class is not None:
            return self.form_class(**self.get_form_kwargs())
        if self.filterset_class is not None:
            return self.filterset_class(self.request.GET).form


class GeoDataSetCreateView(UserCreatedObjectCreateView):
    form_class = GeoDataSetModelForm
    permission_required = "maps.add_geodataset"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs


class FilteredMapMixin(MapMixin):
    model_name = None  # TODO: Remove this for pk
    template_name = "filtered_map.html"

    def get_dataset(self):
        try:
            return GeoDataset.objects.get(model_name=self.model_name)
        except GeoDataset.DoesNotExist as err:
            raise ImproperlyConfigured(
                f"No GeoDataset with model_name {self.model_name} found."
            ) from err

    def get_region_feature_id(self):
        return self.get_dataset().region_id

    def get_map_configuration(self):
        dataset = self.get_dataset()
        if dataset.map_configuration:
            return dataset.map_configuration
        else:
            return MapConfiguration.objects.get(name="Default Map Configuration")

    # def get_dataset(self):
    #     return GeoDataset.objects.get(pk=self.kwargs.get('pk')) # TODO: Implement this functionality

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Ensure a fast COUNT() is used rather than evaluating the queryset
        try:
            total_count = self.object_list.count()
        except Exception:
            total_count = None
        context.update(
            {
                "total_count": total_count,
            }
        )
        return context


class GeoDataSetPublishedFilteredMapView(FilteredMapMixin, PublishedObjectFilterView):
    paginate_by = None

    # TODO: Implement method to get the model, so that the create_url can be retrieved from the CRUDUrlsMixin
    def get_create_url(self):
        return None


class GeoDataSetReviewFilteredMapView(FilteredMapMixin, ReviewObjectFilterView):
    paginate_by = None

    # TODO: Implement method to get the model, so that the create_url can be retrieved from the CRUDUrlsMixin
    def get_create_url(self):
        return None


class GeoDataSetPrivateFilteredMapView(FilteredMapMixin, PrivateObjectFilterView):
    paginate_by = None

    # TODO: Implement method to get the model, so that the create_url can be retrieved from the CRUDUrlsMixin
    def get_create_url(self):
        return None


class GeoDataSetUpdateView(UserCreatedObjectUpdateView):
    model = GeoDataset
    form_class = GeoDataSetModelForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs


class GeoDataSetModalDeleteView(UserCreatedObjectModalDeleteView):
    model = GeoDataset


# ----------- GeoDataSet Utils -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class GeoDataSetAutocompleteView(UserCreatedObjectAutocompleteView):
    model = GeoDataset


# ----------- Location CRUD---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class LocationPublishedListView(PublishedObjectListView):
    model = Location
    dashboard_url = reverse_lazy("maps-dashboard")


class LocationPrivateListView(PrivateObjectListView):
    model = Location
    dashboard_url = reverse_lazy("maps-dashboard")


class LocationCreateView(UserCreatedObjectCreateView):
    form_class = LocationModelForm
    permission_required = "maps.add_location"


class LocationDetailView(MapMixin, UserCreatedObjectDetailView):
    model = Location


class LocationUpdateView(UserCreatedObjectUpdateView):
    model = Location
    form_class = LocationModelForm


class LocationModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Location


# ----------- Region CRUD-----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class RegionPublishedFilterView(PublishedObjectFilterView):
    model = Region
    filterset_class = RegionFilterSet
    dashboard_url = reverse_lazy("maps-dashboard")


class RegionPrivateFilterView(PrivateObjectFilterView):
    model = Region
    filterset_class = RegionFilterSet
    dashboard_url = reverse_lazy("maps-dashboard")


class RegionMapView(LoginRequiredMixin, MapMixin, FilterView):
    template_name = "region_map.html"
    filterset_class = RegionFilterSet
    map_title = "Regions"


class RegionDetailView(MapMixin, UserCreatedObjectDetailView):
    model = Region
    features_layer_api_basename = "api-region"

    def get_region_feature_id(self):
        return self.object.pk

    def get_override_params(self):
        params = super().get_override_params()
        params.pop("features_feature_id", None)

        show_composed = self.request.GET.get("show_composed_of") in {"1", "true"}
        if show_composed:
            params["load_features"] = True
            params["features_layer_style"] = {
                "color": "#f49a33",
                "weight": 2,
                "opacity": 1.0,
                "fillColor": "#f49a33",
                "fillOpacity": 0.0,
                "dashArray": "6, 6",
                "lineCap": "round",
                "lineJoin": "round",
                "fillRule": "evenodd",
                "className": "",
                "radius": 3,
            }
        else:
            params["load_features"] = False

        return params

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["show_composed_of"] = self.request.GET.get("show_composed_of") in {
            "1",
            "true",
        }
        return context

    def post_process_map_config(self, map_config):
        map_config = super().post_process_map_config(map_config)
        show_composed = self.request.GET.get("show_composed_of") in {"1", "true"}
        map_config["showComposedOf"] = show_composed
        if show_composed:
            map_config["composedOfRegionId"] = self.object.pk
        return map_config


class RegionCreateView(UserCreatedObjectCreateView):
    form_class = RegionModelForm
    permission_required = "maps.add_region"


class RegionUpdateView(UserCreatedObjectUpdateView):
    model = Region
    form_class = RegionModelForm


class RegionModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Region


# ----------- Catchment CRUD--------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CatchmentPublishedFilterView(PublishedObjectFilterView):
    model = Catchment
    filterset_class = CatchmentFilterSet
    dashboard_url = reverse_lazy("maps-dashboard")


class CatchmentPrivateFilterView(PrivateObjectFilterView):
    model = Catchment
    filterset_class = CatchmentFilterSet
    dashboard_url = reverse_lazy("maps-dashboard")


class CatchmentDetailView(MapMixin, UserCreatedObjectDetailView):
    model = Catchment


class CatchmentCreateView(CreateUserObjectMixin, TemplateView):
    template_name = "catchment_create_method_select.html"
    permission_required = "maps.add_catchment"


class CatchmentCreateSelectRegionView(UserCreatedObjectCreateView):
    template_name = "maps/catchment_form.html"
    form_class = CatchmentModelForm
    permission_required = "maps.add_catchment"


class CatchmentCreateDrawCustomView(UserCreatedObjectCreateView):
    template_name = "catchment_draw_form.html"
    form_class = CatchmentCreateDrawCustomForm
    permission_required = "maps.add_catchment"


class CatchmentCreateMergeLauView(UserCreatedObjectCreateView):
    template_name = "catchment_merge_formset.html"
    form = None
    form_class = CatchmentCreateMergeLauForm
    formset = None
    formset_model = Region
    formset_class = RegionMergeFormSet
    formset_form_class = RegionMergeForm
    formset_helper_class = TomSelectFormsetHelper
    formset_factory_kwargs = {"extra": 2}
    permission_required = "maps.add_catchment"

    def get_formset_kwargs(self, **kwargs):
        if self.request.method in ("POST", "PUT"):
            kwargs.update({"data": self.request.POST.copy()})
        return kwargs

    def get_formset(self):
        FormSet = formset_factory(
            self.formset_form_class,
            formset=self.formset_class,
            **self.formset_factory_kwargs,
        )
        return FormSet(**self.get_formset_kwargs())

    def get_region_name(self):
        # The region will get the same custom name as the catchment
        if self.object:
            return self.object.name
        return None

    def create_region_borders(self):
        geoms = [
            form.get("region").borders.geom
            for form in self.formset.cleaned_data
            if form.get("region") is not None
        ]
        new_geom = geoms[0]
        for geom in geoms[1:]:
            new_geom = new_geom.union(geom)
        new_geom.normalize()
        if not isinstance(new_geom, MultiPolygon):
            new_geom = MultiPolygon(new_geom)
        return GeoPolygon.objects.create(geom=new_geom)

    def get_region(self):
        return Region.objects.create(
            name=self.get_region_name(), borders=self.create_region_borders()
        )

    def get_context_data(self, **kwargs):
        if "formset" not in kwargs:
            kwargs["formset"] = self.get_formset()
        kwargs["formset_helper"] = self.formset_helper_class()
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        self.formset = self.get_formset()
        if not self.formset.is_valid():
            return self.form_invalid(form)
        with transaction.atomic():
            response = super().form_valid(form)
            self.object.region = self.get_region()
            self.object.type = "custom"
            self.object.save()
        return response


class CatchmentUpdateView(UserCreatedObjectUpdateView):
    model = Catchment
    form_class = CatchmentModelForm


class CatchmentModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Catchment


# ----------- Catchment utilities---------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CatchmentAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Catchment
    geodataset_model_name = None

    def get_region(self):
        return GeoDataset.objects.get(model_name=self.geodataset_model_name).region

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.geodataset_model_name:
            queryset = queryset.filter(
                region__borders__geom__within=self.get_region().geom
            )
        return queryset


# ----------- Region Utils ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class RegionAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Region


class NutsRegionAutocompleteView(UserCreatedObjectAutocompleteView):
    model = NutsRegion
    search_lookups = ["region_ptr", "name_latn__icontains", "levl_code__icontains"]
    value_fields = ["id", "name_latn", "levl_code", "parent_id", "nuts_id"]

    def apply_filters(self, queryset):
        # Check for ancestor filtering (nuts_id prefix matching)
        # When ancestor is provided, skip the standard filter_by (parent_id) logic
        # since we're filtering by ancestor instead of immediate parent
        ancestor_nuts_id = self.request.GET.get("ancestor")
        if ancestor_nuts_id:
            return queryset.filter(nuts_id__startswith=ancestor_nuts_id)

        if not self.filter_by and not self.exclude_by:
            return queryset

        if self.filter_by:
            import urllib.parse

            lookup, value = (
                urllib.parse.unquote(self.filter_by).replace("'", "").split("=")
            )
            # Only apply parent_id filter if a value is provided
            if value:
                dependent_field, dependent_field_lookup = lookup.split("__")
                levl_code = int(dependent_field.split("_")[-1]) + 1
                filter_dict = {"levl_code": levl_code, "parent_id": value}
                queryset = queryset.filter(**filter_dict)

        return queryset


class NutsRegionLevel0AutocompleteView(NutsRegionAutocompleteView):
    def hook_queryset(self, queryset):
        return queryset.filter(levl_code=0)


class NutsRegionLevel1AutocompleteView(NutsRegionAutocompleteView):
    def hook_queryset(self, queryset):
        return queryset.filter(levl_code=1)


class NutsRegionLevel2AutocompleteView(NutsRegionAutocompleteView):
    def hook_queryset(self, queryset):
        return queryset.filter(levl_code=2)


class NutsRegionLevel3AutocompleteView(NutsRegionAutocompleteView):
    def hook_queryset(self, queryset):
        return queryset.filter(levl_code=3)


class RegionOfLauAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Region
    search_lookups = ["name__icontains", "lauregion__lau_id__contains"]
    value_fields = ["name", "lauregion__lau_id", "lauregion__lau_name"]

    def hook_queryset(self, queryset):
        """
        Filter Regions to only show those that have a corresponding LAU Region.
        """
        return queryset.filter(pk__in=Subquery(LauRegion.objects.all().values("pk")))

    def hook_prepare_results(self, results):
        """
        Customize the display label to include the LAU ID code, similar to
        LauRegion.__str__ method: f"{self.lau_name} ({self.lau_id})"
        """
        for item in results:
            # Get the LAU ID from the related LauRegion object
            lau_id = item.get("lauregion__lau_id")
            lau_name = item.get("lauregion__lau_name")
            item["text"] = f"{lau_name} ({lau_id})"
        return results


class CatchmentOptionGeometryAPI(APIView):
    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request):
        """Return GeoJSON for catchment options.

        If a ``parent_id`` query parameter is provided, the endpoint returns all
        child catchments of the parent catchment's region. Otherwise it returns
        *all* catchments.
        """
        qs = Catchment.objects.select_related("region", "region__borders").all()

        parent_id = request.query_params.get("parent_id")
        if parent_id is not None:
            try:
                parent_catchment = Catchment.objects.get(pk=parent_id)
            except Catchment.DoesNotExist:
                return JsonResponse(
                    {"detail": "Parent catchment not found."}, status=404
                )
            parent_region = parent_catchment.region
            # Keep select_related for serializer geometry access
            qs = parent_region.child_catchments.select_related(
                "region", "region__borders"
            ).all()

        serializer = CatchmentGeoFeatureModelSerializer(qs, many=True)
        return JsonResponse({"geoJson": serializer.data})


# ----------- NutsRegions ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CatchmentRegionGeometryAPI(APIView):
    """
    Similar to RegionGeometryAPI. Instead of taking the id of the requested region, this takes a catchment id as input
    and returns the geometry of the associated Region.
    """

    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request, *args, **kwargs):
        if "pk" in request.query_params:
            # select_related needed for geometry serialization
            catchment = Catchment.objects.select_related(
                "region", "region__borders"
            ).get(pk=request.query_params.get("pk"))
            regions = Region.objects.select_related("borders").filter(
                catchment=catchment
            )
            serializer = RegionGeoFeatureModelSerializer(regions, many=True)
            return JsonResponse({"geoJson": serializer.data})

        return JsonResponse({})


class CatchmentRegionSummaryAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request, *args, **kwargs):
        if "pk" in request.query_params:
            catchment = Catchment.objects.get(pk=request.query_params.get("pk"))
            try:
                region = catchment.region.nutsregion
                serializer = NutsRegionSummarySerializer(
                    region, field_labels_as_keys=True, context={"request": request}
                )
                return Response({"summaries": [serializer.data]})
            except Region.nutsregion.RelatedObjectDoesNotExist:
                pass

            try:
                region = catchment.region.lauregion
                serializer = LauRegionSummarySerializer(
                    region, field_labels_as_keys=True, context={"request": request}
                )
                return Response({"summaries": [serializer.data]})
            except Region.nutsregion.RelatedObjectDoesNotExist:
                pass

        return Response({})


# ----------- NUTS Map -------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class NutsRegionPublishedMapView(GeoDataSetPublishedFilteredMapView):
    model = NutsRegion
    model_name = "NutsRegion"
    template_name = "nuts_region_map.html"
    filterset_class = NutsRegionFilterSet
    features_layer_api_basename = "api-nuts-region"
    map_title = "NUTS Regions"


class NutsRegionPedigreeAPI(APIView):
    """
    This API is used to reduce options in select widgets of filters. It returns only the ID and name of the
    region and not the geometry.
    """

    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request):
        if "id" not in request.query_params:
            raise ParseError(
                'Query parameter "id" missing. Must provide valid id of NUTS region.'
            )

        if "direction" not in request.query_params or request.query_params[
            "direction"
        ] not in ("children", "parents"):
            raise ParseError(
                'Missing or wrong query parameter "direction". Options: "parents", "children"'
            )

        try:
            instance = NutsRegion.objects.get(id=request.query_params["id"])
        except AttributeError as err:
            raise NotFound(
                "A NUTS region with the provided id does not exist."
            ) from err
        except NutsRegion.DoesNotExist as err:
            raise NotFound(
                "A NUTS region with the provided id does not exist."
            ) from err

        data = {}

        if request.query_params["direction"] == "children":
            for lvl in range(instance.levl_code + 1, 4):
                qs = NutsRegion.objects.filter(
                    levl_code=lvl, nuts_id__startswith=instance.nuts_id
                )
                serializer = NutsRegionOptionSerializer(qs, many=True)
                data[f"id_level_{lvl}"] = serializer.data

        if request.query_params["direction"] == "parents":
            for lvl in range(instance.levl_code - 1, -1, -1):
                instance = instance.parent
                serializer = NutsRegionOptionSerializer(instance)
                data[f"id_level_{lvl}"] = serializer.data

        return Response(data)


class NutsAndLauCatchmentPedigreeAPI(APIView):
    """
    This API is used to reduce options in select widgets of filters. It returns only the ID and name of the
    region and not the geometry.
    """

    authentication_classes = []
    permission_classes = []

    @staticmethod
    def get(request):
        if "id" not in request.query_params:
            raise ParseError(
                'Query parameter "id" missing. Must provide valid catchment id.'
            )

        if "direction" not in request.query_params or request.query_params[
            "direction"
        ] not in ("children", "parents"):
            raise ParseError(
                'Missing or wrong query parameter "direction". Options: "parents", "children"'
            )

        try:
            catchment = Catchment.objects.get(id=request.query_params["id"])
            instance = catchment.region.nutsregion
        except AttributeError as err:
            raise NotFound(
                "A NUTS region with the provided id does not exist."
            ) from err
        except Catchment.DoesNotExist as err:
            raise NotFound(
                "A NUTS region with the provided id does not exist."
            ) from err

        data = {}

        if request.query_params["direction"] == "children":
            for lvl in range(instance.levl_code + 1, 4):
                # Prefetch needed: serializer accesses region_ptr.catchment_set in get_id
                qs = NutsRegion.objects.filter(
                    levl_code=lvl, nuts_id__startswith=instance.nuts_id
                ).prefetch_related("region_ptr__catchment_set")
                serializer = NutsRegionCatchmentOptionSerializer(qs, many=True)
                data[f"id_level_{lvl}"] = serializer.data
            data["id_level_4"] = []
            if instance.levl_code == 3:
                # Prefetch needed: serializer accesses region_ptr.catchment_set
                qs = LauRegion.objects.filter(nuts_parent=instance).prefetch_related(
                    "region_ptr__catchment_set"
                )
                serializer = LauRegionOptionSerializer(qs, many=True)
                data["id_level_4"] = serializer.data

        if request.query_params["direction"] == "parents":
            for lvl in range(instance.levl_code - 1, -1, -1):
                instance = instance.parent
                serializer = NutsRegionCatchmentOptionSerializer(instance)
                data[f"id_level_{lvl}"] = serializer.data

        return Response(data)


# ----------- Attribute CRUD -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AttributePublishedListView(PublishedObjectListView):
    model = Attribute
    dashboard_url = reverse_lazy("maps-dashboard")


class AttributePrivateListView(PrivateObjectListView):
    model = Attribute
    dashboard_url = reverse_lazy("maps-dashboard")


class AttributeCreateView(UserCreatedObjectCreateView):
    form_class = AttributeModelForm
    success_url = reverse_lazy("attribute-list")
    permission_required = "maps.add_attribute"


class AttributeModalCreateView(UserCreatedObjectModalCreateView):
    form_class = AttributeModalModelForm
    success_url = reverse_lazy("attribute-list")
    permission_required = "maps.add_attribute"


class AttributeDetailView(UserCreatedObjectDetailView):
    template_name = "attribute_detail.html"
    model = Attribute


class AttributeModalDetailView(UserCreatedObjectModalDetailView):
    model = Attribute


class AttributeUpdateView(UserCreatedObjectUpdateView):
    model = Attribute
    form_class = AttributeModelForm


class AttributeModalUpdateView(UserCreatedObjectModalUpdateView):
    model = Attribute
    form_class = AttributeModalModelForm


class AttributeModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Attribute


# ----------- Region Attribute Value CRUD ------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class RegionAttributeValueCreateView(UserCreatedObjectCreateView):
    form_class = RegionAttributeValueModelForm
    permission_required = "maps.add_regionattributevalue"


class RegionAttributeValueModalCreateView(UserCreatedObjectModalCreateView):
    form_class = RegionAttributeValueModalModelForm
    permission_required = "maps.add_regionattributevalue"


class RegionAttributeValueDetailView(UserCreatedObjectDetailView):
    model = RegionAttributeValue


class RegionAttributeValueModalDetailView(UserCreatedObjectModalDetailView):
    model = RegionAttributeValue


class RegionAttributeValueUpdateView(UserCreatedObjectUpdateView):
    model = RegionAttributeValue
    form_class = RegionAttributeValueModelForm


class RegionAttributeValueModalUpdateView(UserCreatedObjectModalUpdateView):
    model = RegionAttributeValue
    form_class = RegionAttributeValueModalModelForm


class RegionAttributeValueModalDeleteView(UserCreatedObjectModalDeleteView):
    model = RegionAttributeValue

    def get_success_url(self):
        return reverse("region-detail", kwargs={"pk": self.object.region.pk})


class RegionChildCatchmentOptions(OwnedObjectModelSelectOptionsView):
    model = Catchment


class ClearGeojsonCacheView(UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_staff

    def get(self, request, *args, **kwargs):
        pattern = request.GET.get("pattern", "*")
        clear_geojson_cache_pattern(pattern)
        return JsonResponse(
            {"status": "success", "message": f"Cache cleared with pattern: {pattern}"}
        )
