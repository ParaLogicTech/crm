// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.provide("crm");

crm.LeadController = class LeadController extends frappe.ui.form.Controller {
	setup() {
		this.frm.custom_make_buttons = {
			"Opportunity": "Opportunity",
		};

		this.frm.email_field = "email_id";
	}

	refresh() {
		this.set_dynamic_link();
		this.set_sales_person_from_user();
		this.setup_buttons();

		this.frm.toggle_reqd("lead_name", !this.frm.doc.organization_lead);

		if (!this.frm.doc.__islocal) {
			frappe.contacts.render_address_and_contact(this.frm);
		} else {
			frappe.contacts.clear_address_and_contact(this.frm);
		}
	}

	validate() {
		frappe.regional.format_tax_id(this.frm, "tax_id");
		frappe.regional.format_cnic(this.frm, "tax_cnic");
		frappe.regional.format_strn(this.frm, "tax_strn");

		frappe.regional.format_mobile_no(this.frm, "mobile_no");
		frappe.regional.format_mobile_no(this.frm, "mobile_no_2");
	}

	set_dynamic_link() {
		frappe.dynamic_link = {doc: this.frm.doc, fieldname: "name", doctype: "Lead"};
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

	setup_buttons() {
		if (!this.frm.doc.__islocal) {
			this.frm.add_custom_button(__("Opportunity"), () => this.make_opportunity(),
				__("Create"));
		}
	}

	make_opportunity() {
		frappe.model.open_mapped_doc({
			method: "crm.crm.doctype.lead.lead.make_opportunity",
			frm: this.frm,
		});
	}

	organization_lead() {
		this.frm.toggle_reqd("lead_name", !this.frm.doc.organization_lead);
		this.frm.toggle_reqd("company_name", this.frm.doc.organization_lead);
	}

	company_name() {
		if (this.frm.doc.organization_lead == 1) {
			this.frm.set_value("lead_name", this.frm.doc.company_name);
		}
	}

	tax_id() {
		frappe.regional.format_tax_id(this.frm, "tax_id");
		frappe.regional.validate_duplicate_tax_id(this.frm.doc, "tax_id");
	}
	tax_cnic() {
		frappe.regional.format_cnic(this.frm, "tax_cnic");
		frappe.regional.validate_duplicate_tax_id(this.frm.doc, "tax_cnic");
	}
	tax_strn() {
		frappe.regional.format_strn(this.frm, "tax_strn");
		frappe.regional.validate_duplicate_tax_id(this.frm.doc, "tax_strn");
	}

	mobile_no() {
		frappe.regional.format_mobile_no(this.frm, "mobile_no");
	}
	mobile_no_2() {
		frappe.regional.format_mobile_no(this.frm, "mobile_no_2");
	}
};

extend_cscript(cur_frm.cscript, new crm.LeadController({frm: cur_frm}));
