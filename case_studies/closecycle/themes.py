from urllib.parse import urlencode

from django.urls import reverse

THEMES = {
    "apple_chain": {
        "label": "Apple Chain",
        "color": "#ff4f4f",
        "description": "Recovering value from apple and cider residues through preservation and complementary product routes, linking regional producers with processors and users of the resulting materials.",
    },
    "greenhouses": {
        "label": "Greenhouses",
        "color": "#339933",
        "description": "Preserving and valorizing seasonal greenhouse plant residues, addressing moisture and contamination so that materials can return to crop production through compost and other useful products.",
    },
    "nature_conservation": {
        "label": "Nature Conservation",
        "color": "#a2b301",
        "description": "Connecting nature-reserve management with agriculture: vegetation removed for conservation can become locally useful soil amendments, subject to suitable logistics, processing and regulatory arrangements.",
    },
    "tree_cultivation": {
        "label": "Tree Cultivation",
        "color": "#bf9000",
        "description": "Developing and applying growing media from regional residues for nurseries and tree planting, assessing plant performance, material quality and opportunities to replace conventional inputs.",
    },
    "municipalities_farms": {
        "label": "Municipalities and Farms",
        "color": "#607749",
        "description": "Closing regional nutrient, material and energy cycles between citizens, municipalities and farms by connecting biowaste and farm-residue management with useful products and their local applications.",
    },
    "food_crops": {
        "label": "Food Crops",
        "color": "#ffb600",
        "description": "Evaluating residue-based fertilizers and soil improvers in food-crop production, linking regional suppliers and processors with growers while assessing soil health, crop performance and safe use.",
    },
    "biorefinery_modules": {
        "label": "Biorefinery Modules",
        "color": "#01b3d1",
        "description": "Integrating farm-based processing units such as green biorefining, biogas and pyrolysis so that biomass, nutrients, materials and energy can circulate between agricultural activities and product uses.",
    },
}
THEME_CHOICES = tuple((key, value["label"]) for key, value in THEMES.items())
PILOT_REGION_ROLE = (
    "A pilot region provides the regional context for a Territorial Biorefinery "
    "Network (TBN): stakeholders connect residue suppliers, processing facilities "
    "and product users. Its showcases demonstrate specific parts of this network."
)
PILOT_BOUNDARY_NOTE = (
    "Polygons show mapped geographical context, often based on administrative "
    "boundaries. They are not exact limits of stakeholder relationships or "
    "material flows, which may extend beyond the mapped area."
)


def get_theme(key):
    theme = THEMES.get(key)
    return (
        {
            "key": key,
            **theme,
            "url": reverse("Showcase")
            + "?"
            + urlencode({"scope": "published", "theme": key}),
        }
        if theme
        else None
    )


def pilot_region_info(catchment):
    return {
        "id": catchment.pk,
        "name": str(catchment),
        "description": catchment.description or "",
        "url": reverse("catchment-detail", args=[catchment.pk]),
        "showcases_url": reverse("Showcase")
        + "?"
        + urlencode({"scope": "published", "pilot_region": catchment.pk}),
        "role": PILOT_REGION_ROLE,
        "boundary_note": PILOT_BOUNDARY_NOTE,
    }
