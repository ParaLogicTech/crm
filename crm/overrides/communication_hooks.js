frappe.ui.form.on("Communication", {
	refresh: (frm) => {
		// setup custom Make button only if Communication is Email
		if(frm.doc.communication_medium == "Email" && frm.doc.sent_or_received == "Received") {
			frm.events.setup_crm_buttons(frm);
		}
	},

	setup_crm_buttons: (frm) => {
		let confirm_msg = "Are you sure you want to create {0} from this email?";
		if (!in_list(["Lead", "Opportunity"], frm.doc.reference_doctype)) {
			frm.add_custom_button(__("Lead"), () => {
				frappe.confirm(__(confirm_msg, [__("Lead")]), () => {
					frm.trigger('make_lead_from_communication');
				})
			}, __('Create'));

			frm.add_custom_button(__("Opportunity"), () => {
				frappe.confirm(__(confirm_msg, [__("Opportunity")]), () => {
					frm.trigger('make_opportunity_from_communication');
				})
			}, __('Create'));
		}
	},

	make_lead_from_communication: (frm) => {
		return frappe.call({
			method: "crm.crm.doctype.lead.lead.make_lead_from_communication",
			args: {
				communication: frm.doc.name
			},
			freeze: true,
			callback: (r) => {
				if(r.message) {
					frm.reload_doc()
				}
			}
		})
	},

	make_opportunity_from_communication: (frm) => {
		const fields = [{
			fieldtype: 'Link',
			label: __('Select a Company'),
			fieldname: 'company',
			options: 'Company',
			reqd: 1,
			default: frappe.defaults.get_user_default("Company")
		}];

		frappe.prompt(fields, data => {
			frappe.call({
				method: "crm.crm.doctype.opportunity.opportunity.make_opportunity_from_communication",
				args: {
					communication: frm.doc.name,
					company: data.company
				},
				freeze: true,
				callback: (r) => {
					if(r.message) {
						frm.reload_doc();
						frappe.show_alert({
							message: __("Opportunity {0} created",
								['<a href="/app/opportunity/'+r.message+'">' + r.message + '</a>']),
							indicator: 'green'
						});
					}
				}
			});
		},
		'Create an Opportunity',
		'Create');
	}
});