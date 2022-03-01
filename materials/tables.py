from django.urls import reverse
from django.utils.html import format_html
from django_tables2 import Column, Table


def averages_table_factory(group_settings):
    table_data = []
    composition_set = group_settings.average_composition
    for share in composition_set.materialcomponentshare_set.all():
        remove_html = format_html(
            '''
            <a href="{0}" class="collapse multi-collapse">
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
            'fraction': f'{share.as_percentage}',
            'remove': remove_html
        }
        table_data.append(table_row)
    if len(table_data) == 0:
        table_data.append({
            'component': None,
            'fraction': None,
        })

    footers = {
        'component': format_html(
            '''
            <a href="{0}" class="modal-link collapse multi-collapse">
                <i class="fas fa-fw fa-plus"></i> Add component
            </a>
            ''',
            reverse('add_component', kwargs={'pk': group_settings.id})
        ),
        'fraction': format_html(
            '''
            <a href="{0}" class="modal-link collapse multi-collapse">
                <i class="fas fa-fw fa-edit"></i> Change composition
            </a>
            ''',
            reverse('compositionset-update-modal', kwargs={'pk': group_settings.average_composition.id})
        )
    }
    columns = {
        'component': Column(footer=footers['component']),
        'fraction': Column(footer=footers['fraction']),
        'remove': Column(attrs={"td": {"class": "collapse multi-collapse"}, "th": {"class": "collapse multi-collapse"}})
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
            <a href="{0}" class="modal-link collapse multi-collapse">
                <i class="fas fa-fw fa-edit"></i>
            </a>
            ''',
            reverse('compositionset-update-modal', kwargs={'pk': cs.id}))

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
