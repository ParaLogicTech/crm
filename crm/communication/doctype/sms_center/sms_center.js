// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

extend_cscript(cur_frm.cscript, {
	refresh() {
		this.frm.disable_save();
		this.frm.page.set_primary_action(__("Send SMS"), () => {
			return this.send_sms();
		});

		this.frm.fields_dict.receiver_list.$input.css("height", "500px");
		this.frm.fields_dict.message.$input.css("height", "477px");
	},

	send_sms() {
		frappe.confirm(__("Are you sure you want to send this SMS?"), () => {
			return this.frm.call({
				method: "send_sms",
				doc: this.frm.doc,
				freeze: 1,
				freeze_message: __("Sending SMS"),
			});
		});
	},

	create_receiver_list() {
		return this.frm.call({
			method: "create_receiver_list",
			doc: this.frm.doc,
			freeze: 1,
			freeze_message: __("Creating Receiver List"),
			callback: () => {
				this.set_message_count();
			},
		});
	},

	receiver_list() {
		let receivers = cstr(this.frm.doc.receiver_list).split("\n").filter(d => d);
		this.frm.set_value("total_receivers", receivers.length);
	},

	message() {
		this.set_message_count();
	},

	set_message_count() {
		let total_characters = cstr(this.frm.doc.message).length;
		let total_msg = 1;

		if (total_characters > 160) {
			total_msg = cint(total_characters / 160);
			total_msg = total_characters % 160 == 0 ? total_msg : total_msg + 1;
		}

		this.frm.set_value("total_characters", total_characters);
		this.frm.set_value("total_messages_per_receiver", this.frm.doc.message ? total_msg : 0);
		this.frm.set_value("total_messages", this.frm.doc.message ? total_msg * cint(this.frm.doc.total_receivers) : 0);
	},
});
