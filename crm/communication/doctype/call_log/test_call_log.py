# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from unittest.mock import patch

import frappe

from crm.communication.doctype.call_log.call_log import add_call_summary
from crm.crm.doctype.lead.test_lead import make_lead
from crm.tests.utils import CRMTestCase

# Links to ERPNext DocTypes, which don't exist on a site with only crm
test_ignore = ["Employee"]


class TestCallerMatching(CRMTestCase):
	"""Run as a Pakistan site. Stored numbers are expected without spaces and dashes. Mobile nos are saved
	in international format here, because Pakistan's validation still requires dashes for local mobile nos."""

	def setUp(self):
		super().setUp()
		self.set_default_country("Pakistan")

	def test_caller_matched_to_lead(self):
		lead = make_lead(mobile_no="+923001112233")

		for caller in ("+923001112233", "00923001112233", "03001112233", "0300-1112233"):
			call_log = make_call_log(**{"from": caller})
			self.assertEqual(call_log.lead, lead.name, caller)
			self.assertIsNone(call_log.contact)

	def test_caller_matched_to_lead_saved_with_dashes(self):
		# Pakistani local mobile nos are still saved as 03##-####### until they're migrated
		lead = make_lead(mobile_no="0300-1112244")
		contact = make_contact("0300-1112255")

		for caller in ("+923001112244", "00923001112244", "03001112244"):
			self.assertEqual(make_call_log(**{"from": caller}).lead, lead.name, caller)

		self.assertEqual(make_call_log(**{"from": "+923001112255"}).contact, contact.name)

	def test_caller_matched_to_lead_landline(self):
		lead = make_lead(phone="04235551234")

		call_log = make_call_log(**{"from": "+924235551234"})
		self.assertEqual(call_log.lead, lead.name)

	def test_caller_matched_to_contact(self):
		contact = make_contact("+923004445566")

		call_log = make_call_log(**{"from": "+92 300 4445566"})
		self.assertEqual(call_log.contact, contact.name)

	def test_unknown_caller(self):
		make_lead(mobile_no="+923007778800")

		# Only the end of the number matches
		call_log = make_call_log(**{"from": "+923107778800"})
		self.assertIsNone(call_log.lead)
		self.assertIsNone(call_log.contact)

	def test_lead_created_after_call(self):
		earlier_call = make_call_log(**{"from": "03005556677"})
		other_call = make_call_log(**{"from": "03001234000"})

		lead = make_lead(lead_name="Late Caller", mobile_no="+923005556677")

		earlier_call.reload()
		self.assertEqual(earlier_call.lead, lead.name)
		self.assertEqual(earlier_call.lead_name, "Late Caller")
		self.assertIsNone(frappe.db.get_value("Call Log", other_call.name, "lead"))

	def test_contact_created_after_call(self):
		earlier_call = make_call_log(**{"from": "03008889900"})

		contact = make_contact("+923008889900", first_name="Late Contact")

		earlier_call.reload()
		self.assertEqual(earlier_call.contact, contact.name)
		self.assertEqual(earlier_call.contact_name, contact.get_title())

	def test_already_linked_call_is_not_relinked(self):
		first_lead = make_lead(mobile_no="+923002223344")
		call_log = make_call_log(**{"from": "03002223344"})

		make_lead(mobile_no="+923002223344")
		self.assertEqual(frappe.db.get_value("Call Log", call_log.name, "lead"), first_lead.name)


class TestCallLog(CRMTestCase):
	def test_caller_matching_outside_pakistan_and_uae(self):
		# Without regional prefixes the number has to match as is
		self.set_default_country("United States")
		lead = make_lead(mobile_no="4155550100")

		self.assertEqual(make_call_log(**{"from": "415-555-0100"}).lead, lead.name)
		self.assertIsNone(make_call_log(**{"from": "+14155550100"}).lead)

	def test_dashed_form_only_for_pakistan(self):
		self.set_default_country("United States")
		make_lead(mobile_no="0300-1112266")

		self.assertIsNone(make_call_log(**{"from": "03001112266"}).lead)

	def test_add_call_summary(self):
		call_log = make_call_log()

		add_call_summary(call_log.name, "Customer wants a callback")
		comment = frappe.get_all(
			"Comment",
			filters={
				"reference_doctype": "Call Log",
				"reference_name": call_log.name,
				"comment_type": "Comment",
			},
			pluck="content",
		)
		self.assertEqual(len(comment), 1)
		self.assertIn("Customer wants a callback", comment[0])

	def test_disconnect_event(self):
		call_log = make_call_log(status="Ringing")

		with patch("frappe.publish_realtime") as publish_realtime:
			call_log.status = "Completed"
			call_log.save()

		events = [c.args[0] for c in publish_realtime.call_args_list]
		self.assertIn(f"call_{call_log.id}_disconnected", events)

	def test_no_disconnect_event_while_in_progress(self):
		call_log = make_call_log(status="Ringing")

		with patch("frappe.publish_realtime") as publish_realtime:
			call_log.status = "In Progress"
			call_log.save()

		events = [c.args[0] for c in publish_realtime.call_args_list]
		self.assertNotIn(f"call_{call_log.id}_disconnected", events)

	def test_call_with_number_and_medium(self):
		# What a telephony integration (e.g. Twilio) creates for every call
		call_log = make_call_log(to="03001239999", medium="Twilio")
		self.assertTrue(frappe.db.exists("Call Log", call_log.name))

	def test_no_call_popup_without_employees(self):
		with (
			patch("crm.communication.doctype.call_log.call_log.has_employee_doctypes", return_value=False),
			patch("frappe.publish_realtime") as publish_realtime,
		):
			call_log = make_call_log(to="03001239999", medium="Twilio")
			call_log.to = "03001238888"
			call_log.save()

		events = [c.args[0] for c in publish_realtime.call_args_list]
		self.assertNotIn("show_call_popup", events)


def make_call_log(**kwargs):
	call_log = frappe.get_doc(
		{
			"doctype": "Call Log",
			"id": "_Test Call " + frappe.generate_hash(length=8),
			"from": "03000000001",
			"status": "Ringing",
		},
	)
	call_log.update(kwargs)
	call_log.insert()
	return call_log


def make_contact(phone, first_name="_Test Caller"):
	return frappe.get_doc(
		{
			"doctype": "Contact",
			"first_name": first_name,
			"phone_nos": [{"phone": phone, "is_primary_mobile_no": 1}],
		},
	).insert()
