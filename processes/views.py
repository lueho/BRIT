from django.shortcuts import render
from django.views.generic import TemplateView

# Create your views here.

class ProcessMockDashboard(TemplateView):
    template_name = "processes/mock_dashboard.html"

    def get_context_data(self, **kwargs):
        return {
            "process_types": [
                {
                    "id": 1,
                    "name": "Anaerobic Digestion",
                    "category": "Biochemical",
                    "input": [
                        {"name": "Manure", "id": 104},
                        {"name": "Organic Waste", "id": 105}
                    ],
                    "output": [
                        {"name": "Biogas", "id": 204},
                        {"name": "Digestate", "id": 205}
                    ],
                    "short_description": "Biological breakdown of organic waste into biogas and digestate using microbes in the absence of oxygen.",
                    "description": "Anaerobic digestion is a biological process in which microorganisms break down organic matter, such as manure and organic waste, in the absence of oxygen. This process produces renewable biogas (mainly methane and CO2) and digestate, which can be used as a soil amendment. The process typically operates at mesophilic (20–45°C) or thermophilic (45–65°C) temperatures. <a href='https://www.tech4biowaste.eu/wiki/Anaerobic_digestion' target='_blank'>Learn more</a>.",
                    "mechanism": "Fermentation",
                    "temperature_min": 20,
                    "temperature_max": 65,
                    "yield_percentage": 55,
                    "links": [
                        {"label": "Detail View", "url": "/processes/detail/1"}
                    ]
                },
                {
                    "id": 2,
                    "name": "Gasification",
                    "category": "Thermochemical",
                    "input": [
                        {"name": "Wood Chips", "id": 108},
                        {"name": "Biomass", "id": 109}
                    ],
                    "output": [
                        {"name": "Syngas", "id": 210},
                        {"name": "Biochar", "id": 202}
                    ],
                    "short_description": "Thermochemical conversion of biomass or wood chips into syngas and biochar at high temperatures.",
                    "description": "Gasification is a thermochemical process that converts carbonaceous materials like wood chips and biomass into syngas (a mixture of CO, H2, and CO2) and biochar by partial oxidation at high temperatures (typically 700–1500°C) in a low-oxygen environment. Syngas can be used for energy or as a chemical feedstock. <a href='https://www.tech4biowaste.eu/wiki/Gasification' target='_blank'>Learn more</a>.",
                    "mechanism": "Partial Oxidation",
                    "temperature_min": 700,
                    "temperature_max": 1500,
                    "yield_percentage": 60,
                    "links": [
                        {"label": "Detail View", "url": "/processes/detail/2"}
                    ]
                },
                {
                    "id": 3,
                    "name": "Pyrolysis",
                    "category": "Thermochemical",
                    "input": [
                        {"name": "Forest Residues", "id": 101},
                        {"name": "Straw", "id": 102}
                    ],
                    "output": [
                        {"name": "Bio-oil", "id": 201},
                        {"name": "Biochar", "id": 202},
                        {"name": "Syngas", "id": 203}
                    ],
                    "short_description": "Thermal decomposition of biomass without oxygen to produce bio-oil, biochar, and syngas.",
                    "description": "Pyrolysis is the thermal decomposition of organic materials such as forest residues and straw in the absence of oxygen. It produces bio-oil, biochar, and syngas, with process conditions (temperature, residence time) influencing the product distribution. <a href='https://www.tech4biowaste.eu/wiki/Pyrolysis' target='_blank'>Learn more</a>.",
                    "mechanism": "Thermal Decomposition",
                    "temperature_min": 400,
                    "temperature_max": 700,
                    "yield_percentage": 65,
                    "links": [
                        {"label": "Detail View", "url": "/processes/detail/3"}
                    ]
                }
            ]
        }


class ProcessTypeListMock(TemplateView):
    template_name = "processes/mock_type_list.html"

    def get_context_data(self, **kwargs):
        return {
            "process_types": [
                {"id": 1, "name": "Anaerobic Digestion", "category": "Biochemical", "description": "Biological process for biogas and digestate from organic waste."},
                {"id": 2, "name": "Gasification", "category": "Thermochemical", "description": "Produces syngas from solid feedstocks at high temperature."},
                {"id": 3, "name": "Pyrolysis", "category": "Thermochemical", "description": "Converts biomass into bio-oil, char, and syngas via rapid heating."},
            ]
        }


