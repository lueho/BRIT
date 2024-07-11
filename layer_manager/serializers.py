from rest_framework_gis.serializers import GeoFeatureModelSerializer

#
# class LocationGeoFeatureModelSerializer(GeoFeatureSerializer):
#     class Meta:
#         model = Layer
#         geo_field = 'geom'
#         fields = ('id', 'name', 'geom', 'address', 'description')
#
#     # get the fields from the field layer_fields of the Layer model
#
#     def get_fields(self):
#         fields = self.Meta.model.layer_fields
#         return fields
