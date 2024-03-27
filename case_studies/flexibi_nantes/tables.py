from django.urls import reverse
from django.utils.html import format_html
from django_tables2 import Column, Table


def growthcycle_table_factory(growth_cycle):
    table_data = []
    for component in growth_cycle.group_settings.components():
        table_row = {'component': component.name}
        shares = growth_cycle.shares.filter(
            component=component,
            timestepset__timestep__in=growth_cycle.timesteps
        )
        for share in shares:
            table_row[share.timestep.name] = f'{share.average}'
        table_data.append(table_row)
    if len(table_data) == 0:
        table_row = {'component': None}
        for timestep in growth_cycle.timesteps:
            table_row[timestep.name] = None
        table_data.append(table_row)

    def footer(ts):
        return format_html(
            '''
            <a href="javascript:void(0);" class="modal-link toggle-edit", data-link="{0}">
                <i class="fas fa-fw fa-edit"></i>
            </a>
            ''',
            reverse('growth_cycle_timestep_update', kwargs={'pk': ts.id})
        )

    if len(table_data) > 0:
        columns = {}
        for name in list(table_data[0].keys()):
            if not name == 'component':
                timestep_set = growth_cycle.growthtimestepset_set.get(timestep__name=name)
                columns[name] = Column(footer=footer(timestep_set))
            else:
                columns[name] = Column()
        columns['id'] = f'distribution-table-group-{growth_cycle.id}'
    else:
        columns = {}
    sequence = ['component']
    for timestep in growth_cycle.timesteps.order_by('id'):
        sequence.append(timestep.name)
    inner_meta = type('Meta', (), {'sequence': tuple(sequence)})
    columns.update({'Meta': inner_meta})
    table_class = type(f'DistributionTable-{growth_cycle.id}', (Table,), columns)
    return table_class(table_data)
