frappe.listview_settings["Appointment"] = {
	add_fields: ["status", "docstatus", "end_dt"],
	get_indicator: function(doc) {
		if (doc.status == "Open") {
			var is_late = false;
			if (doc.end_dt) {
				var now_dt = moment(frappe.datetime.now_datetime(true));
				var end_dt = frappe.datetime.str_to_obj(doc.end_dt);

				if (now_dt.isAfter(end_dt)) {
					is_late = true;
				}
			}

			if (is_late) {
				return [__("Late"), "yellow", "status,=," + doc.status];
			} else {
				return [__(doc.status), "orange", "status,=," + doc.status];
			}
		} else if (doc.status == "Rescheduled") {
			return [__(doc.status), "light-blue", "status,=," + doc.status];
		} else if (doc.status == "Checked In") {
			return [__(doc.status), "blue", "status,=," + doc.status];
		} else if (doc.status == "Missed") {
			return [__(doc.status), "grey", "status,=," + doc.status];
		} else if (["Closed", "Converted"].includes(doc.status)) {
			return [__(doc.status), "green", "status,=," + doc.status];
		}
	},

	onload: function(listview) {
		if (listview.page.fields_dict.appointment_for) {
			listview.page.fields_dict.appointment_for.get_query = function() {
				return {
					"filters": {
						"name": ["in", crm.utils.get_appointment_allowed_party_types()],
					},
				};
			};
		}
	},
};
