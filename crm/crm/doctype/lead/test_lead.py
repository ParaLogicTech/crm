# Copyright (c) 2023, ParaLogic and Contributors
# See license.txt

import frappe

from crm.crm.doctype.lead.lead import (
	_get_lead_contact_details,
	get_lead_address_details,
	get_lead_with_phone_number,
	make_lead_from_communication,
	make_opportunity,
)
from crm.tests.utils import CRMTestCase


class TestLead(CRMTestCase):
	def test_lead_name_is_required(self):
		lead = frappe.get_doc({"doctype": "Lead", "email_id": "no.name@example.com"})
		self.assertRaises(frappe.ValidationError, lead.insert)

	def test_lead_name_falls_back_to_company_name(self):
		lead = make_lead(lead_name=None, company_name="  Fallback   Traders ")
		self.assertEqual(lead.company_name, "Fallback Traders")
		self.assertEqual(lead.lead_name, "Fallback Traders")

	def test_lead_name_whitespace_is_cleaned(self):
		lead = make_lead(lead_name="  John    Smith ")
		self.assertEqual(lead.lead_name, "John Smith")

	def test_organization_lead(self):
		lead = make_lead(
			lead_name="Jane Doe",
			company_name="Doe Industries",
			organization_lead=1,
			gender="Female",
			salutation="Ms",
		)
		self.assertEqual(lead.lead_name, "Doe Industries")
		self.assertIsNone(lead.gender)
		self.assertIsNone(lead.salutation)

	def test_invalid_email_address(self):
		self.assertRaises(frappe.InvalidEmailAddressError, make_lead, email_id="not-an-email")

	def test_email_address_is_stripped(self):
		lead = make_lead(email_id="  stripped@example.com ")
		self.assertEqual(lead.email_id, "stripped@example.com")

	def test_mobile_no_2_moves_to_empty_mobile_no(self):
		lead = make_lead(mobile_no_2="03001234567")
		self.assertEqual(lead.mobile_no, "03001234567")
		self.assertFalse(lead.mobile_no_2)

	def test_new_lead_is_open(self):
		self.assertEqual(make_lead().status, "Open")

	def test_status_follows_opportunities(self):
		lead = make_lead()

		lost_opportunity = make_opportunity_for_lead(lead.name)
		self.assertEqual(get_lead_status(lead), "Opportunity")

		lost_opportunity.set_is_lost(1, lost_reasons_list=[])
		self.assertEqual(get_lead_status(lead), "Lost Opportunity")

		# An open Opportunity takes precedence over a lost one
		open_opportunity = make_opportunity_for_lead(lead.name)
		self.assertEqual(get_lead_status(lead), "Opportunity")

		# Converted takes precedence over all others
		open_opportunity.db_set("status", "Converted")
		lead.reload()
		lead.set_status(update=True)
		self.assertEqual(get_lead_status(lead), "Converted")

	def test_status_after_reopening_lost_opportunity(self):
		lead = make_lead()
		opportunity = make_opportunity_for_lead(lead.name)

		opportunity.set_is_lost(1, lost_reasons_list=[])
		opportunity.set_is_lost(0)
		self.assertEqual(get_lead_status(lead), "Opportunity")

	def test_status_after_deleting_opportunity(self):
		lead = make_lead()
		opportunity = make_opportunity_for_lead(lead.name)

		opportunity.delete()
		self.assertEqual(get_lead_status(lead), "Interested")

	def test_make_opportunity(self):
		lead = make_lead(
			lead_name="Ali Khan",
			company_name="Khan Traders",
			email_id="ali.khan@example.com",
			mobile_no="03001112233",
			territory="Rest Of The World",
		)

		opportunity = make_opportunity(lead.name)
		self.assertEqual(opportunity.opportunity_from, "Lead")
		self.assertEqual(opportunity.party_name, lead.name)
		self.assertEqual(opportunity.customer_name, "Khan Traders")
		self.assertEqual(opportunity.contact_email, "ali.khan@example.com")
		self.assertEqual(opportunity.contact_mobile, "03001112233")
		self.assertEqual(opportunity.territory, "Rest Of The World")

		opportunity.insert()
		self.assertEqual(get_lead_status(lead), "Opportunity")

	def test_contact_details(self):
		lead = make_lead(
			lead_name="Sara Ahmed",
			salutation="Ms",
			designation="Manager",
			email_id="sara@example.com",
			mobile_no="03001234567",
			mobile_no_2="03007654321",
			phone="0421234567",
		)

		details = _get_lead_contact_details(lead.name)
		self.assertEqual(details.contact_display, "Ms Sara Ahmed")
		self.assertEqual(details.contact_designation, "Manager")
		self.assertEqual(details.contact_email, "sara@example.com")
		self.assertEqual(details.contact_mobile, "03001234567")
		self.assertEqual(details.contact_mobile_2, "03007654321")
		self.assertEqual(details.contact_phone, "0421234567")

	def test_contact_details_of_organization_lead(self):
		lead = make_lead(company_name="Org Lead Co", organization_lead=1, designation="Manager")

		details = _get_lead_contact_details(lead.name)
		self.assertEqual(details.contact_display, "")
		self.assertEqual(details.contact_designation, "")

	def test_address_details(self):
		lead = make_lead(address_line1="12 Main Road", city="Lahore", country="Pakistan")

		address = get_lead_address_details(lead.name)
		self.assertEqual(address.address_line1, "12 Main Road")
		self.assertEqual(address.city, "Lahore")
		self.assertEqual(address.country, "Pakistan")

	def test_address_details_without_address_line1(self):
		lead = make_lead(city="Lahore")
		self.assertEqual(get_lead_address_details(lead.name), {})

	def test_lead_with_phone_number(self):
		self.set_default_country("Pakistan")
		mobile_lead = make_lead(mobile_no="+923331112244")
		phone_lead = make_lead(phone="04235556677")

		self.assertEqual(get_lead_with_phone_number("+923331112244"), mobile_lead.name)
		self.assertEqual(get_lead_with_phone_number("0333-1112244"), mobile_lead.name)
		self.assertEqual(get_lead_with_phone_number("+924235556677"), phone_lead.name)
		self.assertIsNone(get_lead_with_phone_number("3331112244"))
		self.assertIsNone(get_lead_with_phone_number(None))

	def test_make_lead_from_communication(self):
		communication = make_communication(
			sender="new.sender@example.com", sender_full_name="New Sender", phone_no="03009998877",
		)

		lead_name = make_lead_from_communication(communication.name)
		lead = frappe.get_doc("Lead", lead_name)
		self.assertEqual(lead.lead_name, "New Sender")
		self.assertEqual(lead.email_id, "new.sender@example.com")
		self.assertEqual(lead.mobile_no, "03009998877")

		communication.reload()
		self.assertEqual(communication.reference_doctype, "Lead")
		self.assertEqual(communication.reference_name, lead_name)

	def test_make_lead_from_communication_uses_existing_lead(self):
		by_email = make_lead(email_id="existing.sender@example.com")
		by_mobile = make_lead(mobile_no="03004445566")

		communication = make_communication(sender="existing.sender@example.com")
		self.assertEqual(make_lead_from_communication(communication.name), by_email.name)

		communication = make_communication(sender="unknown.sender@example.com", phone_no="03004445566")
		self.assertEqual(make_lead_from_communication(communication.name), by_mobile.name)

	def test_make_lead_from_communication_without_linking(self):
		communication = make_communication(sender="unlinked.sender@example.com")

		make_lead_from_communication(communication.name, ignore_communication_links=True)
		communication.reload()
		self.assertFalse(communication.reference_name)


def make_lead(**kwargs):
	lead = frappe.get_doc({"doctype": "Lead", "lead_name": "_Test Lead " + frappe.generate_hash(length=8)})
	lead.update(kwargs)
	lead.insert()
	return lead


def make_opportunity_for_lead(lead_name, **kwargs):
	opportunity = frappe.get_doc(
		{
			"doctype": "Opportunity",
			"opportunity_from": "Lead",
			"party_name": lead_name,
		},
	)
	opportunity.update(kwargs)
	opportunity.insert()
	return opportunity


def make_communication(**kwargs):
	communication = frappe.get_doc(
		{
			"doctype": "Communication",
			"communication_type": "Communication",
			"communication_medium": "Email",
			"sent_or_received": "Received",
			"subject": "_Test Enquiry",
			"content": "Please send me a quote",
		},
	)
	communication.update(kwargs)
	communication.insert(ignore_permissions=True)
	return communication


def get_lead_status(lead):
	return frappe.db.get_value("Lead", lead.name, "status")
