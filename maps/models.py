from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db.models import MultiPolygonField, PointField
from django.contrib.gis.geos import GEOSGeometry
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models, transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.urls import NoReverseMatch, reverse
from tree_queries.models import TreeNode
from tree_queries.query import TreeQuerySet

from bibliography.models import Source
from utils.object_management.models import (
    NamedUserCreatedObject,
    UserCreatedObjectQuerySet,
)

TYPES = (
    ("administrative", "administrative"),
    ("custom", "custom"),
    ("nuts", "nuts"),
    ("lau", "lau"),
)

GIS_SOURCE_MODELS = (
    ("HamburgRoadsideTrees", "HamburgRoadsideTrees"),
    ("HamburgGreenAreas", "HamburgGreenAreas"),
    ("NantesGreenhouses", "NantesGreenhouses"),
    ("NutsRegion", "NutsRegion"),
    ("WasteCollection", "WasteCollection"),
)

LAYER_TYPE_CHOICES = [
    ("region", "Region"),
    ("catchment", "Catchment"),
    ("features", "Features"),
]

LINE_CAP_CHOICES = [
    ("butt", "Butt"),
    ("round", "Round"),
    ("square", "Square"),
]

LINE_JOIN_CHOICES = [
    ("miter", "Miter"),
    ("round", "Round"),
    ("bevel", "Bevel"),
]

FILL_RULE_CHOICES = [
    ("evenodd", "Even-Odd"),
    ("nonzero", "Non-Zero"),
]

HEX_COLOR_REGEX = RegexValidator(
    regex=r"^#(?:[0-9a-fA-F]{3}){1,2}$", message="Enter a valid hex color code."
)


class MapLayerStyle(NamedUserCreatedObject):
    stroke = models.BooleanField(
        default=True, help_text="If False, the layer will not have a stroke."
    )
    color = models.CharField(
        max_length=7,
        default="#3388ff",
        validators=[HEX_COLOR_REGEX],
        help_text="Stroke color for the layer in hexadecimal format.",
    )
    weight = models.PositiveIntegerField(default=3, help_text="Stroke width in pixels.")
    opacity = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Stroke opacity, between 0 and 1.",
    )
    fill = models.BooleanField(
        default=True, help_text="If False, the layer will not have a fill."
    )
    fill_color = models.CharField(
        max_length=7,
        blank=True,
        validators=[HEX_COLOR_REGEX],
        help_text="Fill color for the layer in hexadecimal format.",
    )
    fill_opacity = models.FloatField(
        default=0.2,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Fill opacity, between 0 and 1.",
    )
    dash_array = models.CharField(
        max_length=50,
        blank=True,
        help_text="Define the stroke dash pattern, e.g., '5, 10'.",
    )
    dash_offset = models.CharField(
        max_length=50, blank=True, help_text="Define the stroke dash offset."
    )
    line_cap = models.CharField(
        max_length=10,
        choices=LINE_CAP_CHOICES,
        default="round",
        help_text="Shape to be used at the end of the stroke.",
    )
    line_join = models.CharField(
        max_length=10,
        choices=LINE_JOIN_CHOICES,
        default="round",
        help_text="Shape to be used at the joints between segments.",
    )
    fill_rule = models.CharField(
        max_length=10,
        choices=FILL_RULE_CHOICES,
        default="evenodd",
        help_text="Rule used to determine if a point is inside the path.",
    )
    class_name = models.CharField(
        max_length=50,
        blank=True,
        help_text="CSS class name(s) to add to the layer for additional styling.",
    )
    radius = models.FloatField(
        default=10.0, help_text="Radius of the circle marker in pixels."
    )
    bubbling_mouse_events = models.BooleanField(
        default=True,
        help_text="When true, a mouse event on this path will trigger the same event on the map.",
    )


def get_default_layer_style(layer_type):
    default_style_names = {
        "region": "Default Region Layer Style",
        "catchment": "Default Catchment Layer Style",
        "features": "Default Features Layer Style",
    }

    style_name = default_style_names.get(layer_type, "Default Style")

    style, created = MapLayerStyle.objects.get_or_create(
        name=style_name,
        defaults={
            "stroke": True,
            "color": "#000000",
            "weight": 3,
            "opacity": 1.0,
            "fill": True,
            "fill_color": "#FFFFFF",
            "fill_opacity": 0.2,
            "dash_array": "",
            "dash_offset": "",
            "line_cap": "round",
            "line_join": "round",
            "fill_rule": "evenodd",
            "class_name": "",
            "radius": 10.0,
            "bubbling_mouse_events": True,
        },
    )
    return style


