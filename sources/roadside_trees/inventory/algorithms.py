from distributions.plots import Distribution
from inventories.algorithms import InventoryAlgorithmsBase
from inventories.models import Scenario
from materials.models import ComponentMeasurement, SampleSeries
from sources.roadside_trees.models import HamburgRoadsideTrees
from sources.urban_green_spaces.models import HamburgGreenAreas


class InventoryAlgorithms(InventoryAlgorithmsBase):
    @classmethod
    def hamburg_park_production(cls, **kwargs):
        keep_columns = ["anlagenname", "belegenheit", "gruenart", "nutzcode"]

        kwargs.update({"source_model": HamburgGreenAreas})
        kwargs.update({"keep_columns": keep_columns})
        return super().avg_area_yield(**kwargs)

    @classmethod
    def hamburg_roadside_tree_production(cls, **kwargs):
        kwargs.update({"source_model": HamburgRoadsideTrees})
        result = super().avg_point_yield(**kwargs)

        scenario = Scenario.objects.get(id=kwargs.get("scenario_id"))
        feedstock = SampleSeries.objects.get(id=kwargs.get("feedstock_id"))

        result["aggregated_distributions"] = []

        inv_shares = feedstock.inventoryamountshare_set.filter(
            scenario=scenario
        ).select_related("timestep__distribution")
        if not inv_shares.exists():
            return result

        temporal_distribution = inv_shares.first().timestep.distribution

        distribution = Distribution(
            temporal_distribution,
            name="Seasonal production per component",
        )

        total_production = 0
        for agg_val in result["aggregated_values"]:
            if agg_val["name"] == "Total production":
                total_production = agg_val["value"]
        temp_dist = {share.timestep_id: share.average for share in inv_shares}
        component_measurements = ComponentMeasurement.objects.filter(
            sample__series=feedstock,
            group__name="Macro Components",
        ).select_related("sample__timestep__distribution", "component")

        seasonal_measurements = [
            m
            for m in component_measurements
            if m.sample.timestep.distribution_id == temporal_distribution.id
        ]

        if seasonal_measurements:
            for measurement in seasonal_measurements:
                amount_share = temp_dist.get(measurement.sample.timestep.id)
                if amount_share is None:
                    continue
                value = (
                    float(measurement.average)
                    * float(amount_share)
                    * float(total_production)
                )
                distribution.add_share(
                    measurement.sample.timestep, measurement.component, value
                )
        else:
            average_measurements = [
                m
                for m in component_measurements
                if m.sample.timestep.distribution.name == "Average"
            ]
            for inv_share in inv_shares:
                for measurement in average_measurements:
                    value = (
                        float(measurement.average)
                        * float(inv_share.average)
                        * float(total_production)
                    )
                    distribution.add_share(
                        inv_share.timestep, measurement.component, value
                    )

        result["aggregated_distributions"].append(distribution.serialize())

        return result


__all__ = ["InventoryAlgorithms"]
