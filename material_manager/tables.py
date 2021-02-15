from django.urls import reverse
from django.utils.html import format_html
from django_tables2 import Column, Table


def averages_table_factory(group_settings):
    table_data = []
    composition_set = group_settings.average_composition
    for share in composition_set.materialcomponentshare_set.all():
        remove_html = format_html(
            '''
            <a href="{0}" class="toggle-edit">
                <i class="fas fa-fw fa-trash"></i>
            </a>
            ''',
            reverse('material_component_group_remove_component', kwargs={
                'pk': group_settings.id,
                'component_pk': share.component.id
            })
        )
        table_row = {
            'component': share.component.name,
            'weight fraction': f'{share.average} +- {share.standard_deviation}',
            'remove': remove_html
        }
        table_data.append(table_row)
    if len(table_data) == 0:
        table_data.append({
            'component': None,
            'weight fraction': None,
        })

    footers = {
        'component': format_html(
            '''
            <a href="javascript:void(0);" class="modal-link toggle-edit" data-link="{0}">
                <i class="fas fa-fw fa-plus"></i> Add component
            </a>
            ''',
            reverse('add_component', kwargs={'pk': group_settings.id})
        ),
        'weight fraction': format_html(
            '''
            <a href="javascript:void(0);" class="modal-link toggle-edit" data-link="{0}">
                <i class="fas fa-fw fa-edit"></i> Change composition
            </a>
            ''',
            reverse('composition_set_update', kwargs={'pk': group_settings.average_composition.id})
        )
    }
    columns = {
        'component': Column(footer=footers['component']),
        'weight fraction': Column(footer=footers['weight fraction']),
        'remove': Column(attrs={"td": {"class": "toggle-edit"}, "th": {"class": "toggle-edit"}})
    }
    table_class = type(f'AveragesTable{group_settings.id}', (Table,), columns)
    return table_class(table_data)


def distribution_table_factory(group_settings, distribution):
    table_data = []
    for component in group_settings.components():
        table_row = {'component': component.name}
        shares = group_settings.shares.filter(
            component=component,
            composition_set__timestep__in=distribution.timestep_set.all()
        )
        for share in shares:
            table_row[share.timestep.name] = f'{share.average}'
        table_data.append(table_row)
    if len(table_data) == 0:
        table_row = {'component': None}
        for timestep in distribution.timestep_set.all():
            table_row[timestep.name] = None
        table_data.append(table_row)

    def footer(cs):
        return format_html(
            '''
            <a href="javascript:void(0);" class="modal-link toggle-edit", data-link="{0}">
                <i class="fas fa-fw fa-edit"></i>
            </a>
            ''',
            reverse('composition_set_update', kwargs={'pk': cs.id}))

    if len(table_data) > 0:
        columns = {}
        for name in list(table_data[0].keys()):
            if not name == 'component':
                composition_set = group_settings.compositionset_set.get(timestep__name=name)
                columns[name] = Column(footer=footer(composition_set))
            else:
                columns[name] = Column()
        columns['id'] = f'distribution-table-group-{group_settings.id}-dist-{distribution.id}'
    else:
        columns = {}
    sequence = ['component']
    for timestep in distribution.timestep_set.all().order_by('id'):
        sequence.append(timestep.name)
    inner_meta = type('Meta', (), {'sequence': tuple(sequence)})
    columns.update({'Meta': inner_meta})
    table_class = type(f'DistributionTable-{group_settings.id}-{distribution.id}', (Table,), columns)
    return table_class(table_data)
