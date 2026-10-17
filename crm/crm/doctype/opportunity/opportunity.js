// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("crm");

crm.Opportunity = class Opportunity extends frappe.ui.form.Controller {
	setup() {
		this.frm.custom_make_buttons = {
			"Appointment": "Appointment",
		};

		this.frm.email_field = "contact_email";
		this.setup_queries();
	}

	refresh() {
		this.set_opportunity_from();
		this.set_dynamic_link();
		this.update_dynamic_fields();
		this.set_sales_person_from_user();
		this.setup_buttons();
	}

	setup_buttons() {
		if (!this.frm.doc.__islocal) {
			if (this.frm.perm[0].write) {
				this.frm.add_custom_button(__("Submit Communication"), () => this.submit_communication());

				if (!["Lost", "Closed", "Converted"].includes(this.frm.doc.status)) {
					this.frm.add_custom_button(__("Lost"), () => {
						crm.utils.set_as_lost_dialog(this.frm);
					}, __("Status"));

					this.frm.add_custom_button(__("Close"), () => {
						this.frm.set_value("status", "Closed");
						this.frm.save();
					}, __("Status"));
				}

				if (["Lost", "Closed"].includes(this.frm.doc.status)) {
					this.frm.add_custom_button(__("Reopen"), () => {
						if (this.frm.doc.status == "Lost") {
							crm.utils.update_lost_status(this.frm, false);
						} else {
							this.frm.set_value("lost_reasons", [])
							this.frm.set_value("order_lost_reason", null)
							this.frm.set_value("status", "Open");
							this.frm.save();
						}
					}, __("Status"));
				}
			}

			if (this.frm.doc.status !== "Lost") {
				if (!this.frm.doc.conversion_document || this.frm.doc.conversion_document == "Appointment") {
					this.frm.add_custom_button(__('Appointment'), () => this.create_appointment(),
						__("Create"));
				}
			}

			if (this.frm.page.get_inner_group_button(__("Create")).length) {
				this.frm.page.set_inner_btn_group_as_primary(__("Create"));
			}
		}
	}

	setup_queries() {
		let me = this;

		me.frm.set_query("opportunity_from", () => {
			return {
				"filters": {
					"name": ["in", crm.utils.get_opportunity_allowed_party_types()],
				}
			}
		});

		me.frm.set_query('customer_address', frappe.contacts.address_query);
		me.frm.set_query('contact_person', frappe.contacts.contact_query);
	}

	set_opportunity_from() {
		let allowed_party_types = crm.utils.get_opportunity_allowed_party_types();
		if (allowed_party_types.length == 1 && !this.frm.doc.opportunity_from) {
			this.frm.set_value("opportunity_from", allowed_party_types[0]);
			this.frm.set_df_property("opportunity_from", "hidden", 1);
		}
	}

	update_dynamic_fields() {
		let me = this;

		if (me.frm.doc.opportunity_from) {
			me.frm.set_df_property("party_name", "label", __(me.frm.doc.opportunity_from));
			me.frm.set_df_property("customer_address", "label", __(me.frm.doc.opportunity_from + " Address"));
			me.frm.set_df_property("contact_person", "label", __(me.frm.doc.opportunity_from + " Contact Person"));
		} else {
			me.frm.set_df_property("party_name", "label", __("Party"));
			me.frm.set_df_property("customer_address", "label", __("Address"));
			me.frm.set_df_property("contact_person", "label", __("Contact Person"));
		}
	}

	set_dynamic_link() {
		frappe.dynamic_link = {
			doc: this.frm.doc,
			fieldname: 'party_name',
			doctype: this.frm.doc.opportunity_from || "Lead"
		}
	}

	set_sales_person_from_user() {
		if (!this.frm.get_field('sales_person') || this.frm.doc.sales_person || !this.frm.doc.__islocal) {
			return;
		}

		crm.utils.get_sales_person_from_user(sales_person => {
			if (sales_person) {
				this.frm.set_value('sales_person', sales_person);
			}
		});
	}

	opportunity_from() {
		this.set_dynamic_link();
		this.update_dynamic_fields();
		this.frm.set_value("party_name", "");
	}

	opportunity_type() {
		this.setup_buttons()
		this.update_dynamic_fields()
	}

	contact_person() {
		return crm.utils.get_contact_details(this.frm, "opportunity_from");
	}

	customer_address() {
		return crm.utils.get_address_display(this.frm, "opportunity_from", "customer_address", "address_display");
	}

	party_name() {
		return this.get_customer_details();
	}

	get_customer_details() {
		let me = this;

		if (me.frm.doc.opportunity_from && me.frm.doc.party_name) {
			return frappe.call({
				method: "crm.crm.doctype.opportunity.opportunity.get_customer_details",
				args: {
					args: {
						doctype: me.frm.doc.doctype,
						opportunity_from: me.frm.doc.opportunity_from,
						party_name: me.frm.doc.party_name,
					}
				},
				callback: function (r) {
					if (r.message && !r.exc) {
						return me.frm.set_value(r.message);
					}
				}
			});
		}
	}

	submit_communication() {
		this.frm.check_if_unsaved();

		let prev_followup = this.frm.doc.contact_schedule.find(element => !element.contact_date);

		const dialog = new frappe.ui.Dialog({
			title: __('Submit Communication'),
			doc: {
				prev_follow_up_remarks: prev_followup && prev_followup.to_discuss,
				prev_follow_up_date: prev_followup && prev_followup.schedule_date,
			},
			fields: [
				{
					fieldname: "remarks",
					fieldtype: "Small Text",
					label: __("Remarks"),
					reqd: 1
				},
				{
					fieldtype: "Section Break", depends_on: "eval:doc.prev_follow_up_remarks || doc.prev_follow_up_date"
				},
				{
					label : "Follow Up Remarks",
					fieldname: "prev_follow_up_remarks",
					fieldtype: "Small Text",
					read_only: 1
				},
				{
					fieldtype: "Column Break"
				},
				{
					label : "Follow Up Date",
					fieldname: "prev_follow_up_date",
					fieldtype: "Date",
					read_only: 1
				},
				{
					fieldtype: "Section Break"
				},
				{
					fieldname: "action",
					fieldtype: "Select",
					label: __("Action"),
					reqd: 1,
					options: ["", "Submit Remarks Only", "Schedule Follow Up", "Mark As Lost", "Mark As Closed", "Create Appointment"],
					onchange: () => {
						let is_followup = dialog.get_value("action") == "Schedule Follow Up";
						let is_lost = dialog.get_value("action") == "Mark As Lost";

						dialog.set_df_property("schedule_date", "reqd", is_followup ? 1 : 0);
						dialog.set_df_property("follow_up_days", "reqd", is_followup ? 1 : 0);

						dialog.set_df_property("lost_reason", "reqd", is_lost ? 1 : 0);
					}
				},
				{fieldtype: "Section Break", depends_on: "eval:doc.action == 'Schedule Follow Up'"},
				{
					label : "Follow Up in Days",
					fieldname: "follow_up_days",
					fieldtype: "Int",
					onchange: () => {
						let today = frappe.datetime.nowdate();
						let contact_date = frappe.datetime.add_days(today, dialog.get_value('follow_up_days'));
						dialog.set_value('schedule_date', contact_date);
					}
				},
				{fieldtype: "Column Break"},
				{
					label : "Schedule Date",
					fieldname: "schedule_date",
					fieldtype: "Date",
					onchange: () => {
						let today = frappe.datetime.get_today();
						let schedule_date = dialog.get_value('schedule_date');
						dialog.doc.follow_up_days = frappe.datetime.get_diff(schedule_date, today);
						dialog.get_field('follow_up_days').refresh();
					}
				},
				{fieldtype: "Section Break", depends_on: "eval:doc.action == 'Mark As Lost'"},
				{
					fieldtype: "Table MultiSelect",
					label: __("Lost Reasons"),
					fieldname: "lost_reason",
					options: 'Lost Reason Detail',
				},
			],
			primary_action: (dialog_data) => {
				return frappe.call({
					method: "crm.crm.doctype.opportunity.opportunity.submit_communication_with_action",
					args: {
						opportunity: this.frm.doc.name,
						remarks: dialog_data.remarks,
						action: dialog_data.action,
						follow_up_date: dialog_data.schedule_date,
						lost_reason: dialog_data.lost_reason,
						detailed_reason: dialog_data.detailed_reason,
					},
					callback: (r) => {
						if (r.message) {
							dialog.hide();

							this.frm.reload_doc();

							if (r.message.appointment_doc) {
								frappe.model.sync(r.message.appointment_doc);
								frappe.set_route("Form", r.message.appointment_doc.doctype, r.message.appointment_doc.name);
							}
						}
					},
				});
			}
		});
		dialog.show();
	}

	create_appointment() {
		frappe.model.open_mapped_doc({
			method: "crm.crm.doctype.opportunity.opportunity.make_appointment",
			frm: this.frm
		});
	}

	contact_schedule_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		this.set_follow_up_sales_person_from_user(row);
	}

	set_follow_up_sales_person_from_user(row) {
		if (row.sales_person) {
			return;
		}

		crm.utils.get_sales_person_from_user(sales_person => {
			if (sales_person) {
				frappe.model.set_value(row.doctype, row.name, 'sales_person', sales_person);
			}
		});
	}

};

extend_cscript(cur_frm.cscript, new crm.Opportunity({frm: cur_frm}));
