# Copyright (c) 2013, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, nowdate, format_time, format_datetime, now_datetime
from crm.crm.doctype.appointment.appointment import get_appointments_for_reminder_notification,\
	get_appointment_reminders_scheduled_time, get_reminder_date_from_appointment_date, automated_reminder_enabled


class AppointmentSheetReport(object):
	date_format = "d/MM/y"
	time_format = "hh:mm a"
	datetime_format = "{0}, {1}".format(date_format, time_format)

	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})
		self.filters.from_date = getdate(self.filters.from_date or nowdate())
		self.filters.to_date = getdate(self.filters.to_date or nowdate())

	def run(self):
		self.get_data()
		self.get_project_data()
		self.get_reminder_data()
		self.process_data()
		columns = self.get_columns()
		return columns, self.data

	def get_data(self):
		conditions = self.get_conditions()
		conditions_str = "and {}".format(" and ".join(conditions)) if conditions else ""

		select_fields = self.get_select_fields()
		select_fields_str = ", ".join(select_fields)

		self.data = frappe.db.sql(f"""
			select {select_fields_str}
			from `tabAppointment` a
			left join `tabNotification Count` n on n.reference_doctype = 'Appointment' and n.reference_name = a.name
				and n.notification_type = 'Appointment Reminder'
			where a.docstatus = 1 {conditions_str}
			group by a.name
			order by a.scheduled_dt, a.creation
		""", self.filters, as_dict=1)

	def get_select_fields(self):
		return [
			"a.name as appointment", "a.appointment_type", "a.appointment_source", "a.service_advisor",
			"a.voice_of_customer", "a.remarks",
			"a.scheduled_dt", "a.scheduled_date", "a.scheduled_time", "a.appointment_duration", "a.end_dt",
			"a.appointment_for", "a.party_name", "a.customer_name",
			"a.contact_display", "a.contact_mobile", "a.contact_phone", "a.contact_email",
			"a.applies_to_variant_of", "a.applies_to_variant_of_name", "a.applies_to_item", "a.applies_to_item_name",
			"max(n.last_sent_dt) as last_sent_dt", "a.confirmation_dt", "a.status", "a.owner"
		]

	def get_project_data(self):
		appointment_list = [d.appointment for d in self.data]

		if appointment_list:
			project_data = frappe.db.sql("""
				SELECT name as project, appointment, project_type
				FROM tabProject
				WHERE appointment in %s
			""", [appointment_list], as_dict=1)

			project_map = {d.appointment: d for d in project_data}

			for d in self.data:
				project_details = project_map.get(d.appointment, {})
				d.project = project_details.get("project")
				d.project_type = project_details.get("project_type")

	def get_reminder_data(self):
		if automated_reminder_enabled():
			now_dt = now_datetime()
			scheduled_dates = set([d.scheduled_date for d in self.data if d.scheduled_dt > now_dt and not d.last_sent_dt])

			for current_date in scheduled_dates:
				reminder_date = get_reminder_date_from_appointment_date(current_date)
				scheduled_reminder_dt = get_appointment_reminders_scheduled_time(reminder_date)
				appointments_for_reminder = get_appointments_for_reminder_notification(reminder_date)

				for d in self.data:
					if d.appointment in appointments_for_reminder:
						d.scheduled_reminder_dt = scheduled_reminder_dt

		for d in self.data:
			if d.last_sent_dt:
				d.reminder = "Last Sent: {0}".format(format_datetime(d.last_sent_dt, self.datetime_format))
			elif d.scheduled_reminder_dt:
				d.reminder = "Scheduled: {0}".format(format_datetime(d.scheduled_reminder_dt, self.datetime_format))

	def process_data(self):
		for d in self.data:
			d.contact_number = d.contact_mobile or d.contact_phone

			# Model Name if not a variant
			if not d.applies_to_variant_of_name:
				d.applies_to_variant_of_name = d.applies_to_item_name

			if d.get("project_type"):
				self.filters.has_project_type = True

			# Date/Time Formatting
			self.set_formatted_datetime(d)

	def set_formatted_datetime(self, d):
		d.scheduled_dt_fmt = format_datetime(d.scheduled_dt, self.datetime_format)
		d.scheduled_time_fmt = format_time(d.scheduled_time, self.time_format)

		d.confirmation_dt_fmt = format_datetime(d.confirmation_dt, self.datetime_format)

	def get_conditions(self):
		conditions = []

		if self.filters.get("company"):
			conditions.append("a.company = %(company)s")

		if self.filters.get("from_date"):
			conditions.append("a.scheduled_date >= %(from_date)s")

		if self.filters.get("to_date"):
			conditions.append("a.scheduled_date <= %(to_date)s")

		if self.filters.get("appointment_type"):
			conditions.append("a.appointment_type = %(appointment_type)s")

		if self.filters.get("service_advisor"):
			lft, rgt = frappe.db.get_value("Sales Person", self.filters.service_advisor, ["lft", "rgt"])
			conditions.append("""a.service_advisor in (select name from `tabSales Person`
				where lft >= {0} and rgt <= {1})""".format(lft, rgt))

		return conditions

	def get_columns(self):
		columns = [
			{'label': _("Appointment"), 'fieldname': 'appointment', 'fieldtype': 'Link', 'options': 'Appointment', 'width': 100},
			{'label': _("Date"), 'fieldname': 'scheduled_date', 'fieldtype': 'Date', 'width': 80},
			{'label': _("Time"), 'fieldname': 'scheduled_time_fmt', 'fieldtype': 'Data', 'width': 70},
			{'label': _("Party"), 'fieldname': 'party_name', 'fieldtype': 'Dynamic Link', 'options': 'appointment_for', 'width': 80},
			{'label': _("Customer Name"), 'fieldname': 'customer_name', 'fieldtype': 'Data', 'width': 150},
			{'label': _("Contact #"), 'fieldname': 'contact_number', 'fieldtype': 'Data', 'width': 100},
			{"label": _("Item"), "fieldname": "applies_to_variant_of_name", "fieldtype": "Data", "width": 120},
			{"label": _("Item Code"), "fieldname": "applies_to_item", "fieldtype": "Link", "options": "Item", "width": 120},
		]

		columns += [
			{"label": _("Voice of Customer"), "fieldname": "voice_of_customer", "fieldtype": "Data", "width": 200},
			{'label': _("Status"), 'fieldname': 'status', 'fieldtype': 'Data', 'width': 80},
			{'label': _("Service Advisor"), 'fieldname': 'service_advisor', 'fieldtype': 'Link', 'options': "Sales Person", 'width': 110},
			{"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 200, "editable": 1},
			{'label': _("Project"), 'fieldname': 'project', 'fieldtype': 'Link', 'width': 100, 'options': 'Project'},
			{'label': _("Project Type"), 'fieldname': 'project_type', 'fieldtype': 'Link', 'width': 100, 'options': 'Project Type'},
			{'label': _("Source"), 'fieldname': 'appointment_source', 'fieldtype': 'Data', 'width': 100},
			{"label": _("Reminder"), "fieldname": "reminder", "fieldtype": "Data", "width": 200},
			{"label": _("Confirmation Time"), "fieldname": "confirmation_dt_fmt", "fieldtype": "Data", "width": 140},
			{'label': _("Created By"), 'fieldname': 'owner', 'fieldtype': 'Link', "options": "User", "width": 150},
		]

		if not self.filters.has_project_type:
			columns = [c for c in columns if c.get("fieldname") != "project_type"]

		return columns


def execute(filters=None):
	return AppointmentSheetReport(filters).run()
