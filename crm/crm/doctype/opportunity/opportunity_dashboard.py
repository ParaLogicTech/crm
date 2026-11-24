from frappe import _


def get_data():
	return {
		"fieldname": "opportunity",
		"transactions": [
			{
				"label": _("Appointment"),
				"items": ["Appointment"],
			},
		],
	}