class MapLayerConfiguration(NamedUserCreatedObject):
    layer_type = models.CharField(
        max_length=50,
        choices=LAYER_TYPE_CHOICES,
        help_text="Type of the layer (region, catchment, feature).",
    )
    load_layer = models.BooleanField(
        default=True,
        help_text="If False, the dataset will not be loaded initially to avoid long loading times.",
    )
    feature_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Unique identifier for the feature if fixed.",
    )
    style = models.ForeignKey(
        MapLayerStyle,
        on_delete=models.PROTECT,
        related_name="layer_configurations",
        help_text="Styling information for the layer.",
    )

    api_basename = models.CharField(
        max_length=255,
        blank=True,
        help_text="Base name for API used to derive endpoint urls for geometries, details and summaries",
    )

    def get_geometries_url(self):
        if self.api_basename:
            try:
                return reverse(f"{self.api_basename}-geojson").rstrip("/") + "/"
            except NoReverseMatch:
                return None
        return None

    def get_features_layer_details_url_template(self):
        if self.api_basename:
            try:
                template = (
                    reverse(f"{self.api_basename}-detail", kwargs={"pk": None})
                    .replace("None", "")
                    .rstrip("/")
                    + "/"
                )
                return template
            except NoReverseMatch:
                return None
        return None

    def get_layer_summary_url(self):
        if self.api_basename:
            try:
                return reverse(f"{self.api_basename}-summaries")
            except NoReverseMatch:
                return None
        return None


@receiver(pre_save, sender=MapLayerConfiguration)
def assign_default_layer_style(sender, instance, **kwargs):
    if not instance.style_id:
        with transaction.atomic():
            instance.style = get_default_layer_style(instance.layer_type)


class MapConfiguration(NamedUserCreatedObject):
    layers = models.ManyToManyField(
        MapLayerConfiguration,
        related_name="map_configurations",
        help_text="Layers associated with this map configuration.",
    )
    adjust_bounds_to_layer = models.CharField(
        max_length=50,
        choices=LAYER_TYPE_CHOICES,
        default="region",
        help_text="Layer to which the map bounds should be adjusted.",
    )
    apply_filter_to_features = models.BooleanField(default=False)
    load_features_layer_summary = models.BooleanField(default=False)


def get_model_choices():
    from django.apps import apps

    existing_models = apps.get_models()
    return [
        (model.__name__, f"{model._meta.app_label}.{model.__name__}")
        for model in existing_models
        if not model._meta.abstract
    ]


class ModelMapConfiguration(models.Model):
    model_name = models.CharField(
        max_length=100, unique=True, choices=get_model_choices
    )
    map_config = models.ForeignKey(
        "MapConfiguration",
        on_delete=models.CASCADE,
        related_name="model_map_configurations",
    )

    class Meta:
        ordering = ["model_name"]


class Location(NamedUserCreatedObject):
    geom = PointField(null=True)
    address = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = "Location"

    def __str__(self):
        return f"{self.name}{' at ' + self.address if self.address else ''}"


class GeoPolygon(models.Model):
    fid = models.BigAutoField(primary_key=True)
    geom = MultiPolygonField(blank=True, null=True)


