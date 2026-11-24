frappe.listview_settings["Lead"] = {
	add_fields: ["status"],
	get_indicator: function(doc) {
		let indicator = [__(doc.status), frappe.utils.guess_colour(doc.status), "status,=," + doc.status];

		if (doc.status == "Lead") {
			indicator[1] = "yellow";
		} else if (doc.status == "Open") {
			indicator[1] = "orange";
		} else if (["Replied", "Interested"].includes(doc.status)) {
			indicator[1] = "purple";
		} else if (doc.status == "Opportunity") {
			indicator[1] = "blue";
		} else if (["Lost Opportunity", "Not Interested"].includes(doc.status)) {
			indicator[1] = "gray";
		} else if (doc.status == "Converted") {
			indicator[1] = "green";
		}
		return indicator;
	},
};
