// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

frappe.ui.form.on("Territory", {
	setup(frm) {
		frm.set_query("parent_territory", () => {
			return {
				filters: [
					["Territory", "is_group", "=", 1],
					["Territory", "name", "!=", frm.doc.territory_name],
				],
			};
		});
	},

	refresh(frm) {
		frm.events.set_root_readonly(frm);
	},

	set_root_readonly(frm) {
		// read-only for root territory
		if (!frm.doc.parent_territory && !frm.doc.__islocal) {
			frm.set_read_only();
			frm.set_intro(__("This is a root territory and cannot be edited."));
		} else {
			frm.set_intro(null);
		}
	},
});
