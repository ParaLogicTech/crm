import frappe
from frappe.utils import cstr


@frappe.whitelist()
def get_address_display(address=None, lead=None):
	return render_address(address, lead=lead, check_permissions=True)


def render_address(address=None, lead=None, check_permissions=False):
	from frappe.contacts.doctype.address.address import render_address
	from crm.crm.doctype.lead.lead import get_lead_address_details

	out = None

	if address:
		out = render_address(address, check_permissions=check_permissions)
	elif lead:
		lead_address_details = get_lead_address_details(lead, check_permissions=check_permissions)
		out = render_address(lead_address_details)

	return out


@frappe.whitelist()
def get_contact_details(
	contact=None,
	lead=None,
	get_contact_no_list=False,
	link_doctype=None,
	link_name=None,
):
	return _get_contact_details(
		contact,
		lead=lead,
		get_contact_no_list=get_contact_no_list,
		link_doctype=link_doctype,
		link_name=link_name,
		check_permissions=True,
	)


def _get_contact_details(
	contact=None,
	lead=None,
	get_contact_no_list=False,
	link_doctype=None,
	link_name=None,
	check_permissions=False,
):
	from frappe.contacts.doctype.contact.contact import _get_contact_details
	from crm.crm.doctype.lead.lead import _get_lead_contact_details

	if contact:
		out = _get_contact_details(
			contact,
			get_contact_no_list=get_contact_no_list,
			link_doctype=link_doctype,
			link_name=link_name,
			check_permissions=check_permissions,
		)
	elif lead:
		out = _get_lead_contact_details(lead, check_permissions=check_permissions)
	else:
		out = _get_contact_details(None, check_permissions=check_permissions)

	return out


@frappe.whitelist()
def get_last_interaction(contact=None, lead=None):

	if not contact and not lead: return

	last_communication = None
	last_issue = None
	if contact:
		query_condition = ''
		values = []
		contact = frappe.get_doc('Contact', contact)
		for link in contact.links:
			if link.link_doctype == 'Customer':
				last_issue = get_last_issue_from_customer(link.link_name)
			query_condition += "(`reference_doctype`=%s AND `reference_name`=%s) OR"
			values += [link.link_doctype, link.link_name]

		if query_condition:
			# remove extra appended 'OR'
			query_condition = query_condition[:-2]
			last_communication = frappe.db.sql("""
				SELECT `name`, `content`
				FROM `tabCommunication`
				WHERE `sent_or_received`='Received'
				AND ({})
				ORDER BY `modified`
				LIMIT 1
			""".format(query_condition), values, as_dict=1)  # nosec

	if lead:
		last_communication = frappe.get_all('Communication', filters={
			'reference_doctype': 'Lead',
			'reference_name': lead,
			'sent_or_received': 'Received'
		}, fields=['name', 'content'], order_by='`creation` DESC', limit=1)

	last_communication = last_communication[0] if last_communication else None

	return {
		'last_communication': last_communication,
		'last_issue': last_issue
	}


def get_last_issue_from_customer(customer_name):
	issues = frappe.get_all('Issue', {
		'customer': customer_name
	}, ['name', 'subject', 'customer'], order_by='`creation` DESC', limit=1)

	return issues[0] if issues else None


def get_scheduled_employees_for_popup(communication_medium):
	if not communication_medium: return []

	now_time = frappe.utils.nowtime()
	weekday = frappe.utils.get_weekday()

	available_employee_groups = frappe.get_all("Communication Medium Timeslot", filters={
		'day_of_week': weekday,
		'parent': communication_medium,
		'from_time': ['<=', now_time],
		'to_time': ['>=', now_time],
	}, fields=['employee_group'])

	available_employee_groups = tuple([emp.employee_group for emp in available_employee_groups])

	employees = frappe.get_all('Employee Group Table', filters={
		'parent': ['in', available_employee_groups]
	}, fields=['user_id'])

	employee_emails = set([employee.user_id for employee in employees])

	return employee_emails


def strip_number(number):
	if not number: return
	# strip 0 from the start of the number for proper number comparisions
	# eg. 07888383332 should match with 7888383332
	number = number.lstrip('0')
	return number
