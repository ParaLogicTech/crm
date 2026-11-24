// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.provide("crm");

crm.CustomerFeedback = class CustomerFeedback extends frappe.ui.form.Controller {
	setup() {
		this.setup_queries();
	}

	refresh() {
		this.set_feedback_from();
		this.set_sales_person_from_user();
		this.update_dynamic_fields();
		this.set_dynamic_link();
	}

	setup_queries() {
		let me = this;

		me.frm.set_query("contact_person", frappe.contacts.contact_query);

		me.frm.set_query("feedback_from", () => {
			return {
				"filters": {
					"name": ["in", crm.utils.get_feedback_allowed_party_types()],
				},
			};
		});

		me.frm.set_query("feedback_sub_type", () => {
			return {
				filters: {
					feedback_type: this.frm.doc.feedback_type,
				},
			};
		});

		me.frm.set_query("feedback_status", () => {
			return {
				filters: {
					feedback_type: ["in", [this.frm.doc.feedback_type, ""]],
				},
			};
		});
	}

	set_feedback_from() {
		let allowed_party_types = crm.utils.get_feedback_allowed_party_types();
		if (allowed_party_types.length == 1 && !this.frm.doc.feedback_from) {
			this.frm.set_value("feedback_from", allowed_party_types[0]);
			this.frm.set_df_property("feedback_from", "hidden", 1);
		}
	}

	feedback_from() {
		this.set_dynamic_link();
		this.update_dynamic_fields();
		this.frm.set_value("party_name", "");
	}

	contact_person() {
		return crm.utils.get_contact_details(this.frm, "feedback_from");
	}

	party_name() {
		return this.get_customer_details();
	}

	update_dynamic_fields() {
		let me = this;

		if (this.frm.doc.feedback_from) {
			me.frm.set_df_property("party_name", "label", __(me.frm.doc.feedback_from));
			me.frm.set_df_property("contact_person", "label", __(me.frm.doc.feedback_from + " Contact Person"));
		} else {
			me.frm.set_df_property("party_name", "label", __("Party"));
			me.frm.set_df_property("contact_person", "label", __("Contact Person"));
		}
	}

	set_dynamic_link() {
		frappe.dynamic_link = {
			doc: this.frm.doc,
			fieldname: "party_name",
			doctype: this.frm.doc.feedback_from || "Lead",
		};
	}

	get_customer_details() {
		if (this.frm.doc.feedback_from && this.frm.doc.party_name) {
			return frappe.call({
				method: "crm.crm.doctype.customer_feedback.customer_feedback.get_customer_details",
				args: {
					args: {
						doctype: this.frm.doc.doctype,
						feedback_from: this.frm.doc.feedback_from,
						party_name: this.frm.doc.party_name,
						project: this.frm.doc.project,
					},
				},
				callback: (r) => {
					if (r.message && !r.exc) {
						for (let key in r.message) {
							if (Object.hasOwn(r.message, key) && this.frm.fields_dict[key]) {
								this.frm.set_value(key, r.message[key]);
							}
						}
					}
				},
			});
		}
	}

	reference_doctype() {
		this.frm.set_value("reference_name", null);
	}

	reference_name() {
		return this.determine_party();
	}

	determine_party() {
		if (this.frm.doc.reference_doctype && this.frm.doc.reference_name && !this.frm.doc.party_name) {
			return this.frm.call({
				method: "determine_party_from_reference_name",
				doc: this.frm.doc,
				callback: () => {
					this.frm.refresh_fields();
				},
			});
		}
	}

	feedback_type() {
		if (this.frm.doc.feedback_type) {
			this.frm.set_value("feedback_sub_type", null);
			this.frm.set_value("feedback_status", null);
		}
	}

	set_sales_person_from_user() {
		if (!this.frm.get_field("sales_person") || this.frm.doc.sales_person || !this.frm.doc.__islocal) {
			return;
		}

		crm.utils.get_sales_person_from_user(sales_person => {
			if (sales_person) {
				this.frm.set_value("sales_person", sales_person);
			}
		});
	}
};

extend_cscript(cur_frm.cscript, new crm.CustomerFeedback({frm: cur_frm}));
