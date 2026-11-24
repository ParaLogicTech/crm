import frappe
from frappe.model.base_document import get_controller


def boot_session(bootinfo):
	if frappe.session.user != "Guest":
		if frappe.session.data.user_type == "System User":
			update_page_info(bootinfo)
			update_allowed_party_types(bootinfo)


def update_page_info(bootinfo):
	bootinfo.page_info.update({
		"Territory Tree": {
			"title": "Territory Tree",
			"route": "Tree/Territory",
		},
		"Sales Person Tree": {
			"title": "Sales Person Tree",
			"route": "Tree/Sales Person",
		},
	})


def update_allowed_party_types(bootinfo):
	bootinfo.opportunity_allowed_party_types = get_controller("Opportunity").get_allowed_party_types()
	bootinfo.appointment_allowed_party_types = get_controller("Appointment").get_allowed_party_types()
	bootinfo.feedback_allowed_party_types = get_controller("Customer Feedback").get_allowed_party_types()
