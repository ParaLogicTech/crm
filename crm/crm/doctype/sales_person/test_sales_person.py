# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from datetime import datetime

import frappe
from frappe.utils import add_days, add_years, getdate, nowdate

from crm.crm.doctype.sales_person.sales_person import (
	SalesPerson,
	get_advisor_sales_person_from_user,
	get_sales_person_from_user,
	get_service_advisor_from_user,
)
from crm.tests.utils import CRMTestCase

test_records = frappe.get_test_records("Sales Person")

test_ignore = ["Item Group"]


class TestSalesPerson(CRMTestCase):
	def test_parent_defaults_to_root(self):
		sales_person = make_sales_person(parent_sales_person=None)
		self.assertEqual(sales_person.parent_sales_person, "Sales Team")

	def test_tree_position(self):
		team = make_sales_person(is_group=1, is_service_advisor=0)
		member = make_sales_person(parent_sales_person=team.name)
		team.reload()

		self.assertTrue(team.lft < member.lft < member.rgt < team.rgt)

	def test_sales_person_from_user(self):
		user = make_user()
		self.assertIsNone(get_sales_person_from_user(user))

		sales_person = make_sales_person(user_id=user, is_service_advisor=0)
		self.assertEqual(get_sales_person_from_user(user), sales_person.name)

		sales_person.enabled = 0
		sales_person.save()
		self.assertIsNone(get_sales_person_from_user(user))

	def test_sales_person_from_session_user(self):
		user = make_user()
		sales_person = make_sales_person(user_id=user)

		frappe.set_user(user)
		try:
			self.assertEqual(get_sales_person_from_user(), sales_person.name)
		finally:
			frappe.set_user("Administrator")

	def test_service_advisor_from_user(self):
		user = make_user()
		sales_person = make_sales_person(user_id=user, is_service_advisor=0)

		self.assertEqual(
			get_advisor_sales_person_from_user(user),
			{"sales_person": sales_person.name, "is_service_advisor": 0},
		)
		self.assertIsNone(get_service_advisor_from_user(user))

		sales_person.is_service_advisor = 1
		sales_person.save()
		self.assertEqual(
			get_advisor_sales_person_from_user(user),
			{"sales_person": sales_person.name, "is_service_advisor": 1},
		)
		self.assertEqual(get_service_advisor_from_user(user), sales_person.name)

	def test_user_without_sales_person(self):
		user = make_user()
		self.assertEqual(
			get_advisor_sales_person_from_user(user), {"sales_person": None, "is_service_advisor": 0},
		)
		self.assertIsNone(get_service_advisor_from_user(user))

	def test_timeline_data(self):
		from crm.crm.doctype.opportunity.test_opportunity import make_opportunity

		sales_person = make_sales_person()
		other = make_sales_person()

		recent = add_days(nowdate(), -10)
		make_opportunity(sales_person=sales_person.name, transaction_date=recent)
		make_opportunity(sales_person=sales_person.name, transaction_date=recent)
		make_opportunity(sales_person=sales_person.name, transaction_date=add_years(nowdate(), -2))
		make_opportunity(sales_person=other.name, transaction_date=recent)

		timeline = SalesPerson.get_timeline_data(sales_person.name)
		self.assertEqual(
			{getdate(datetime.fromtimestamp(timestamp)): count for timestamp, count in timeline.items()},
			{getdate(recent): 2},
		)


def make_sales_person(**kwargs):
	sales_person = frappe.get_doc(
		{
			"doctype": "Sales Person",
			"sales_person_name": "_Test Sales Person " + frappe.generate_hash(length=8),
			"parent_sales_person": "Sales Team",
			"is_service_advisor": 1,
		},
	)
	sales_person.update(kwargs)
	sales_person.insert()
	return sales_person


def make_user():
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": f"_test_sales_person_{frappe.generate_hash(length=8)}@example.com",
			"first_name": "_Test Sales Person User",
			"send_welcome_email": 0,
		},
	)
	user.insert()
	return user.name
