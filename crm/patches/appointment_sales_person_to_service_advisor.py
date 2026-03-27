import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	appointment_sales_person_field_exists = frappe.db.has_column("Appointment", "sales_person")

	frappe.delete_doc_if_exists("Property Setter", "Appointment Type-sales_persons-label")
	frappe.delete_doc_if_exists("Property Setter", "Appointment-sales_person-label")

	if frappe.db.exists("DocType", "Appointment Sales Person"):
		frappe.rename_doc("DocType", "Appointment Sales Person", "Appointment Service Advisor", force=True)

	frappe.reload_doc("crm", "doctype", "sales_person")
	frappe.reload_doc("crm", "doctype", "appointment_service_advisor")
	frappe.reload_doc("crm", "doctype", "appointment_type")
	frappe.reload_doc("crm", "doctype", "appointment_source")
	frappe.reload_doc("crm", "doctype", "appointment")

	rename_field("Appointment Service Advisor", "sales_person", "service_advisor")

	rename_field("Appointment Source", "sales_person_non_mandatory", "service_advisor_non_mandatory")

	rename_field("Appointment Type", "sales_persons", "service_advisors")
	rename_field("Appointment Type", "validate_sales_person_availability", "validate_service_advisor_availability")
	rename_field("Appointment Type", "sales_person_mandatory", "service_advisor_mandatory")
	rename_field("Appointment Type", "sales_person_validate_self", "service_advisor_validate_self")

	if appointment_sales_person_field_exists:
		rename_field("Appointment", "sales_person", "service_advisor")
		frappe.db.sql("update `tabAppointment` set sales_person = null")

	frappe.db.sql("""
		update `tabAppointment` apt
		inner join `tabOpportunity` opp on opp.name = apt.opportunity
		set apt.sales_person = opp.sales_person
		where apt.sales_person is null or apt.sales_person = ''
	""")

	frappe.db.sql("""
		update `tabSales Person` sp
		set is_service_advisor = 1
		where exists(
			select asa.name from `tabAppointment Service Advisor` asa where asa.service_advisor = sp.name
		)
	""")
