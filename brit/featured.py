from utils.external_urls import ABFALLATLAS_URL

ECN_BRIT_EU_URL = "https://www.compostnetwork.info/brit-eu/"
ECN_FACTSHEETS_URL = "https://www.compostnetwork.info/downloads/factsheets/"

FEATURED_DESTINATIONS = (
    {
        "slug": "waste-atlas",
        "icon": "fa-map-marked-alt",
        "category": "Standalone tool",
        "title": "Waste Atlas",
        "description": (
            "Explore maps of biowaste collection systems, quantities and "
            "regional differences across projects, countries and years."
        ),
        "url_name": "waste-atlas-overview",
        "cta_label": "Open Waste Atlas",
        "image_path": "img/featured/germany_organic_collection_amount_map.webp",
        "image_alt": "Map of German districts coloured by the collected amount of organic waste per capita",
        "image_width": 1280,
        "image_height": 720,
        "logos": (),
        "external_link": {"label": "abfall-atlas.de", "url": ABFALLATLAS_URL},
    },
    {
        "slug": "brit-eu",
        "icon": "fa-chart-bar",
        "category": "Project results",
        "title": "BRIT-EU results",
        "description": (
            "Discover BRIT-EU maps, collection data and R analysis resources "
            "for comparing municipal biowaste collection systems."
        ),
        "url_name": "brit-eu-results",
        "cta_label": "Explore BRIT-EU results",
        "image_path": "img/featured/europe_data_coverage_map.webp",
        "image_alt": "Map of Europe highlighting the regions with biowaste collection data",
        "image_width": 1280,
        "image_height": 720,
        "logos": (
            {
                "image_path": "img/brit_eu_logo.png",
                "alt": "BRIT-EU logo",
                "width": 1335,
                "height": 387,
                "variant": "project",
            },
        ),
        "external_link": {"label": "All results at ECN", "url": ECN_BRIT_EU_URL},
    },
    {
        "slug": "closecycle",
        "icon": "fa-recycle",
        "category": "Project showcases",
        "title": "CLOSECYCLE showcases",
        "description": (
            "Discover how regional residues become useful products through "
            "Territorial Biorefinery Networks."
        ),
        "url_name": "Showcase",
        "cta_label": "Explore showcases",
        "image_path": "img/featured/closecycle_showcases_themes_map.webp",
        "image_alt": "Map of the CLOSECYCLE showcases, pilot regions and themes across the North Sea region",
        "image_width": 1280,
        "image_height": 720,
        "logos": (
            {
                "image_path": "img/interreg_with_closecycle_logo.png",
                "alt": (
                    "CLOSECYCLE project logo with Interreg North Sea and "
                    "European Union co-funding acknowledgement"
                ),
                "width": 1237,
                "height": 500,
                "variant": "interreg",
            },
            {
                "image_path": "img/closecycle_logo.png",
                "alt": "CLOSECYCLE logo",
                "width": 506,
                "height": 91,
                "variant": "project-secondary",
            },
        ),
        "external_link": None,
    },
)

BRIT_EU_MAP_LINKS = (
    {
        "label": "Catalonia",
        "url_name": "waste-atlas-catalonia-collection-system-map",
        "ecn_profile_url": "https://www.compostnetwork.info/brit-case-study-profile-catalonia-spain/",
    },
    {
        "label": "North Rhine-Westphalia",
        "url_name": "waste-atlas-nrw-collection-system-map",
        "ecn_profile_url": "https://www.compostnetwork.info/brit-case-study-profile-north-rhine-westphalia-germany/",
    },
    {
        "label": "Rhineland-Palatinate",
        "url_name": "waste-atlas-rp-collection-system-map",
        "ecn_profile_url": "https://www.compostnetwork.info/brit-case-study-profile-rhineland-palatinate-germany/",
    },
    {
        "label": "Sweden",
        "url_name": "waste-atlas-sweden-collection-system-map",
        "ecn_profile_url": "https://www.compostnetwork.info/brit-country-profile-sweden/",
    },
    {
        "label": "South Tyrol",
        "url_name": "waste-atlas-south-tyrol-collection-system-map",
        "ecn_profile_url": "https://www.compostnetwork.info/brit-case-study-profile-bolzano/",
    },
)

BRIT_EU_ECN_FACTSHEETS = (
    {
        "label": "Target waste category",
        "url": "https://www.compostnetwork.info/fact-sheet-target-waste-category/",
    },
    {
        "label": "Participation policy & connection rate",
        "url": "https://www.compostnetwork.info/fact-sheet-participation-policy-connection-rate/",
    },
    {
        "label": "Collection mode & use control",
        "url": "https://www.compostnetwork.info/fact-sheet-collection-mode-use-control/",
    },
    {
        "label": "Collection frequency structure & annual collection count",
        "url": "https://www.compostnetwork.info/fact-sheet-collection-frequency-structure-annual-collection-count/",
    },
    {
        "label": "Collection container configuration",
        "url": "https://www.compostnetwork.info/fact-sheet-collection-container-configuration/",
    },
    {
        "label": "Correlation assessment of biowaste performance indicators",
        "url": "https://www.compostnetwork.info/special-factsheet-brit/",
    },
)
