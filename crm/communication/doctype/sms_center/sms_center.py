# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.core.doctype.sms_settings.sms_settings import clean_receiver_number, send_sms
from frappe.model.document import Document
from frappe.utils import cint, cstr, get_datetime, now_datetime

# Receivers that come from ERPNext DocTypes, which a site with only crm doesn't have
erpnext_send_to_doctypes = {
	"All Customer Contact": "Customer",
	"All Supplier Contact": "Supplier",
	"All Sales Partner Contact": "Sales Partner",
	"All Employee (Active)": "Employee",
}


class SMSCenter(Document):
	@frappe.whitelist()
	def create_receiver_list(self):
		self.validate_send_to_installed()

		receivers = []

		if self.send_to in ["All Contact", "All Customer Contact", "All Supplier Contact", "All Sales Partner Contact"]:
			self.is_promotional = 1

			conditions = []
			join = "inner join `tabDynamic Link` dl on dl.parent = c.name and dl.parenttype = 'Contact'"

			if self.send_to == "All Customer Contact":
				conditions.append("dl.link_doctype = 'Customer'")
				if self.customer:
					conditions.append("dl.link_name = {0}".format(frappe.db.escape(self.customer)))
			elif self.send_to == "All Supplier Contact":
				conditions.append("dl.link_doctype = 'Supplier'")
				if self.supplier:
					conditions.append("dl.link_name = {0}".format(frappe.db.escape(self.supplier)))
			elif self.send_to == "All Sales Partner Contact":
				conditions.append("dl.link_doctype = 'Sales Partner'")
				if self.sales_partner:
					conditions.append("dl.link_name = {0}".format(frappe.db.escape(self.sales_partner)))
			else:
				join = ""

			conditions = " and {0}".format(" and ".join(conditions)) if conditions else ""
			receivers = frappe.db.sql("""
				select distinct c.full_name, c.mobile_no
				from `tabContact` c
				{0}
				where ifnull(c.mobile_no,'') != '' {1}
				order by c.full_name
			""".format(join, conditions))

		elif self.send_to == "All Lead (Open)":
			self.is_promotional = 1

			receivers = frappe.db.sql("""
				select lead_name, mobile_no
				from `tabLead`
				where ifnull(mobile_no, '') != '' and status = 'Open'
				order by lead_name
			""")

		elif self.send_to == "All Employee (Active)":
			conditions = []
			if self.department:
				conditions.append("department = {0}".format(frappe.db.escape(self.department)))
			if self.branch:
				conditions.append("branch = {0}".format(frappe.db.escape(self.branch)))

			conditions = " and {0}".format(" and ".join(conditions)) if conditions else ""

			receivers = frappe.db.sql("""
				select employee_name, cell_number
				from `tabEmployee`
				where status = 'Active' and ifnull(cell_number, '') != '' {0}
				order by employee_name
			""".format(conditions))

		elif self.send_to == "All Sales Person":
			receivers = frappe.db.sql("""
				select sp.name, sp.contact_mobile
				from `tabSales Person` sp
				where ifnull(sp.contact_mobile,'') != ''
				order by sp.name
			""")

		numbers_visited = set()
		receiver_list = []
		for r in receivers:
			name, number = r
			number = clean_receiver_number(number, format_sms=True)

			if not number or number in numbers_visited:
				continue

			if name:
				receiver_list.append(f"{name} | {number}")
			else:
				receiver_list.append(number)

			numbers_visited.add(number)

		self.receiver_list = "\n".join(receiver_list)
		self.total_receivers = len(receiver_list)

	def validate_send_to_installed(self):
		doctype = erpnext_send_to_doctypes.get(self.send_to)
		if not doctype or frappe.db.table_exists(doctype):
			return

		frappe.throw(_("Cannot create a receiver list for {0} because {1} is not installed").format(
			frappe.bold(_(self.send_to)), _(doctype),
		))

	def get_receiver_nos(self):
		receiver_nos = []
		if self.receiver_list:
			for d in self.receiver_list.split("\n"):
				receiver_no = cstr(d)
				if "|" in d:
					receiver_no = receiver_no.split("|")[-1]

				receiver_no = cstr(receiver_no).strip()
				if receiver_no:
					receiver_nos.append(receiver_no)

		return receiver_nos

	@frappe.whitelist()
	def send_sms(self):
		if not self.message:
			frappe.throw(_("Please enter message before sending"))

		receiver_list = self.get_receiver_nos()
		if not receiver_list:
			frappe.throw(_("Receiver List is empty. Please create Receiver List"))

		if self.send_after and get_datetime(self.send_after) < now_datetime():
			frappe.throw(_("Schedule Send Time cannot be in the past"))

		queue = bool(self.send_after or len(receiver_list) > 10)
		send_sms(
			receiver_list,
			message=cstr(self.message),
			is_promotional=cint(self.is_promotional),
			reference_doctype="SMS Center",
			reference_name="SMS Center",
			queue=queue,
			queue_separately=True,
			send_after=self.send_after,
			priority=0,
		)

		if queue:
			frappe.msgprint(_("SMS has been scheduled to send"), indicator="green")
