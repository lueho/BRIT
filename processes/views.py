from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import render
from django.views.generic import TemplateView

# Create your views here.

# Shared mock process data for dashboard and detail views
MOCK_PROCESS_TYPES = [
    {
        "id": 12,
        "name": "Pulping",
        "url_name": "processes:mock_process_overview",
        "category": "Physicochemical",
        "input": [
            {"name": "Straw", "id": 102},
            {"name": "Wood Chips", "id": 108},
        ],
        "output": [],
        "short_description": "An overview of pulping technologies for disintegrating biomass into fibres.",
        "description": "This is a summary page for various pulping technologies.",
        "mechanism": "Physico-chemical or chemical reactions",
        "temperature_min": 130,
        "temperature_max": 190,
        "yield_percentage": "40 - 90%",
        "sources": [],
        "info_charts": [],
    },
    {
        "id": 1,
        "name": "Anaerobic Digestion",
        "category": "Biochemical",
        "input": [
            {"name": "Manure", "id": 104},
            {"name": "Organic Waste", "id": 105},
        ],
        "output": [
            {"name": "Biogas", "id": 204},
            {"name": "Digestate", "id": 205},
        ],
        "short_description": "Biological breakdown of organic waste into biogas and digestate using microbes in the absence of oxygen.",
        "description": "Anaerobic digestion is a biological process in which microorganisms break down organic matter, such as manure and organic waste, in the absence of oxygen. This process produces renewable biogas (mainly methane and CO2) and digestate, which can be used as a soil amendment. The process typically operates at mesophilic (20–45°C) or thermophilic (45–65°C) temperatures. <a href='https://www.tech4biowaste.eu/wiki/Anaerobic_digestion' target='_blank'>Learn more</a>.",
        "mechanism": "Fermentation",
        "temperature_min": 20,
        "temperature_max": 65,
        "yield_percentage": 55,
        "links": [{"label": "Detail View", "url": "/processes/detail/1"}],
        "sources": [
            {
                "type": "website",
                "title": "Tech4Biowaste: Anaerobic Digestion",
                "url": "https://www.tech4biowaste.eu/wiki/Anaerobic_digestion",
            }
        ],
        "info_charts": [
            {"name": "Info Chart I", "url": "#"},
            {"name": "Info Chart II", "url": "#"},
        ],
    },
    {
        "id": 2,
        "name": "Gasification",
        "category": "Thermochemical",
        "input": [
            {"name": "Wood Chips", "id": 108},
            {"name": "Biomass", "id": 109},
        ],
        "output": [
            {"name": "Syngas", "id": 210},
            {"name": "Biochar", "id": 202},
        ],
        "short_description": "Thermochemical conversion of biomass or wood chips into syngas and biochar at high temperatures.",
        "description": "Gasification is a thermochemical process that converts carbonaceous materials like wood chips and biomass into syngas (a mixture of CO, H2, and CO2) and biochar by partial oxidation at high temperatures (typically 700–1500°C) in a low-oxygen environment. Syngas can be used for energy or as a chemical feedstock. <a href='https://www.tech4biowaste.eu/wiki/Gasification' target='_blank'>Learn more</a>.",
        "mechanism": "Partial Oxidation",
        "temperature_min": 700,
        "temperature_max": 1500,
        "yield_percentage": 60,
        "links": [{"label": "Detail View", "url": "/processes/detail/2"}],
        "sources": [
            {
                "type": "website",
                "title": "Tech4Biowaste: Gasification",
                "url": "https://www.tech4biowaste.eu/wiki/Gasification",
            }
        ],
        "info_charts": [
            {"name": "Info Chart I", "url": "#"},
            {"name": "Info Chart II", "url": "#"},
        ],
    },
    {
        "id": 3,
        "name": "Pyrolysis",
        "category": "Thermochemical",
        "input": [
            {"name": "Forest Residues", "id": 101},
            {"name": "Straw", "id": 102},
        ],
        "output": [
            {"name": "Bio-oil", "id": 201},
            {"name": "Biochar", "id": 202},
            {"name": "Syngas", "id": 203},
        ],
        "short_description": "Thermal decomposition of biomass without oxygen to produce bio-oil, biochar, and syngas.",
        "description": "Pyrolysis is the thermal decomposition of organic materials such as forest residues and straw in the absence of oxygen. It produces bio-oil, biochar, and syngas, with process conditions (temperature, residence time) influencing the product distribution. <a href='https://www.tech4biowaste.eu/wiki/Pyrolysis' target='_blank'>Learn more</a>.",
        "mechanism": "Thermal Decomposition",
        "temperature_min": 400,
        "temperature_max": 700,
        "yield_percentage": 65,
        "links": [{"label": "Detail View", "url": "/processes/detail/3"}],
        "sources": [
            {
                "type": "website",
                "title": "Tech4Biowaste: Pyrolysis",
                "url": "https://www.tech4biowaste.eu/wiki/Pyrolysis",
            }
        ],
        "info_charts": [
            {"name": "Info Chart I", "url": "#"},
            {"name": "Info Chart II", "url": "#"},
        ],
    },
    {
        "id": 4,
        "name": "Composting",
        "category": "Biochemical",
        "input": [
            {"name": "Organic Waste", "id": 105},
            {"name": "Green Waste", "id": 110},
        ],
        "output": [{"name": "Compost", "id": 301}],
        "short_description": "Aerobic biological decomposition of organic material to produce compost.",
        "description": "Composting is an aerobic process that converts organic waste into stable, humus-like material called compost, which can be used as a soil conditioner. <a href='https://www.tech4biowaste.eu/wiki/Composting' target='_blank'>Learn more</a>.",
        "mechanism": "Aerobic Decomposition",
        "temperature_min": 40,
        "temperature_max": 70,
        "yield_percentage": 50,
        "links": [{"label": "Detail View", "url": "/processes/detail/4"}],
        "sources": [
            {
                "type": "website",
                "title": "Tech4Biowaste: Composting",
                "url": "https://www.tech4biowaste.eu/wiki/Composting",
            }
        ],
        "info_charts": [
            {"name": "Info Chart I", "url": "#"},
            {"name": "Info Chart II", "url": "#"},
        ],
    },
    {
        "id": 5,
        "name": "Hydrothermal Processing",
        "category": "Thermochemical",
        "input": [{"name": "Wet Biomass", "id": 120}],
        "output": [
            {"name": "Hydrochar", "id": 302},
            {"name": "Process Water", "id": 303},
        ],
        "short_description": "Thermochemical conversion of wet biomass under high pressure and moderate temperature.",
        "description": "Hydrothermal processing converts wet biomass into hydrochar and process water under subcritical water conditions. <a href='https://www.tech4biowaste.eu/wiki/Hydrothermal_processing' target='_blank'>Learn more</a>.",
        "mechanism": "Hydrothermal Conversion",
        "temperature_min": 180,
        "temperature_max": 300,
        "yield_percentage": 45,
        "links": [{"label": "Detail View", "url": "/processes/detail/5"}],
        "sources": [
            {
                "type": "website",
                "title": "Tech4Biowaste: Hydrothermal Processing",
                "url": "https://www.tech4biowaste.eu/wiki/Hydrothermal_processing",
            }
        ],
        "info_charts": [
            {"name": "Info Chart I", "url": "#"},
            {"name": "Info Chart II", "url": "#"},
        ],
    },
    {
        "id": 6,
        "name": "Torrefaction",
        "category": "Thermochemical",
        "input": [{"name": "Biomass", "id": 109}],
        "output": [{"name": "Torrified Biomass", "id": 304}],
        "short_description": "Mild pyrolysis process to improve biomass fuel properties.",
        "description": "Torrefaction is a thermochemical treatment of biomass at 200–320°C in the absence of oxygen, producing a solid fuel with improved properties. <a href='https://www.tech4biowaste.eu/wiki/Torrefaction' target='_blank'>Learn more</a>.",
        "mechanism": "Mild Pyrolysis",
        "temperature_min": 200,
        "temperature_max": 320,
        "yield_percentage": 70,
        "links": [{"label": "Detail View", "url": "/processes/detail/6"}],
        "sources": [
            {
                "type": "website",
                "title": "Tech4Biowaste: Torrefaction",
                "url": "https://www.tech4biowaste.eu/wiki/Torrefaction",
            }
        ],
        "info_charts": [
            {"name": "Info Chart I", "url": "#"},
            {"name": "Info Chart II", "url": "#"},
        ],
    },
    {
        "id": 7,
        "name": "Steam Explosion",
        "category": "Physical",
        "input": [{"name": "Lignocellulosic Biomass", "id": 301}],
        "output": [{"name": "Exploded Biomass", "id": 305}],
        "short_description": "Mechanical and thermal pre-treatment using high-pressure steam.",
        "description": "Steam explosion is a pre-treatment process in which biomass is treated with high-pressure steam and then rapidly depressurized, causing the material to break apart. <a href='https://www.tech4biowaste.eu/wiki/Steam_explosion' target='_blank'>Learn more</a>.",
        "mechanism": "Mechanical/Thermal Pre-treatment",
        "temperature_min": 160,
        "temperature_max": 240,
        "yield_percentage": 60,
        "links": [{"label": "Detail View", "url": "/processes/detail/7"}],
        "sources": [
            {
                "type": "website",
                "title": "Tech4Biowaste: Steam Explosion",
                "url": "https://www.tech4biowaste.eu/wiki/Steam_explosion",
            }
        ],
        "info_charts": [
            {"name": "Info Chart I", "url": "#"},
            {"name": "Info Chart II", "url": "#"},
        ],
    },
    {
        "id": 8,
        "name": "Ultrasonication",
        "category": "Physical",
        "input": [{"name": "Sludge", "id": 401}],
        "output": [{"name": "Disintegrated Sludge", "id": 402}],
        "short_description": "Use of ultrasound waves to disintegrate sludge and enhance bioprocesses.",
        "description": "Ultrasonication applies ultrasound waves to sludge or biomass to disrupt cell walls and enhance subsequent bioprocesses. <a href='https://www.tech4biowaste.eu/wiki/Ultrasonication' target='_blank'>Learn more</a>.",
        "mechanism": "Ultrasound Disintegration",
        "temperature_min": 20,
        "temperature_max": 60,
        "yield_percentage": 40,
        "links": [{"label": "Detail View", "url": "/processes/detail/8"}],
        "sources": [
            {
                "type": "website",
                "title": "Tech4Biowaste: Ultrasonication",
                "url": "https://www.tech4biowaste.eu/wiki/Ultrasonication",
            }
        ],
        "info_charts": [
            {"name": "Info Chart I", "url": "#"},
            {"name": "Info Chart II", "url": "#"},
        ],
    },
    {
        "id": 9,
        "name": "Biocomposite Processing",
        "category": "Material",
        "input": [
            {"name": "Biopolymers", "id": 501},
            {"name": "Natural Fibres", "id": 502},
        ],
        "output": [{"name": "Biocomposite", "id": 503}],
        "short_description": "Manufacturing of composite materials from biopolymers and natural fibres.",
        "description": "Biocomposite processing involves combining biopolymers and natural fibres to create composite materials with enhanced properties. <a href='https://www.tech4biowaste.eu/wiki/Biocomposite_processing' target='_blank'>Learn more</a>.",
        "mechanism": "Composite Manufacturing",
        "temperature_min": 100,
        "temperature_max": 200,
        "yield_percentage": 80,
        "links": [{"label": "Detail View", "url": "/processes/detail/9"}],
        "sources": [
            {
                "type": "website",
                "title": "Tech4Biowaste: Biocomposite Processing",
                "url": "https://www.tech4biowaste.eu/wiki/Biocomposite_processing",
            }
        ],
        "info_charts": [
            {"name": "Info Chart I", "url": "#"},
            {"name": "Info Chart II", "url": "#"},
        ],
    },
]


