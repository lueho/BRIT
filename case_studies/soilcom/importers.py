import sys

from sources.waste_collection import importers as source_importers

sys.modules[__name__] = source_importers
