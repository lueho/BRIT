import sys

from sources.greenhouses import models as source_models

sys.modules[__name__] = source_models
