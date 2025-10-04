"""Filter tests for the processes module."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from materials.models import Material

from ..filters import ProcessCategoryFilter, ProcessFilter
from ..models import Process, ProcessCategory, ProcessMaterial


class ProcessCategoryFilterTestCase(TestCase):
    """Test ProcessCategory filters."""

    def setUp(self):
        self.owner = get_user_model().objects.create(username="test_user")
        ProcessCategory.objects.create(
            name="Thermochemical", owner=self.owner, publication_status="published"
        )
        ProcessCategory.objects.create(
            name="Biochemical", owner=self.owner, publication_status="published"
        )
        ProcessCategory.objects.create(
            name="Physical", owner=self.owner, publication_status="draft"
        )

    def test_filter_by_name(self):
        """Filter should find categories by name."""
        filterset = ProcessCategoryFilter(
            data={"name": "Thermo"}, queryset=ProcessCategory.objects.all()
        )
        self.assertEqual(filterset.qs.count(), 1)
        self.assertEqual(filterset.qs.first().name, "Thermochemical")

    def test_filter_by_publication_status(self):
        """Filter should find categories by publication status."""
        filterset = ProcessCategoryFilter(
            data={"publication_status": "published"},
            queryset=ProcessCategory.objects.all(),
        )
        self.assertEqual(filterset.qs.count(), 2)

    def test_no_filter_returns_all(self):
        """Empty filter should return all categories."""
        filterset = ProcessCategoryFilter(data={}, queryset=ProcessCategory.objects.all())
        self.assertEqual(filterset.qs.count(), 3)


class ProcessFilterTestCase(TestCase):
    """Test Process filters."""

    def setUp(self):
        self.owner = get_user_model().objects.create(username="test_user")
        
        self.category1 = ProcessCategory.objects.create(
            name="Thermochemical", owner=self.owner, publication_status="published"
        )
        self.category2 = ProcessCategory.objects.create(
            name="Biochemical", owner=self.owner, publication_status="published"
        )
        
        self.process1 = Process.objects.create(
            name="Pyrolysis",
            mechanism="Thermal Decomposition",
            owner=self.owner,
            publication_status="published",
        )
        self.process1.categories.add(self.category1)
        
        self.process2 = Process.objects.create(
            name="Gasification",
            mechanism="Partial Oxidation",
            owner=self.owner,
            publication_status="published",
        )
        self.process2.categories.add(self.category1)
        
        self.process3 = Process.objects.create(
            name="Anaerobic Digestion",
            mechanism="Fermentation",
            owner=self.owner,
            publication_status="published",
        )
        self.process3.categories.add(self.category2)
        
        self.parent_process = Process.objects.create(
            name="Parent Process",
            owner=self.owner,
            publication_status="published",
        )
        
        self.child_process = Process.objects.create(
            name="Child Process",
            parent=self.parent_process,
            owner=self.owner,
            publication_status="published",
        )

    def test_filter_by_name(self):
        """Filter should find processes by name."""
        filterset = ProcessFilter(data={"name": "Pyro"}, queryset=Process.objects.all())
        self.assertEqual(filterset.qs.count(), 1)
        self.assertEqual(filterset.qs.first().name, "Pyrolysis")

    def test_filter_by_mechanism(self):
        """Filter should find processes by mechanism."""
        filterset = ProcessFilter(
            data={"mechanism": "Fermentation"}, queryset=Process.objects.all()
        )
        self.assertEqual(filterset.qs.count(), 1)
        self.assertEqual(filterset.qs.first().name, "Anaerobic Digestion")

    def test_filter_by_category(self):
        """Filter should find processes by category."""
        filterset = ProcessFilter(
            data={"categories": [self.category1.pk]}, queryset=Process.objects.all()
        )
        self.assertEqual(filterset.qs.count(), 2)

    def test_filter_by_parent(self):
        """Filter should find child processes by parent."""
        filterset = ProcessFilter(
            data={"parent": self.parent_process.pk}, queryset=Process.objects.all()
        )
        self.assertEqual(filterset.qs.count(), 1)
        self.assertEqual(filterset.qs.first().name, "Child Process")

    def test_filter_by_publication_status(self):
        """Filter should find processes by publication status."""
        Process.objects.create(
            name="Draft Process",
            owner=self.owner,
            publication_status="draft",
        )
        
        filterset = ProcessFilter(
            data={"publication_status": "published"}, queryset=Process.objects.all()
        )
        self.assertEqual(filterset.qs.count(), 5)  # Excludes draft

    def test_filter_by_input_material(self):
        """Filter should find processes by input material."""
        material = Material.objects.create(
            name="Wood Chips", owner=self.owner, publication_status="published"
        )
        ProcessMaterial.objects.create(
            process=self.process1,
            material=material,
            role=ProcessMaterial.Role.INPUT,
        )
        
        filterset = ProcessFilter(
            data={"input_material": "Wood"}, queryset=Process.objects.all()
        )
        self.assertEqual(filterset.qs.count(), 1)
        self.assertEqual(filterset.qs.first().name, "Pyrolysis")

    def test_filter_by_output_material(self):
        """Filter should find processes by output material."""
        material = Material.objects.create(
            name="Bio-oil", owner=self.owner, publication_status="published"
        )
        ProcessMaterial.objects.create(
            process=self.process1,
            material=material,
            role=ProcessMaterial.Role.OUTPUT,
        )
        
        filterset = ProcessFilter(
            data={"output_material": "Bio-oil"}, queryset=Process.objects.all()
        )
        self.assertEqual(filterset.qs.count(), 1)
        self.assertEqual(filterset.qs.first().name, "Pyrolysis")
