import sys

from sources.waste_collection import derived_values as source_derived_values

sys.modules[__name__] = source_derived_values
