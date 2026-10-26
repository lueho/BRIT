class ReadWriteSerializerViewSetMixin:
    """Use ``write_serializer_class`` for mutating actions.

    Set ``write_serializer_class`` alongside ``serializer_class``; create,
    update, and partial_update get the write serializer, all other actions
    fall back to the read serializer.
    """

    write_serializer_class = None
    write_actions = ("create", "update", "partial_update")

    def get_serializer_class(self):
        if (
            self.action in self.write_actions
            and self.write_serializer_class is not None
        ):
            return self.write_serializer_class
        return super().get_serializer_class()