class ProcessMockDashboard(PermissionRequiredMixin, TemplateView):
    permission_required = "processes.access_app_feature"
    template_name = "processes/mock_dashboard.html"

    def get_context_data(self, **kwargs):
        return {"process_types": MOCK_PROCESS_TYPES}


class ProcessOverviewMock(PermissionRequiredMixin, TemplateView):
    permission_required = "processes.access_app_feature"
    template_name = "processes/mock_process_overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Filter for technologies related to "Pulping"
        # Using IDs 7 (Steam Explosion), 10, and 11
        pulping_ids = [7, 10, 11]
        context["technologies"] = [
            p for p in MOCK_PROCESS_TYPES if p["id"] in pulping_ids
        ]
        return context


class ProcessTypeListMock(PermissionRequiredMixin, TemplateView):
    permission_required = "processes.access_app_feature"
    template_name = "processes/mock_type_list.html"

    def get_context_data(self, **kwargs):
        return {
            "process_types": [
                {
                    "id": 1,
                    "name": "Anaerobic Digestion",
                    "category": "Biochemical",
                    "description": "Biological process for biogas and digestate from organic waste.",
                },
                {
                    "id": 2,
                    "name": "Gasification",
                    "category": "Thermochemical",
                    "description": "Produces syngas from solid feedstocks at high temperature.",
                },
                {
                    "id": 3,
                    "name": "Pyrolysis",
                    "category": "Thermochemical",
                    "description": "Converts biomass into bio-oil, char, and syngas via rapid heating.",
                },
                {
                    "id": 4,
                    "name": "Composting",
                    "category": "Biochemical",
                    "description": "Aerobic biological decomposition of organic material to produce compost.",
                },
                {
                    "id": 5,
                    "name": "Hydrothermal Processing",
                    "category": "Thermochemical",
                    "description": "Conversion of wet biomass into hydrochar and process water under subcritical water conditions.",
                },
                {
                    "id": 6,
                    "name": "Torrefaction",
                    "category": "Thermochemical",
                    "description": "Mild pyrolysis process for improving biomass fuel properties.",
                },
                {
                    "id": 7,
                    "name": "Steam Explosion",
                    "category": "Physical",
                    "description": "Mechanical and thermal pre-treatment using high-pressure steam.",
                },
                {
                    "id": 8,
                    "name": "Ultrasonication",
                    "category": "Physical",
                    "description": "Use of ultrasound waves to disintegrate sludge and enhance bioprocesses.",
                },
                {
                    "id": 9,
                    "name": "Biocomposite Processing",
                    "category": "Material",
                    "description": "Manufacturing of composite materials from biopolymers and natural fibres.",
                },
                {
                    "id": 10,
                    "name": "Horizontal tube digester for straw",
                    "category": "Pulping",
                    "description": "Specially designed for straw, giving higher quality fibres for brown and white grades.",
                },
                {
                    "id": 11,
                    "name": "Liquor circulation digesters for wood",
                    "category": "Pulping",
                    "description": "Technology for pulping of wood to fibres of highest quality by Kraft or Sulfite pulping.",
                },
            ]
        }


