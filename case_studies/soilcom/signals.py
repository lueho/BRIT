import sys

from sources.waste_collection import signals as source_signals

sys.modules[__name__] = source_signals
