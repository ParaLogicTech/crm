from frappe import _


def get_data():
	return {
		"fieldname": "campaign",
		"non_standard_fieldnames": {
			"Email Campaign": "campaign_name",
		},
		"transactions": [
			{
				"label": _("Leads"),
				"items": ["Lead", "Opportunity"],
			},
			{
				"label": _("Email Campaigns"),
				"items": ["Email Campaign"],
			},
		],
	}
