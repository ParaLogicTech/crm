// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Sales Person", {
	setup(frm) {
		frm.set_query("parent_sales_person", () => {
			return {
				filters: [
					["Sales Person", "is_group", "=", 1],
					["Sales Person", "name", "!=", frm.doc.sales_person_name],
				],
			};
		});
	},

	refresh(frm) {
		frm.events.set_root_readonly(frm);
	},

	set_root_readonly(frm) {
		// read-only for root sales person
		if (!frm.doc.parent_sales_person && !frm.doc.__islocal) {
			frm.disable_form();
			frm.set_intro(__("This is a root sales person and cannot be edited."));
		} else {
			frm.set_intro(null);
		}
	},
});