class ProcessTypeDetailMock(TemplateView):
    template_name = "processes/mock_type_detail.html"

    def get_context_data(self, **kwargs):
        pt_id = int(self.kwargs.get('pk', 0))
        data = {
            1: {
                "id": 1,
                "name": "Anaerobic Digestion",
                "category": "Biochemical",
                "mechanism": "Fermentation",
                "temperature_min": 20,
                "temperature_max": 65,
                "yield_percentage": 55,
                "description": "Anaerobic digestion is a biological process in which microorganisms break down organic matter, such as manure and organic waste, in the absence of oxygen. This process produces renewable biogas (mainly methane and CO2) and digestate, which can be used as a soil amendment.",
                "input": [
                    {"name": "Manure", "id": 104},
                    {"name": "Organic Waste", "id": 105}
                ],
                "output": [
                    {"name": "Biogas", "id": 204},
                    {"name": "Digestate", "id": 205}
                ],
                "links": [
                    {"label": "Tech4Biowaste: Anaerobic Digestion", "url": "https://www.tech4biowaste.eu/wiki/Anaerobic_digestion"}
                ]
            },
            2: {
                "id": 2,
                "name": "Gasification",
                "category": "Thermochemical",
                "mechanism": "Partial Oxidation",
                "temperature_min": 700,
                "temperature_max": 1500,
                "yield_percentage": 60,
                "description": "Gasification is a thermochemical process that converts carbonaceous materials like wood chips and biomass into syngas (a mixture of CO, H2, and CO2) and biochar by partial oxidation at high temperatures (typically 700–1500°C) in a low-oxygen environment.",
                "input": [
                    {"name": "Wood Chips", "id": 108},
                    {"name": "Biomass", "id": 109}
                ],
                "output": [
                    {"name": "Syngas", "id": 210},
                    {"name": "Biochar", "id": 202}
                ],
                "links": [
                    {"label": "Tech4Biowaste: Gasification", "url": "https://www.tech4biowaste.eu/wiki/Gasification"}
                ]
            },
            3: {
                "id": 3,
                "name": "Pyrolysis",
                "category": "Thermochemical",
                "mechanism": "Thermal Decomposition",
                "temperature_min": 400,
                "temperature_max": 700,
                "yield_percentage": 65,
                "description": "Pyrolysis is the thermal decomposition of organic materials such as forest residues and straw in the absence of oxygen. It produces bio-oil, biochar, and syngas, with process conditions (temperature, residence time) influencing the product distribution.",
                "input": [
                    {"name": "Forest Residues", "id": 101},
                    {"name": "Straw", "id": 102}
                ],
                "output": [
                    {"name": "Bio-oil", "id": 201},
                    {"name": "Biochar", "id": 202},
                    {"name": "Syngas", "id": 203}
                ],
                "links": [
                    {"label": "Tech4Biowaste: Pyrolysis", "url": "https://www.tech4biowaste.eu/wiki/Pyrolysis"}
                ]
            },
        }
        return {"process": data.get(pt_id)}


class ProcessMockMaterialDetail(TemplateView):
    template_name = "processes/mock_material_detail.html"

    def get_context_data(self, **kwargs):
        material_id = int(self.kwargs.get('pk', 0))
        data = {
            101: {
                "name": "Forest Residues",
                "category": "Biomass",
                "description": "Woody debris and by-products from forestry operations. Rich in lignocellulosic material, ideal for thermochemical conversion.",
                "composition": "Cellulose, hemicellulose, lignin",
                "uses": "Bio-oil, biochar, heat and power",
                "related_processes": "Fast Pyrolysis, Gasification"
            },
            102: {
                "name": "Straw",
                "category": "Agricultural Residue",
                "description": "Stalks and stems left after grain harvest. Used as feedstock for bioenergy and soil amendment.",
                "composition": "Cellulose, hemicellulose, silica",
                "uses": "Bio-oil, animal bedding, compost",
                "related_processes": "Fast Pyrolysis"
            },
            201: {
                "name": "Bio-oil",
                "category": "Liquid Fuel",
                "description": "Dark brown liquid from fast pyrolysis, used as a renewable fuel or chemical feedstock.",
                "composition": "Complex mixture of oxygenated organics",
                "uses": "Fuel, chemicals, energy",
                "related_processes": "Fast Pyrolysis"
            },
            202: {
                "name": "Biochar",
                "category": "Solid Carbon Product",
                "description": "Carbon-rich solid from pyrolysis, used for soil enhancement and carbon sequestration.",
                "composition": "Fixed carbon, ash, volatile matter",
                "uses": "Soil amendment, carbon sink",
                "related_processes": "Fast Pyrolysis"
            },
            203: {
                "name": "Syngas",
                "category": "Gas Fuel",
                "description": "Mixture of CO, H<sub>2</sub>, and small hydrocarbons from gasification or pyrolysis.",
                "composition": "CO, H<sub>2</sub>, CH<sub>4</sub>",
                "uses": "Energy, chemical synthesis",
                "related_processes": "Fast Pyrolysis, Gasification"
            },
            204: {
                "name": "Biogas",
                "category": "Gas Fuel",
                "description": "Renewable methane-rich gas from anaerobic digestion of organic matter.",
                "composition": "CH<sub>4</sub>, CO<sub>2</sub>, trace gases",
                "uses": "Heat, electricity, vehicle fuel",
                "related_processes": "Anaerobic Digestion"
            },
            205: {
                "name": "Digestate",
                "category": "Soil Amendment",
                "description": "Nutrient-rich residue from anaerobic digestion, used as fertilizer.",
                "composition": "Organic matter, NPK nutrients",
                "uses": "Fertilizer, soil conditioner",
                "related_processes": "Anaerobic Digestion"
            },
        }
        return {"material": data.get(material_id)}


class ProcessRunMock(TemplateView):
    template_name = "processes/mock_run.html"

    def get_context_data(self, **kwargs):
        pt_id = self.kwargs.get('pk')
        return {"process_type": {"id": pt_id, "name": f"Mock ProcessType #{pt_id}"}}
