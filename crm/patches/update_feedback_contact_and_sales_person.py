import frappe
from crm.crm.utils import _get_contact_details
from frappe.contacts.doctype.contact.contact import get_default_contact

user_to_sales_person = {}


def execute():
	feedbacks_for_contact = frappe.get_all(
		"Customer Feedback",
		fields=["name", "feedback_from", "party_name", "contact_person"],
		filters={
			"feedback_from": ['is', 'set'],
			"party_name": ['is', 'set'],
			"contact_person": ['is', 'not set'],
		}
	)
	feedbacks_for_sales_person = frappe.get_all(
		"Customer Feedback",
		fields=["name", "owner"],
		filters={
			"sales_person": ['is', 'not set'],
		}
	)

	for fb in feedbacks_for_contact:
		lead = fb.party_name if fb.feedback_from == "Lead" else None

		contact_person = fb.contact_person
		if fb.feedback_from != "Lead":
			contact_person = get_default_contact(fb.feedback_from, fb.party_name)

		if contact_person:
			contact_details = _get_contact_details(contact_person, lead=lead) or {}
			frappe.db.set_value("Customer Feedback", fb.name, {
				"contact_person": contact_person,
				"contact_display": contact_details.get("contact_display"),
				"contact_mobile": contact_details.get("contact_mobile"),
				"contact_phone": contact_details.get("contact_phone"),
				"contact_email": contact_details.get("contact_email")
			}, update_modified=False)

	for fb in feedbacks_for_sales_person:
		sales_person = get_sales_person(fb.owner)
		if sales_person:
			frappe.db.set_value("Customer Feedback", fb.name, "sales_person", sales_person, update_modified=False)


def get_sales_person(user):
	from crm.crm.doctype.sales_person.sales_person import get_sales_person_from_user

	if not user:
		return None

	if user not in user_to_sales_person:
		user_to_sales_person[user] = get_sales_person_from_user(user)

	return user_to_sales_person[user]
