from frappe import _


def get_data():
	return {
		"fieldname": "lead",
		"non_standard_fieldnames": {
			"Opportunity": "party_name",
			"Appointment": "party_name",
		},
		"transactions": [
			{
				"label": _("CRM"),
				"items": ["Opportunity", "Appointment"],
			},
		],
	}
