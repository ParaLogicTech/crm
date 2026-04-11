from frappe import _


def get_data():
	return {
		'non_standard_fieldnames': {},
		'heatmap': True,
		'heatmap_message': _('This is based on transactions against this Sales Person.'),
		'fieldname': 'sales_person',
		'transactions': [
			{
				'label': _('CRM'),
				'items': ['Lead', 'Opportunity']
			},
		]
	}
