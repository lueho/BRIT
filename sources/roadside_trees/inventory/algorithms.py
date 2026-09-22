from distributions.models import TemporalDistribution, Timestep
from distributions.plots import Distribution
from inventories.algorithms import InventoryAlgorithmsBase
from inventories.models import InventoryInput, Scenario
from materials.models import ComponentMeasurement
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
        input_id = kwargs.get("inventory_input_id", kwargs.get("feedstock_id"))
        feedstock = InventoryInput.objects.get(id=input_id)

        result["aggregated_distributions"] = []

        if not feedstock.is_temporal:
            macro_measurements = feedstock.sample.component_measurements.filter(
                group__name="Macro Components"
            ).select_related("component")
            if not macro_measurements.exists():
                return result

            total_production = 0
            for agg_val in result["aggregated_values"]:
                if agg_val["name"] == "Total production":
                    total_production = agg_val["value"]

            average_distribution = TemporalDistribution.objects.default()
            average_timestep = Timestep.objects.get(
                distribution=average_distribution, name="Average"
            )
            distribution = Distribution(
                average_distribution,
                name="Seasonal production per component",
            )
            for measurement in macro_measurements:
                distribution.add_share(
                    average_timestep,
                    measurement.component,
                    float(measurement.average) * float(total_production),
                )
            result["aggregated_distributions"].append(distribution.serialize())
            return result

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
            sample__series=feedstock.series,
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
