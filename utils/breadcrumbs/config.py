"""
Breadcrumb hierarchy configuration.

Defines the navigation structure for generating breadcrumbs automatically.
Each section corresponds to a sidebar navigation item.
"""

from django.urls import reverse

# Section definitions matching sidebar navigation
SECTIONS = {
    "home": {
        "label": "Home",
        "url_name": "home",
        "icon": "fa-tachometer-alt",
    },
    "maps": {
        "label": "Maps",
        "url_name": "maps_list",
        "icon": "fa-globe-europe",
    },
    "materials": {
        "label": "Materials",
        "url_name": "sample-list-featured",
        "icon": "fa-leaf",
    },
    "sources": {
        "label": "Sources",
        "url_name": "sources-list",
        "icon": "fa-expand-arrows-alt",
    },
    "processes": {
        "label": "Processes",
        "url_name": "processes:dashboard",
        "icon": "fa-flask",
    },
    "inventories": {
        "label": "Inventories",
        "url_name": "scenario-list",
        "icon": "fa-chart-bar",
    },
    "bibliography": {
        "label": "Bibliography",
        "url_name": "source-list",
        "icon": "fa-book",
    },
    "learning": {
        "label": "Learning",
        "url_name": "learning",
        "icon": "fa-graduation-cap",
    },
    "about": {
        "label": "About",
        "url_name": "about",
        "icon": "fa-info-circle",
    },
    "waste_collection": {
        "label": "Waste Collection",
        "url_name": "collection-list",
        "icon": "fa-recycle",
    },
}

# Map model names to their parent section
MODEL_SECTIONS = {
    # Materials app
    "sample": "materials",
    "sampleseries": "materials",
    "material": "materials",
    "materialcategory": "materials",
    "materialcomponent": "materials",
    "materialcomponentgroup": "materials",
    "materialproperty": "materials",
    "materialpropertyvalue": "materials",
    "composition": "materials",
    "analyticalmethod": "materials",
    "weightshare": "materials",
    # Maps app
    "catchment": "maps",
    "region": "maps",
    "nutsregion": "maps",
    "lauregion": "maps",
    "geodataset": "maps",
    "attribute": "maps",
    "regionattributevalue": "maps",
    "location": "maps",
    # Inventories app
    "scenario": "inventories",
    "scenarioinventory": "inventories",
    # Bibliography app
    "source": "bibliography",
    "author": "bibliography",
    "licence": "bibliography",
    # Distributions app
    "temporaldistribution": "materials",
    "timestep": "materials",
    # Waste collection (soilcom)
    "collection": "waste_collection",
    "collector": "waste_collection",
    "collectioncatchment": "waste_collection",
    "wasteflyer": "waste_collection",
    "wastecategory": "waste_collection",
}

# Subsection definitions for models that need intermediate breadcrumbs
# Format: model_name -> {"label": str, "url_name": str, "parent_section": str}
MODEL_SUBSECTIONS = {
    "sample": {
        "label": "Samples",
        "url_name": "sample-list-featured",
    },
    "sampleseries": {
        "label": "Sample Series",
        "url_name": "sampleseries-list",
    },
    "material": {
        "label": "Materials",
        "url_name": "material-list",
    },
    "materialcategory": {
        "label": "Categories",
        "url_name": "materialcategory-list",
    },
    "materialcomponent": {
        "label": "Components",
        "url_name": "materialcomponent-list",
    },
    "materialcomponentgroup": {
        "label": "Component Groups",
        "url_name": "materialcomponentgroup-list",
    },
    "materialproperty": {
        "label": "Properties",
        "url_name": "materialproperty-list",
    },
    "analyticalmethod": {
        "label": "Analytical Methods",
        "url_name": "analyticalmethod-list",
    },
    "catchment": {
        "label": "Catchments",
        "url_name": "catchment-list",
    },
    "region": {
        "label": "Regions",
        "url_name": "region-list",
    },
    "geodataset": {
        "label": "Geo Datasets",
        "url_name": "geodataset-list",
    },
    "attribute": {
        "label": "Attributes",
        "url_name": "attribute-list",
    },
    "location": {
        "label": "Locations",
        "url_name": "location-list",
    },
    "scenario": {
        "label": "Scenarios",
        "url_name": "scenario-list",
    },
    "source": {
        "label": "Sources",
        "url_name": "source-list",
    },
    "author": {
        "label": "Authors",
        "url_name": "author-list",
    },
    "licence": {
        "label": "Licences",
        "url_name": "licence-list",
    },
    "collection": {
        "label": "Collections",
        "url_name": "collection-list",
    },
    "collector": {
        "label": "Collectors",
        "url_name": "collector-list",
    },
}


def get_section_for_model(model_name: str) -> dict | None:
    """Get the section configuration for a given model name."""
    section_key = MODEL_SECTIONS.get(model_name.lower())
    if section_key:
        return SECTIONS.get(section_key)
    return None


def get_subsection_for_model(model_name: str) -> dict | None:
    """Get the subsection configuration for a given model name."""
    return MODEL_SUBSECTIONS.get(model_name.lower())


def get_section_url(section_key: str) -> str | None:
    """Safely resolve a section URL, returning None if it fails."""
    section = SECTIONS.get(section_key)
    if not section:
        return None
    try:
        return reverse(section["url_name"])
    except Exception:
        return None


def get_subsection_url(model_name: str) -> str | None:
    """Safely resolve a subsection URL, returning None if it fails."""
    subsection = get_subsection_for_model(model_name)
    if not subsection:
        return None
    try:
        return reverse(subsection["url_name"])
    except Exception:
        return None
