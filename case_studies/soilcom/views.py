import sys

from sources.waste_collection import views as source_views

sys.modules[__name__] = source_views
