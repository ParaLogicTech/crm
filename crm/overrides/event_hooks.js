// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.provide("frappe.desk");

frappe.ui.form.on("Event", {
	refresh: function(frm) {
		frm.set_query("reference_doctype", "event_participants", function() {
			return {
				"filters": {
					"name": ["in", ["Contact", "Lead"]],
				},
			};
		});

		frm.add_custom_button(__("Add Leads"), function() {
			new frappe.desk.eventParticipants(frm, "Lead");
		}, __("Add Participants"));
	},
});
