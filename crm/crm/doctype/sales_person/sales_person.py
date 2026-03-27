# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import cint
from frappe.utils.nestedset import NestedSet, get_root_of


class SalesPerson(NestedSet):
	nsm_parent_field = 'parent_sales_person'

	def validate(self):
		self.set_missing_parent_sales_person()

	def on_update(self):
		super(SalesPerson, self).on_update()
		self.validate_one_root()

	def set_missing_parent_sales_person(self):
		if not self.parent_sales_person:
			self.parent_sales_person = get_root_of("Sales Person")

	@staticmethod
	def get_timeline_data(name):
		out = dict(frappe.db.sql("""
			select unix_timestamp(dt.transaction_date), count(dt.name)
			from `tabOpportunity` dt
			where dt.sales_person = %s and dt.transaction_date > date_sub(curdate(), interval 1 year)
			group by dt.transaction_date
		""", name))

		return out


def on_doctype_update():
	frappe.db.add_index("Sales Person", ["lft", "rgt"])


@frappe.whitelist()
def get_service_advisor_from_user(user=None):
	details = get_advisor_sales_person_from_user(user)
	return details.sales_person if details.is_service_advisor else None


@frappe.whitelist()
def get_advisor_sales_person_from_user(user=None):
	out = frappe._dict({
		"sales_person": get_sales_person_from_user(user),
		"is_service_advisor": 0,
	})

	if out.sales_person:
		out.is_service_advisor = cint(frappe.get_cached_value("Sales Person", out.sales_person, "is_service_advisor"))

	return out


@frappe.whitelist()
def get_sales_person_from_user(user=None):
	user = user or frappe.session.user
	return frappe.db.get_value("Sales Person", {"user_id": user, "enabled": 1})