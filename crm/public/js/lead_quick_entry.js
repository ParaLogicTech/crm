frappe.provide('frappe.ui.form');

frappe.ui.form.LeadQuickEntryForm = class LeadQuickEntryForm extends frappe.ui.form.QuickEntryForm {
	skip_redirect_on_error = true

	render_dialog() {
		let additional_fields = this.get_lead_fields();
		let additional_fieldnames = additional_fields.map(f => f.fieldname);
		this.mandatory = this.mandatory.filter(f => !additional_fieldnames.includes(f.fieldname));
		this.mandatory = this.mandatory.filter(d => d.fieldname != 'status');
		this.mandatory = this.mandatory.concat(additional_fields);
		super.render_dialog();
		this.setup_events();
		this.set_sales_person_from_user();
	}

	setup_events() {
		let me = this;

		if (me.dialog.fields_dict["tax_id"]) {
			me.dialog.fields_dict["tax_id"].df.onchange = () => {
				var value = me.dialog.get_value('tax_id');
				value = frappe.regional.get_formatted_tax_id(value);
				me.dialog.doc.tax_id = value;
				me.dialog.get_field('tax_id').refresh();
				frappe.regional.validate_duplicate_tax_id(me.dialog.doc, "tax_id");
			};
		}

		if (me.dialog.fields_dict["tax_cnic"]) {
			me.dialog.fields_dict["tax_cnic"].df.onchange = () => {
				var value = me.dialog.get_value('tax_cnic');
				value = frappe.regional.get_formatted_cnic(value);
				me.dialog.doc.tax_cnic = value;
				me.dialog.get_field('tax_cnic').refresh();
				frappe.regional.validate_duplicate_tax_id(me.dialog.doc, "tax_cnic");
			};
		}

		if (me.dialog.fields_dict["tax_strn"]) {
			me.dialog.fields_dict["tax_strn"].df.onchange = () => {
				var value = me.dialog.get_value('tax_strn');
				value = frappe.regional.get_formatted_strn(value);
				me.dialog.doc.tax_strn = value;
				me.dialog.get_field('tax_strn').refresh();
				frappe.regional.validate_duplicate_tax_id(me.dialog.doc, "tax_strn");
			};
		}

		if (me.dialog.fields_dict["mobile_no"]) {
			me.dialog.fields_dict["mobile_no"].df.onchange = () => {
				var value = me.dialog.get_value('mobile_no');
				value = frappe.regional.get_formatted_mobile_no(value);
				me.dialog.doc.mobile_no = value;
				me.dialog.get_field('mobile_no').refresh();
			};
		}

		if (me.dialog.fields_dict["mobile_no_2"]) {
			me.dialog.fields_dict["mobile_no_2"].df.onchange = () => {
				var value = me.dialog.get_value('mobile_no_2');
				value = frappe.regional.get_formatted_mobile_no(value);
				me.dialog.doc.mobile_no_2 = value;
				me.dialog.get_field('mobile_no_2').refresh();
			};
		}
	}

	set_sales_person_from_user() {
		var me = this;
		if (!me.dialog.get_field('sales_person') || me.dialog.doc.sales_person || !me.dialog.doc.__islocal) {
			return;
		}

		crm.utils.get_sales_person_from_user(sales_person => {
			if (sales_person) {
				me.dialog.doc.sales_person = sales_person;
				me.dialog.get_field('sales_person').refresh();
			}
		});
	}

	get_lead_fields() {
		return [
			{
				fieldtype: "Section Break",
				label: __("Source"),
			},
			{
				label: __("Lead Source"),
				fieldname: "source",
				fieldtype: "Link",
				options: "Lead Source"
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Territory"),
				fieldname: "territory",
				fieldtype: "Link",
				options: "Territory"
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Sales Person"),
				fieldname: "sales_person",
				fieldtype: "Link",
				options: "Sales Person"
			},
			{
				fieldtype: "Section Break",
				label: __("Contact Details"),
			},
			{
				label: __("Mobile Number (Primary)"),
				fieldname: "mobile_no",
				fieldtype: "Data"
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Mobile Number (Secondary"),
				fieldname: "mobile_no_2",
				fieldtype: "Data"
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Phone Number"),
				fieldname: "phone_no",
				fieldtype: "Data"
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Email Id"),
				fieldname: "email_id",
				fieldtype: "Data"
			},

			{
				fieldtype: "Section Break",
				label: __("Address Details"),
			},
			{
				label: __("Address Line 1"),
				fieldname: "address_line1",
				fieldtype: "Data"
			},
			{
				label: __("Address Line 2"),
				fieldname: "address_line2",
				fieldtype: "Data"
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("City"),
				fieldname: "city",
				fieldtype: "Data"
			},
			{
				label: __("State"),
				fieldname: "state",
				fieldtype: "Data"
			},
			{
				label: __("Country"),
				fieldname: "country",
				fieldtype: "Link",
				options: "Country"
			},

			{
				fieldtype: "Section Break",
				label: __("Identification & Tax Id"),
			},
			{
				label: __("CNIC"),
				fieldname: "tax_cnic",
				fieldtype: "Data"
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("Tax Id"),
				fieldname: "tax_id",
				fieldtype: "Data"
			},
			{
				fieldtype: "Column Break"
			},
			{
				label: __("STRN"),
				fieldname: "tax_strn",
				fieldtype: "Data"
			},
		];
	}
};