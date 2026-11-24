frappe.listview_settings["Customer Feedback"] = {
	get_indicator: function(doc) {
		let color;
		if (doc.status == "Pending") {
			color = "orange";
		} else if (doc.status == "Completed") {
			color = "green";
		}
		return [__(doc.status), color, "status,=," + doc.status];
	},

	onload: function(listview) {
		if (listview.page.fields_dict.feedback_from) {
			listview.page.fields_dict.feedback_from.get_query = function() {
				return {
					"filters": {
						"name": ["in", crm.utils.get_feedback_allowed_party_types()],
					},
				};
			};
		}
	},
};
