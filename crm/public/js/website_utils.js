frappe.provide("erpnext");
frappe.provide("crm");

Object.assign(crm, {
	// Lead Form API
	// opts: {
	// 	args: { sender, message, subject, full_name, organization, designation, mobile_no, phone_no, country, opportunity_args: {}},
	// 	callback: Function,
	// 	error: Function
	// }
	send_message: function(opts, btn) {
		return frappe.call({
			type: "POST",
			method: "crm.crm.doctype.opportunity.opportunity.make_opportunity_from_lead_form",
			btn: btn,
			args: opts.args,
			callback: opts.callback,
			error: opts.error,
			always: opts.always,
		});
	},

	// Newsletter subscription API
	// opts: {
	// 	email: String,
	// 	email_group: String,
	// 	callback: Function,
	// 	error: Function,
	// 	always: Function,
	// }
	subscribe_to_newsletter: function(opts, btn) {
		return frappe.call({
			type: "POST",
			method: "frappe.email.doctype.newsletter.newsletter.subscribe",
			btn: btn,
			args: {
				email: opts.email,
				email_group: opts.email_group || undefined,
			},
			callback: opts.callback,
			error: opts.error,
			always: opts.always,
		});
	},

	// Utility to bind newsletter subscription email input and button
	// opts: {
	// 	loading_label: String,
	// 	subscribed_label: String,
	// 	error_label: String,
	// 	confirmation_sent_label: String,
	// 	email_group: String
	// 	success: Function,
	// 	error: Function,
	// 	always: Function,
	// }
	bind_newsletter_subscription: function($email_input, $subscribe_btn, opts) {
		if (!opts) opts = {};
		if (!opts.loading_label) opts.loading_label = __("Subscribing...");
		if (!opts.subscribed_label) opts.subscribed_label = __("Subscribed");
		if (!opts.error_label) opts.error_label = __("Error");
		if (!opts.confirmation_sent_label) opts.confirmation_sent_label = __("Sent");

		// handle enter key
		$($email_input).off("keypress").on("keypress", function(e) {
			if (e.key === "Enter") {
				e.preventDefault();
				$subscribe_btn.click();
			}
		});

		// handle submit
		$($subscribe_btn).off("click").on("click", function(e) {
			e.preventDefault();

			let email = strip($email_input.val()).toLowerCase();
			if (!email) {
				return;
			}

			if (!validate_email(email)) {
				frappe.msgprint(__("<b>{0}</b> is not a valid email address", [email]));
				return;
			}

			$email_input.attr("disabled", true);
			$subscribe_btn.html(opts.loading_label).attr("disabled", true);

			let handle_error = () => {
				$email_input.val("").attr("disabled", false);
				$subscribe_btn.html(opts.error_label).attr("disabled", false);

				opts.error && opts.error();
			};

			erpnext.subscribe_to_newsletter({
				email: email,
				email_group: opts.email_group,
				callback: (r) => {
					if (r.message == "subscribed") {
						$subscribe_btn.html(opts.subscribed_label).attr("disabled", true);
						$email_input.attr("disabled", true);

						opts.callback && opts.callback(r);
					} else if (r.message == "confirmation") {
						$subscribe_btn.html(opts.confirmation_sent_label).attr("disabled", true);
						$email_input.attr("disabled", true);

						opts.callback && opts.callback(r);
					} else {
						handle_error();
					}
				},
				error: () => {
					handle_error();
				},
			});
		});
	},
});

// Backwards compatibility
frappe.send_message = erpnext.send_message = crm.send_message;
frappe.subscribe_to_newsletter = erpnext.subscribe_to_newsletter = crm.subscribe_to_newsletter;
