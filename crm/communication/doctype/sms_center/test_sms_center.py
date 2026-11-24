# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.utils import now_datetime

from crm.crm.doctype.lead.test_lead import make_lead
from crm.crm.doctype.opportunity.test_opportunity import make_opportunity
from crm.crm.doctype.sales_person.test_sales_person import make_sales_person
from crm.tests.utils import CRMTestCase

# Links to ERPNext DocTypes, which don't exist on a site with only crm
test_ignore = ["Customer", "Supplier", "Sales Partner", "Department", "Branch"]


class TestSMSCenterReceivers(CRMTestCase):
	def test_all_contacts(self):
		make_contact("_Test SMS Zara", "0300-1110001")
		make_contact("_Test SMS Adil", "0300 1110002")
		without_mobile = make_contact("_Test SMS No Mobile", None)

		sms_center = get_receiver_list("All Contact")
		receivers = sms_center.receiver_list.split("\n")

		self.assertIn("_Test SMS Zara | 03001110001", receivers)
		self.assertIn("_Test SMS Adil | 03001110002", receivers)
		self.assertLess(
			receivers.index("_Test SMS Adil | 03001110002"), receivers.index("_Test SMS Zara | 03001110001"),
		)
		self.assertFalse([r for r in receivers if r.startswith(without_mobile.full_name)])
		self.assertEqual(sms_center.total_receivers, len(receivers))
		self.assertTrue(sms_center.is_promotional)

	def test_duplicate_numbers(self):
		make_contact("_Test SMS First", "0300-1110003")
		make_contact("_Test SMS Second", "03001110003")

		receivers = get_receiver_list("All Contact").receiver_list.split("\n")
		self.assertEqual(len([r for r in receivers if r.endswith("03001110003")]), 1)

	def test_open_leads(self):
		open_lead = make_lead(lead_name="_Test SMS Open Lead", mobile_no="03001110004")
		make_lead(lead_name="_Test SMS Lead Without Mobile")
		lead_with_opportunity = make_lead(
			lead_name="_Test SMS Lead With Opportunity", mobile_no="03001110005",
		)
		make_opportunity(party_name=lead_with_opportunity.name)

		sms_center = get_receiver_list("All Lead (Open)")
		receivers = sms_center.receiver_list.split("\n")

		self.assertIn(f"{open_lead.lead_name} | 03001110004", receivers)
		self.assertFalse([r for r in receivers if "Without Mobile" in r or r.endswith("03001110005")])
		self.assertTrue(sms_center.is_promotional)

	def test_sales_persons(self):
		sales_person = make_sales_person(contact_mobile="03001110006")
		without_mobile = make_sales_person()

		sms_center = get_receiver_list("All Sales Person", is_promotional=0)
		receivers = sms_center.receiver_list.split("\n")

		self.assertIn(f"{sales_person.name} | 03001110006", receivers)
		self.assertFalse([r for r in receivers if r.startswith(without_mobile.name)])
		self.assertFalse(sms_center.is_promotional)

	def test_erpnext_receivers_without_erpnext(self):
		with patch.object(frappe.db, "table_exists", return_value=False):
			for send_to in (
				"All Customer Contact",
				"All Supplier Contact",
				"All Sales Partner Contact",
				"All Employee (Active)",
			):
				self.assertRaisesRegex(
					frappe.ValidationError,
					"is not installed",
					get_receiver_list,
					send_to,
				)

			get_receiver_list("All Contact")

	def test_number_formatter(self):
		set_number_formatter("'92' + number[1:] if number.startswith('0') else number")
		# SMS Settings is cached, so the rollback alone doesn't undo the formatter
		self.addCleanup(frappe.clear_document_cache, "SMS Settings", "SMS Settings")
		make_contact("_Test SMS Formatted", "0300-1110007")

		receivers = get_receiver_list("All Contact").receiver_list.split("\n")
		self.assertIn("_Test SMS Formatted | 923001110007", receivers)


class TestSMSCenterSending(CRMTestCase):
	def test_receiver_nos(self):
		sms_center = frappe.get_doc("SMS Center")
		sms_center.receiver_list = "Ali | 03001110008\n\n03001110009\nA | B | 03001110010\n  "

		self.assertEqual(sms_center.get_receiver_nos(), ["03001110008", "03001110009", "03001110010"])

	def test_message_required(self):
		sms_center = get_sms_center(message="", receiver_list="03001110011")
		self.assertRaises(frappe.ValidationError, sms_center.send_sms)

	def test_receivers_required(self):
		sms_center = get_sms_center(message="Hello", receiver_list="")
		self.assertRaises(frappe.ValidationError, sms_center.send_sms)

	def test_send_after_in_the_past(self):
		sms_center = get_sms_center(send_after=now_datetime() - timedelta(minutes=5))
		self.assertRaises(frappe.ValidationError, sms_center.send_sms)

	def test_send_now(self):
		sms_center = get_sms_center(message="Sale starts today", is_promotional=1)

		with patch("crm.communication.doctype.sms_center.sms_center.send_sms") as send_sms:
			sms_center.send_sms()

		send_sms.assert_called_once()
		args, kwargs = send_sms.call_args
		self.assertEqual(args[0], ["03001110012"])
		self.assertEqual(kwargs["message"], "Sale starts today")
		self.assertEqual(kwargs["is_promotional"], 1)
		self.assertEqual(kwargs["reference_doctype"], "SMS Center")
		self.assertFalse(kwargs["queue"])

	def test_many_receivers_are_queued(self):
		receivers = "\n".join(f"0300111{i:04d}" for i in range(11))
		sms_center = get_sms_center(receiver_list=receivers)

		with patch("crm.communication.doctype.sms_center.sms_center.send_sms") as send_sms:
			sms_center.send_sms()

		self.assertTrue(send_sms.call_args.kwargs["queue"])

	def test_scheduled_send(self):
		send_after = now_datetime() + timedelta(hours=2)
		sms_center = get_sms_center(send_after=send_after)

		with patch("crm.communication.doctype.sms_center.sms_center.send_sms") as send_sms:
			sms_center.send_sms()

		self.assertTrue(send_sms.call_args.kwargs["queue"])
		self.assertEqual(send_sms.call_args.kwargs["send_after"], send_after)


def get_receiver_list(send_to, **kwargs):
	sms_center = frappe.get_doc("SMS Center")
	sms_center.update({"send_to": send_to, **kwargs})
	sms_center.create_receiver_list()
	return sms_center


def get_sms_center(**kwargs):
	sms_center = frappe.get_doc("SMS Center")
	sms_center.update(
		{"message": "Hello", "receiver_list": "_Test | 03001110012", "send_after": None, **kwargs},
	)
	return sms_center


def make_contact(first_name, mobile_no):
	contact = frappe.get_doc({"doctype": "Contact", "first_name": first_name})
	if mobile_no:
		contact.append("phone_nos", {"phone": mobile_no, "is_primary_mobile_no": 1})

	return contact.insert()


def set_number_formatter(number_formatter):
	frappe.db.set_single_value("SMS Settings", "number_formatter", number_formatter)
	frappe.clear_document_cache("SMS Settings", "SMS Settings")