class Region(NamedUserCreatedObject):
    country = models.CharField(max_length=56, null=False)
    borders = models.ForeignKey(GeoPolygon, on_delete=models.PROTECT, null=True)
    composed_of = models.ManyToManyField(
        "self", symmetrical=False, related_name="composing_regions", blank=True
    )

    @property
    def geom(self):
        """Gets the geometry from the associated GeoPolygon."""
        if self.borders:
            return self.borders.geom
        return None  # Return None if no borders are associated

    @geom.setter
    def geom(self, value):
        """
        Sets the geometry.

        If a GeoPolygon is already associated via 'borders', its geometry is updated.
        If no GeoPolygon is associated, a new one is created and linked.
        The associated GeoPolygon instance (new or existing) is saved.
        Note: Saving the Region instance itself might be required afterwards
              by the caller to persist the foreign key link if it was newly created.
        """
        if self.borders is None:
            # Create a new GeoPolygon if one doesn't exist for this Region
            new_geo_poly = GeoPolygon.objects.create(geom=value)
            self.borders = new_geo_poly
            # Important: The caller might need to call region_instance.save()
            # after setting the geom property if the region instance wasn't
            # already saved or if the 'borders' FK needs to be persisted.
        else:
            # Update the geometry of the existing GeoPolygon
            self.borders.geom = value
            self.borders.save()  # Save the changes to the GeoPolygon instance

    def __str__(self):
        return f"{self.name or 'Unnamed Region'} ({self.country})"

    @property
    def country_code(self):
        try:
            return self.nutsregion.cntr_code
        except Region.nutsregion.RelatedObjectDoesNotExist:
            pass
        try:
            return self.lauregion.cntr_code
        except Region.lauregion.RelatedObjectDoesNotExist:
            return None

    @property
    def nuts_or_lau_id(self):
        try:
            return self.nutsregion.nuts_id
        except Region.nutsregion.RelatedObjectDoesNotExist:
            pass
        try:
            return self.lauregion.lau_id
        except Region.lauregion.RelatedObjectDoesNotExist:
            return None

    def __str__(self):
        try:
            return self.nutsregion.__str__()
        except Region.nutsregion.RelatedObjectDoesNotExist:
            pass
        try:
            return self.lauregion.__str__()
        except Region.lauregion.RelatedObjectDoesNotExist:
            return self.name


@receiver(post_save, sender=Region)
def set_country(sender, instance, created, **kwargs):
    if not created:
        return

    if instance.country_code:
        instance.country = instance.country_code
        instance.save(update_fields=["country"])
    elif instance.borders and instance.borders.geom:
        # Buffer the region’s geometry by the tolerance.
        buffered_geom = instance.borders.geom.buffer(-settings.GEO_BORDER_TOLERANCE)
        # Look for a candidate country (NutsRegion with levl_code=0) whose borders contain the buffered geometry.
        candidate = NutsRegion.objects.filter(
            levl_code=0, borders__geom__contains=buffered_geom
        ).first()
        if candidate and candidate.cntr_code:
            instance.country = candidate.cntr_code
            instance.save(update_fields=["country"])


class NutsRegion(Region):
    nuts_id = models.CharField(max_length=5, blank=True, null=True)
    levl_code = models.IntegerField(blank=True, null=True)
    cntr_code = models.CharField(max_length=2, blank=True, null=True)
    name_latn = models.CharField(max_length=70, blank=True, null=True)
    nuts_name = models.CharField(max_length=106, blank=True, null=True)
    mount_type = models.IntegerField(blank=True, null=True)
    urbn_type = models.IntegerField(blank=True, null=True)
    coast_type = models.IntegerField(blank=True, null=True)
    parent = models.ForeignKey(
        "self", related_name="children", on_delete=models.PROTECT, null=True
    )

    @property
    def pedigree(self):
        pedigree = {}

        # add parents
        instance = self
        for lvl in range(self.levl_code, -1, -1):
            pedigree[f"qs_{lvl}"] = NutsRegion.objects.filter(id=instance.id)
            instance = instance.parent

        # add children
        for lvl in range(self.levl_code + 1, 4):
            pedigree[f"qs_{lvl}"] = NutsRegion.objects.filter(
                levl_code=lvl, nuts_id__startswith=self.nuts_id
            )
        if self.levl_code == 3:
            pedigree[f"qs_4"] = self.lau_children.all()

        return pedigree

    def __str__(self):
        return f"{self.nuts_name} ({self.nuts_id})"