class ProcessTypeDetailMock(PermissionRequiredMixin, TemplateView):
    permission_required = "processes.access_app_feature"
    template_name = "processes/mock_type_detail.html"

    def get_context_data(self, **kwargs):
        pt_id = int(self.kwargs.get("pk", 0))
        process = next((p for p in MOCK_PROCESS_TYPES if p["id"] == pt_id), None)
        return {"process": process}


class ProcessMockMaterialDetail(PermissionRequiredMixin, TemplateView):
    permission_required = "processes.access_app_feature"
    template_name = "processes/mock_material_detail.html"

    def get_context_data(self, **kwargs):
        material_id = int(self.kwargs.get("pk", 0))
        data = {
            101: {
                "name": "Forest Residues",
                "category": "Biomass",
                "description": "Woody debris and by-products from forestry operations. Rich in lignocellulosic material, ideal for thermochemical conversion.",
                "composition": "Cellulose, hemicellulose, lignin",
                "uses": "Bio-oil, biochar, heat and power",
                "related_processes": "Fast Pyrolysis, Gasification",
            },
            102: {
                "name": "Straw",
                "category": "Agricultural Residue",
                "description": "Stalks and stems left after grain harvest. Used as feedstock for bioenergy and soil amendment.",
                "composition": "Cellulose, hemicellulose, silica",
                "uses": "Bio-oil, animal bedding, compost",
                "related_processes": "Fast Pyrolysis",
            },
            104: {
                "name": "Manure",
                "category": "Organic Waste",
                "description": "Animal manure from livestock operations, rich in nutrients and organic matter.",
                "composition": "Organic matter, NPK nutrients, moisture",
                "uses": "Anaerobic digestion, fertilizer",
                "related_processes": "Anaerobic Digestion",
            },
            105: {
                "name": "Organic Waste",
                "category": "Biowaste",
                "description": "Kitchen and food waste, green waste from households and commercial sources.",
                "composition": "Moisture, carbohydrates, proteins, fats",
                "uses": "Anaerobic digestion, composting",
                "related_processes": "Anaerobic Digestion",
            },
            108: {
                "name": "Wood Chips",
                "category": "Biomass",
                "description": "Small pieces of wood produced by chipping larger pieces of wood. Used as a solid biofuel.",
                "composition": "Cellulose, hemicellulose, lignin",
                "uses": "Gasification, combustion, mulch",
                "related_processes": "Gasification",
            },
            109: {
                "name": "Biomass",
                "category": "Biomass",
                "description": "Organic material from plants and animals, used as a renewable energy source.",
                "composition": "Varies: cellulose, hemicellulose, lignin, starch, oils",
                "uses": "Gasification, combustion, biofuel production",
                "related_processes": "Gasification",
            },
            201: {
                "name": "Bio-oil",
                "category": "Liquid Fuel",
                "description": "Dark brown liquid from fast pyrolysis, used as a renewable fuel or chemical feedstock.",
                "composition": "Complex mixture of oxygenated organics",
                "uses": "Fuel, chemicals, energy",
                "related_processes": "Fast Pyrolysis",
            },
            202: {
                "name": "Biochar",
                "category": "Solid Carbon Product",
                "description": "Carbon-rich solid from pyrolysis, used for soil enhancement and carbon sequestration.",
                "composition": "Fixed carbon, ash, volatile matter",
                "uses": "Soil amendment, carbon sink",
                "related_processes": "Fast Pyrolysis",
            },
            203: {
                "name": "Syngas",
                "category": "Gas Fuel",
                "description": "Mixture of CO, H<sub>2</sub>, and small hydrocarbons from gasification or pyrolysis.",
                "composition": "CO, H<sub>2</sub>, CH<sub>4</sub>",
                "uses": "Energy, chemical synthesis",
                "related_processes": "Fast Pyrolysis, Gasification",
            },
            204: {
                "name": "Biogas",
                "category": "Gas Fuel",
                "description": "Renewable methane-rich gas from anaerobic digestion of organic matter.",
                "composition": "CH<sub>4</sub>, CO<sub>2</sub>, trace gases",
                "uses": "Heat, electricity, vehicle fuel",
                "related_processes": "Anaerobic Digestion",
            },
            205: {
                "name": "Digestate",
                "category": "Soil Amendment",
                "description": "Nutrient-rich residue from anaerobic digestion, used as fertilizer.",
                "composition": "Organic matter, NPK nutrients",
                "uses": "Fertilizer, soil conditioner",
                "related_processes": "Anaerobic Digestion",
            },
            206: {
                "name": "Straw",
                "category": "Agricultural Residue",
                "description": "Stalks and stems left after grain harvest. Used as feedstock for bioenergy and soil amendment.",
                "composition": "Cellulose, hemicellulose, silica",
                "uses": "Bio-oil, animal bedding, compost",
                "related_processes": "Pulping",
            },
        }
        return {"material": data.get(material_id)}


class ProcessRunMock(PermissionRequiredMixin, TemplateView):
    permission_required = "processes.access_app_feature"
    template_name = "processes/mock_run.html"

    def get_context_data(self, **kwargs):
        pt_id = self.kwargs.get("pk")
        return {"process_type": {"id": pt_id, "name": f"Mock ProcessType #{pt_id}"}}


class StrawAndWoodProcessInfoView(TemplateView):
    template_name = "processes/pulping_straw_infocard.html"
