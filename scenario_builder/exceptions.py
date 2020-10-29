class EmptyQueryset(Exception):
    """The Queryset cannot be empty"""


class BlockedRunningScenario(Exception):
    """The scenario cannot be edited, while it is being evaluated."""
