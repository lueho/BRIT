class CanonicalRelationTestMixin:
    """Mixin providing tests for canonical component/property relations."""

    canonical_attr = "canonical_component"
    comparable_attr = "comparable_component"

    def _test_canonical_defaults_to_self(self, model_class, **create_kwargs):
        """Test that canonical relation defaults to self when not set."""
        obj = model_class.objects.create(**create_kwargs)
        self.assertEqual(getattr(obj, self.canonical_attr), obj)

    def _test_canonical_follows_comparable(self, model_class, **create_kwargs):
        """Test that canonical relation follows comparable_component/property."""
        canonical = model_class.objects.create(name="Canonical", **create_kwargs)
        alias = model_class.objects.create(
            name="Alias",
            **{self.comparable_attr: canonical},
            **create_kwargs,
        )
        self.assertEqual(getattr(alias, self.canonical_attr), canonical)
