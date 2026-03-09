import sys

from sources.waste_collection import models as source_models

sys.modules[__name__] = source_models
