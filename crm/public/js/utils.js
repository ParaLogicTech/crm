frappe.provide("crm.utils");

$.extend(crm.utils, {
	get_sales_person_from_user: function (callback) {
		return frappe.call({
			method: "crm.crm.doctype.sales_person.sales_person.get_sales_person_from_user",
			callback: function (r) {
				if (!r.exc && callback) {
					callback(r.message);
				}
			}
		});
	},

	get_service_advisor_from_user: function (callback) {
		return frappe.call({
			method: "crm.crm.doctype.sales_person.sales_person.get_service_advisor_from_user",
			callback: function (r) {
				if (!r.exc && callback) {
					callback(r.message);
				}
			}
		});
	},

	get_advisor_sales_person_from_user: function (callback) {
		return frappe.call({
			method: "crm.crm.doctype.sales_person.sales_person.get_advisor_sales_person_from_user",
			callback: function (r) {
				if (r.message && callback) {
					callback(r.message);
				}
			}
		});
	},

	get_contact_details: function(frm, party_type_field) {
		if (frm.updating_party_details) {
			return;
		}

		let lead = crm.utils.get_lead_from_doc(frm, party_type_field);

		return frappe.call({
			method: "crm.crm.utils.get_contact_details",
			args: {
				contact: frm.doc.contact_person || "",
				lead: lead,
			},
			callback: function(r) {
				if (r.message) {
					return frm.set_value(r.message);
				}
			}
		});
	},

	get_address_display: function(frm, party_type_field, address_field, display_field) {
		if (frm.updating_party_details) {
			return;
		}

		let lead = crm.utils.get_lead_from_doc(frm, party_type_field);

		return frappe.call({
			method: "crm.crm.utils.get_address_display",
			args: {
				address: frm.doc[address_field] || "",
				lead: lead
			},
			callback: function(r) {
				if (!r.exc) {
					frm.set_value(display_field, r.message);
				}
			}
		})
	},

	get_lead_from_doc: function (frm, party_type_field) {
		if (frm.doc.party_name && frm.doc[party_type_field] === "Lead") {
			return frm.doc.party_name
		}
	},

	set_as_lost_dialog: function(frm) {
		let dialog = new frappe.ui.Dialog({
			title: __("Mark As Lost"),
			fields: [
				{
					"fieldtype": "Table MultiSelect",
					"label": __("Lost Reasons"),
					"fieldname": "lost_reason",
					"options": 'Lost Reason Detail',
					"reqd": 1
				},
				{
					"fieldtype": "Text",
					"label": __("Detailed Reason"),
					"fieldname": "detailed_reason"
				},
			],
			primary_action: () => {
				let values = dialog.get_values();
				let reasons = values["lost_reason"];
				let detailed_reason = values["detailed_reason"];

				crm.utils.update_lost_status(frm, true, reasons, detailed_reason);
				dialog.hide();
			},
			primary_action_label: __('Declare Lost')
		});

		dialog.show();
	},

	update_lost_status: function(frm, is_lost, lost_reasons_list=null, detailed_reason=null) {
		return frappe.call({
			doc: frm.doc,
			method: "set_is_lost",
			args: {
				'is_lost': cint(is_lost),
				'lost_reasons_list': lost_reasons_list,
				'detailed_reason': detailed_reason
			},
			callback: (r) => {
				if (!r.exc) {
					frm.reload_doc();
				}
			}
		});
	},

	get_opportunity_allowed_party_types: function () {
		return frappe.boot.opportunity_allowed_party_types || ["Lead"];
	},
	get_appointment_allowed_party_types: function () {
		return frappe.boot.appointment_allowed_party_types || ["Lead"];
	},
	get_feedback_allowed_party_types: function () {
		return frappe.boot.feedback_allowed_party_types || ["Lead"];
	},
});
