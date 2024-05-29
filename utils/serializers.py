from collections import OrderedDict

from rest_framework.fields import SkipField
from rest_framework.relations import PKOnlyObject
from rest_framework.serializers import Serializer, ModelSerializer


class FieldLabelMixin(Serializer):
    field_labels_as_keys = False

    def __init__(self, *args, **kwargs):
        self.field_labels_as_keys = kwargs.pop('field_labels_as_keys', self.field_labels_as_keys)
        super().__init__(*args, **kwargs)

    def to_representation(self, instance):

        ret = OrderedDict()
        fields = self._readable_fields

        for field in fields:
            try:
                attribute = field.get_attribute(instance)
            except SkipField:
                continue

            # We skip `to_representation` for `None` values so that fields do
            # not have to explicitly deal with that case.
            #
            # For related fields with `use_pk_only_optimization` we need to
            # resolve the pk value.
            check_for_none = attribute.pk if isinstance(attribute, PKOnlyObject) else attribute
            key = field.label if self.field_labels_as_keys else field.field_name
            if check_for_none is None:
                ret[key] = None
            else:
                ret[key] = field.to_representation(attribute)

        return ret


class FieldLabelModelSerializer(FieldLabelMixin, ModelSerializer):
    """Renders output with defined labels instead of field names"""