class LauRegion(Region):
    cntr_code = models.CharField(max_length=2, blank=True, null=True)
    lau_id = models.CharField(max_length=13, blank=True, null=True)
    lau_name = models.CharField(max_length=113, blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    nuts_parent = models.ForeignKey(
        NutsRegion, related_name="lau_children", on_delete=models.PROTECT, null=True
    )

    def __str__(self):
        return f"{self.lau_name} ({self.lau_id})"


class CatchmentQueryset(UserCreatedObjectQuerySet, TreeQuerySet):
    pass


class CatchmentManager(models.Manager):
    def get_queryset(self):
        return CatchmentQueryset(self.model, using=self._db)

    def descendants(self, *args, **kwargs):
        return self.get_queryset().descendants(*args, **kwargs)

    def ancestors(self, *args, **kwargs):
        return self.get_queryset().ancestors(*args, **kwargs)


class Catchment(NamedUserCreatedObject, TreeNode):
    parent_region = models.ForeignKey(
        Region, on_delete=models.CASCADE, related_name="child_catchments", null=True
    )
    region = models.ForeignKey(Region, on_delete=models.CASCADE, null=True)
    type = models.CharField(max_length=14, choices=TYPES, default="custom")

    objects = CatchmentManager()

    @property
    def geom(self) -> GEOSGeometry | None:
        if self.region:
            return self.region.geom
        return None

    @geom.setter
    def geom(self, value: GEOSGeometry | None):  # Added type hint
        """
        Sets the geometry on the associated Region.

        This acts as a shortcut to set the geometry of the Region instance
        linked via the 'region' field.

        Raises:
            AttributeError: If this Catchment instance is not associated
                            with a Region (self.region is None).
        """
        if self.region is None:
            raise AttributeError(
                "Cannot set geometry: Catchment must be associated with a Region first."
            )
        else:
            # Delegate to the Region's geom property setter.
            # The Region's setter handles creating/updating the GeoPolygon
            # and saving the GeoPolygon instance.
            self.region.geom = value
            # Note: Saving the Catchment instance itself is not necessary, as no fields from Catchment are changed.
            # However, if the Region's setter modified the Region instance
            # (e.g., setting 'borders' FK for the first time), the *Region*
            # instance might need saving by the caller if the setter doesn't do it.
            # (The current Region setter only saves the GeoPolygon, not the Region itself).

    @property
    def level(self):
        if hasattr(self.region, "nutsregion"):
            return self.region.nutsregion.levl_code
        if hasattr(self.region, "lauregion"):
            return 4

    def __str__(self):
        return self.name if self.name else self.region.__str__()


@receiver(post_delete, sender=Catchment)
def delete_unused_custom_region(sender, instance, **kwargs):
    if not instance.region.catchment_set.exists() and instance.type == "custom":
        instance.region.delete()


class GeoDataset(NamedUserCreatedObject):
    """
    Holds meta information about datasets from the core module or scenario extensions.
    """

    preview = models.ImageField(upload_to="maps_geodataset/", default="generic_map.png")
    publish = models.BooleanField(default=False)
    region = models.ForeignKey(
        Region, on_delete=models.CASCADE, null=False, related_name="geodatasets"
    )
    model_name = models.CharField(
        max_length=56, choices=GIS_SOURCE_MODELS, null=True
    )  # TODO remove when switch to generic view is done
    sources = models.ManyToManyField(Source, related_name="geodatasets")
    data_content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True
    )
    data_object_id = models.PositiveIntegerField(null=True)
    data_object = GenericForeignKey("data_content_type", "data_object_id")
    map_configuration = models.ForeignKey(
        MapConfiguration,
        on_delete=models.PROTECT,
        null=True,
        related_name="geodatasets",
    )

    def get_absolute_url(self):
        return reverse(f"{self.model_name}")


# TODO: Check if this should be moved to utils app
class Attribute(NamedUserCreatedObject):
    """
    Defines an attribute class that can be attached to features of a map.
    """

    unit = models.CharField(max_length=127)

    def __str__(self):
        return f"{self.name} [{self.unit}]"


class RegionAttributeValue(NamedUserCreatedObject):
    """
    Attaches a value of an attribute class to a region
    """

    region = models.ForeignKey(Region, on_delete=models.PROTECT)
    attribute = models.ForeignKey(Attribute, on_delete=models.PROTECT)
    date = models.DateField(blank=True, null=True)
    value = models.FloatField(default=0.0)
    standard_deviation = models.FloatField(default=0.0, blank=True, null=True)

    def get_absolute_url(self):
        return reverse("region-detail", args=[self.region.pk])


class RegionAttributeTextValue(NamedUserCreatedObject):
    """
    Attaches a category value of an attribute class to a region
    """

    region = models.ForeignKey(Region, on_delete=models.PROTECT)
    attribute = models.ForeignKey(Attribute, on_delete=models.PROTECT)
    date = models.DateField(blank=True, null=True)
    value = models.CharField(max_length=511)
