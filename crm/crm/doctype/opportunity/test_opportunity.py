# Copyright (c) 2023, ParaLogic and Contributors
# See license.txt

import json
from unittest.mock import patch

import frappe
from frappe.tests.utils import change_settings
from frappe.utils import add_days, getdate, now_datetime, nowdate

from crm.crm.doctype.lead.test_lead import make_communication, make_lead
from crm.crm.doctype.opportunity.opportunity import (
	Opportunity,
	auto_mark_opportunity_as_lost,
	create_opportunity_from_communication,
	get_events,
	make_opportunity_from_lead_form,
	schedule_follow_up,
	set_multiple_status,
	submit_communication,
	submit_communication_with_action,
	trigger_recall_lost_opportunities,
)
from crm.tests.utils import CRMTestCase


class TestOpportunity(CRMTestCase):
	def test_party_details_from_lead(self):
		lead = make_lead(
			lead_name="Bilal Ahmed",
			company_name="Ahmed Motors",
			email_id="bilal@example.com",
			mobile_no="03001231234",
			territory="Rest Of The World",
			source="Cold Calling",
		)

		opportunity = make_opportunity(party_name=lead.name)
		self.assertEqual(opportunity.customer_name, "Ahmed Motors")
		self.assertEqual(opportunity.contact_display, "Bilal Ahmed")
		self.assertEqual(opportunity.contact_email, "bilal@example.com")
		self.assertEqual(opportunity.contact_mobile, "03001231234")
		self.assertEqual(opportunity.territory, "Rest Of The World")
		self.assertEqual(opportunity.source, "Cold Calling")
		self.assertEqual(opportunity.title, "Bilal Ahmed (Ahmed Motors)")

	def test_title_of_individual_lead(self):
		lead = make_lead(lead_name="Usman Ali")
		self.assertEqual(make_opportunity(party_name=lead.name).title, "Usman Ali")

	def test_party_contact_details_are_refreshed_on_save(self):
		lead = make_lead(email_id="old.email@example.com")
		opportunity = make_opportunity(party_name=lead.name)

		lead.reload()
		lead.email_id = "new.email@example.com"
		lead.save()

		opportunity.reload()
		opportunity.save()
		self.assertEqual(opportunity.contact_email, "new.email@example.com")

	def test_opportunity_from_must_be_lead(self):
		self.assertRaises(frappe.ValidationError, Opportunity.validate_opportunity_from, "Customer")
		Opportunity.validate_opportunity_from("Lead")

	def test_contact_no_mandatory(self):
		lead = make_lead()

		with change_settings("CRM Settings", opportunity_contact_no_mandatory=1):
			self.assertRaises(frappe.ValidationError, make_opportunity, party_name=lead.name)

			lead.mobile_no = "03001112222"
			lead.save()
			make_opportunity(party_name=lead.name)

	def test_new_opportunity_is_open(self):
		self.assertEqual(make_opportunity().status, "Open")

	def test_replied_status(self):
		opportunity = make_opportunity()
		submit_communication(opportunity.name, nowdate(), "Called the customer")

		opportunity.reload()
		opportunity.save()
		self.assertEqual(opportunity.status, "Replied")

	def test_automated_message_is_not_a_reply(self):
		opportunity = make_opportunity()
		make_communication(
			communication_type="Automated Message",
			reference_doctype="Opportunity",
			reference_name=opportunity.name,
		)

		opportunity.save()
		self.assertEqual(opportunity.status, "Open")

	def test_closed_status_is_kept_on_save(self):
		opportunity = make_opportunity()
		opportunity.set_status(update=True, status="Closed")

		opportunity.reload()
		opportunity.save()
		self.assertEqual(opportunity.status, "Closed")

	def test_mark_as_lost(self):
		lost_reason = make_lost_reason()
		opportunity = make_opportunity()

		opportunity.set_is_lost(
			1,
			lost_reasons_list=[{"lost_reason": lost_reason}],
			detailed_reason="Too expensive",
		)
		opportunity.reload()
		self.assertEqual(opportunity.status, "Lost")
		self.assertEqual(opportunity.order_lost_reason, "Too expensive")
		self.assertEqual(opportunity.lost_date, getdate())
		self.assertEqual([d.lost_reason for d in opportunity.lost_reasons], [lost_reason])

		# A Lost Opportunity stays Lost on save
		opportunity.save()
		self.assertEqual(opportunity.status, "Lost")

	def test_mark_as_lost_with_lost_date(self):
		opportunity = make_opportunity()
		opportunity.set_is_lost(1, lost_reasons_list=[], lost_date=add_days(nowdate(), -3))
		self.assertEqual(
			frappe.db.get_value("Opportunity", opportunity.name, "lost_date"),
			getdate(add_days(nowdate(), -3)),
		)

	def test_reopen_lost_opportunity(self):
		opportunity = make_opportunity()
		opportunity.set_is_lost(
			1, lost_reasons_list=[{"lost_reason": make_lost_reason()}], detailed_reason="Lost",
		)

		opportunity.set_is_lost(0)
		opportunity.reload()
		self.assertEqual(opportunity.status, "Open")
		self.assertFalse(opportunity.order_lost_reason)
		self.assertFalse(opportunity.lost_date)
		self.assertFalse(opportunity.lost_reasons)

	def test_set_multiple_status(self):
		first = make_opportunity()
		second = make_opportunity()

		set_multiple_status(json.dumps([first.name, second.name]), "Closed")
		self.assertEqual(frappe.db.get_value("Opportunity", first.name, "status"), "Closed")
		self.assertEqual(frappe.db.get_value("Opportunity", second.name, "status"), "Closed")

		set_multiple_status(json.dumps([first.name]), "Open")
		self.assertEqual(frappe.db.get_value("Opportunity", first.name, "status"), "Open")

	def test_follow_up_without_dates(self):
		opportunity = get_opportunity()
		opportunity.append("contact_schedule", {"to_discuss": "Pricing"})
		self.assertRaises(frappe.ValidationError, opportunity.insert)

	def test_follow_up_in_the_past(self):
		opportunity = get_opportunity()
		opportunity.append("contact_schedule", {"schedule_date": add_days(nowdate(), -1)})
		self.assertRaises(frappe.ValidationError, opportunity.insert)

	def test_past_follow_up_with_contact_date(self):
		opportunity = get_opportunity()
		opportunity.append(
			"contact_schedule",
			{
				"schedule_date": add_days(nowdate(), -2),
				"contact_date": add_days(nowdate(), -1),
			},
		)
		opportunity.insert()

		self.assertIsNone(opportunity.next_follow_up)
		self.assertEqual(opportunity.status, "Open")

	def test_next_follow_up(self):
		opportunity = get_opportunity()
		opportunity.append("contact_schedule", {"schedule_date": add_days(nowdate(), 10)})
		opportunity.append("contact_schedule", {"schedule_date": add_days(nowdate(), 5)})
		opportunity.insert()

		self.assertEqual(opportunity.next_follow_up, getdate(add_days(nowdate(), 5)))
		self.assertEqual(opportunity.status, "To Follow Up")

		# Once the first follow up is done, the next pending one is due
		opportunity.set_follow_up_contact_date(nowdate())
		opportunity.save()
		self.assertEqual(opportunity.next_follow_up, getdate(add_days(nowdate(), 5)))

		opportunity.set_follow_up_contact_date(nowdate())
		opportunity.save()
		self.assertIsNone(opportunity.next_follow_up)
		self.assertEqual(opportunity.status, "Open")

	def test_follow_up_due_today(self):
		opportunity = get_opportunity()
		opportunity.append("contact_schedule", {"schedule_date": nowdate()})
		opportunity.insert()

		self.assertEqual(opportunity.next_follow_up, getdate())
		self.assertEqual(opportunity.status, "To Follow Up")

	def test_overdue_follow_up(self):
		opportunity = get_opportunity()
		opportunity.append("contact_schedule", {"schedule_date": add_days(nowdate(), 1)})
		opportunity.insert()

		# The follow up date passes without contacting the customer
		frappe.db.set_value(
			"Lead Follow Up", opportunity.contact_schedule[0].name, "schedule_date", add_days(nowdate(), -1),
		)
		opportunity.reload()
		opportunity.save()

		self.assertEqual(opportunity.next_follow_up, getdate(add_days(nowdate(), -1)))
		self.assertEqual(opportunity.status, "Open")

	def test_add_next_follow_up_on_same_date(self):
		opportunity = make_opportunity()
		follow_up_date = add_days(nowdate(), 3)

		opportunity.add_next_follow_up(follow_up_date)
		self.assertRaises(frappe.ValidationError, opportunity.add_next_follow_up, follow_up_date)

		# A follow up without anything to discuss can be given an agenda
		opportunity.add_next_follow_up(follow_up_date, to_discuss="Pricing")
		self.assertEqual(len(opportunity.contact_schedule), 1)
		self.assertEqual(opportunity.contact_schedule[0].to_discuss, "Pricing")

		self.assertRaises(frappe.ValidationError, opportunity.add_next_follow_up, follow_up_date, "Delivery")

	def test_schedule_follow_up(self):
		opportunity = make_opportunity()

		self.assertRaises(frappe.ValidationError, schedule_follow_up, opportunity.name, None)
		self.assertRaises(
			frappe.ValidationError, schedule_follow_up, opportunity.name, add_days(nowdate(), -1),
		)

		schedule_follow_up(opportunity.name, add_days(nowdate(), 2), "Send brochure")
		opportunity.reload()
		self.assertEqual(opportunity.status, "To Follow Up")
		self.assertEqual(opportunity.next_follow_up, getdate(add_days(nowdate(), 2)))
		self.assertEqual(opportunity.contact_schedule[0].to_discuss, "Send brochure")

	def test_submit_communication(self):
		opportunity = make_opportunity()
		self.assertRaises(frappe.ValidationError, submit_communication, opportunity.name, nowdate(), "")

		submit_communication(opportunity.name, nowdate(), "  Discussed   pricing ")
		communication = get_last_communication(opportunity.name)
		self.assertEqual(communication.content, "Discussed pricing")
		self.assertEqual(communication.communication_type, "Feedback")
		self.assertIn(
			("Lead", opportunity.party_name),
			[(d.link_doctype, d.link_name) for d in communication.timeline_links],
		)

	def test_submit_communication_completes_follow_up(self):
		opportunity = make_opportunity()
		schedule_follow_up(opportunity.name, add_days(nowdate(), 1))

		submit_communication(opportunity.name, nowdate(), "Called early")
		opportunity.reload()
		self.assertEqual(opportunity.contact_schedule[0].contact_date, getdate())
		self.assertIsNone(opportunity.next_follow_up)

	def test_communication_action_mark_as_lost(self):
		lost_reason = make_lost_reason()
		opportunity = make_opportunity()

		submit_communication_with_action(
			"Customer bought elsewhere",
			"Mark As Lost",
			opportunity.name,
			lost_reason=json.dumps([{"lost_reason": lost_reason}]),
		)
		opportunity.reload()
		self.assertEqual(opportunity.status, "Lost")
		self.assertEqual(opportunity.order_lost_reason, "Customer bought elsewhere")
		self.assertEqual([d.lost_reason for d in opportunity.lost_reasons], [lost_reason])
		self.assertEqual(get_last_communication(opportunity.name).content, "Customer bought elsewhere")

	def test_communication_action_mark_as_closed(self):
		opportunity = make_opportunity()

		submit_communication_with_action("Not needed any more", "Mark As Closed", opportunity.name)
		self.assertEqual(frappe.db.get_value("Opportunity", opportunity.name, "status"), "Closed")

	def test_communication_action_schedule_follow_up(self):
		opportunity = make_opportunity()

		self.assertRaises(
			frappe.ValidationError,
			submit_communication_with_action,
			"Call back",
			"Schedule Follow Up",
			opportunity.name,
			follow_up_date=add_days(nowdate(), -1),
		)

		submit_communication_with_action(
			"Call back",
			"Schedule Follow Up",
			opportunity.name,
			follow_up_date=add_days(nowdate(), 1),
		)
		opportunity.reload()
		self.assertEqual(opportunity.status, "To Follow Up")
		self.assertEqual(opportunity.contact_schedule[0].to_discuss, "Call back")

	def test_communication_action_schedule_follow_up_reopens_lost(self):
		opportunity = make_opportunity()
		opportunity.set_is_lost(1, lost_reasons_list=[])

		submit_communication_with_action(
			"Customer is interested again",
			"Schedule Follow Up",
			opportunity.name,
			follow_up_date=add_days(nowdate(), 1),
		)
		opportunity.reload()
		self.assertEqual(opportunity.status, "To Follow Up")
		self.assertFalse(opportunity.lost_date)

	def test_communication_action_on_lost_opportunity(self):
		opportunity = make_opportunity()
		opportunity.set_is_lost(1, lost_reasons_list=[])

		self.assertRaises(
			frappe.ValidationError,
			submit_communication_with_action,
			"Close it",
			"Mark As Closed",
			opportunity.name,
		)

		submit_communication_with_action("Customer called again", "Submit Remarks Only", opportunity.name)
		self.assertEqual(get_last_communication(opportunity.name).content, "Customer called again")
		self.assertEqual(frappe.db.get_value("Opportunity", opportunity.name, "status"), "Lost")

	def test_get_events(self):
		opportunity = make_opportunity()
		schedule_follow_up(opportunity.name, add_days(nowdate(), 3))

		events = get_events(nowdate(), add_days(nowdate(), 7))
		self.assertIn(opportunity.name, [d.name for d in events])

		events = get_events(add_days(nowdate(), 4), add_days(nowdate(), 7))
		self.assertNotIn(opportunity.name, [d.name for d in events])

	def test_create_opportunity_from_communication(self):
		communication = make_communication(sender="enquiry@example.com", sender_full_name="Enquiry Sender")

		opportunity = frappe.get_doc("Opportunity", create_opportunity_from_communication(communication.name))
		self.assertEqual(opportunity.opportunity_from, "Lead")
		self.assertEqual(
			frappe.db.get_value("Lead", opportunity.party_name, "email_id"), "enquiry@example.com",
		)

		communication.reload()
		self.assertEqual(communication.reference_doctype, "Opportunity")
		self.assertEqual(communication.reference_name, opportunity.name)

	def test_create_opportunity_from_communication_linked_to_lead(self):
		lead = make_lead()
		communication = make_communication(
			sender="other@example.com",
			reference_doctype="Lead",
			reference_name=lead.name,
		)

		opportunity_name = create_opportunity_from_communication(communication.name)
		self.assertEqual(frappe.db.get_value("Opportunity", opportunity_name, "party_name"), lead.name)

	def test_auto_mark_opportunity_as_lost(self):
		lost_reason = make_lost_reason()
		stale = make_opportunity()
		recent = make_opportunity()
		closed = make_opportunity()
		closed.set_status(update=True, status="Closed")

		for opportunity in (stale, closed):
			set_modified(opportunity, add_days(now_datetime(), -40))

		settings = {
			"auto_mark_opportunity_as_lost": 1,
			"mark_opportunity_lost_after_days": 30,
			"opportunity_auto_lost_reason": lost_reason,
		}
		with change_settings("CRM Settings", settings), patch.object(frappe.db, "commit"):
			auto_mark_opportunity_as_lost()

		self.assertEqual(frappe.db.get_value("Opportunity", stale.name, "status"), "Lost")
		self.assertEqual(
			frappe.get_all("Lost Reason Detail", filters={"parent": stale.name}, pluck="lost_reason"),
			[lost_reason],
		)
		self.assertEqual(frappe.db.get_value("Opportunity", recent.name, "status"), "Open")
		self.assertEqual(frappe.db.get_value("Opportunity", closed.name, "status"), "Closed")

	def test_auto_mark_opportunity_as_lost_disabled(self):
		opportunity = make_opportunity()
		set_modified(opportunity, add_days(now_datetime(), -40))

		settings = {"auto_mark_opportunity_as_lost": 0, "mark_opportunity_lost_after_days": 30}
		with change_settings("CRM Settings", settings), patch.object(frappe.db, "commit"):
			auto_mark_opportunity_as_lost()

		self.assertEqual(frappe.db.get_value("Opportunity", opportunity.name, "status"), "Open")

	def test_trigger_recall_lost_opportunities(self):
		due = make_opportunity()
		due.set_is_lost(1, lost_reasons_list=[], lost_date=add_days(nowdate(), -7))
		not_due = make_opportunity()
		not_due.set_is_lost(1, lost_reasons_list=[], lost_date=add_days(nowdate(), -6))
		already_recalled = make_opportunity()
		already_recalled.set_is_lost(1, lost_reasons_list=[], lost_date=add_days(nowdate(), -8))

		recalled = []

		def record_recall(doc):
			recalled.append(doc.name)

		with (
			change_settings("CRM Settings", recall_lost_opportunity_days_after=7),
			patch.object(frappe.db, "commit"),
			patch("frappe.email.doctype.notification.notification.has_notification", return_value=True),
			patch.object(Opportunity, "trigger_recall_lost_opportunity", record_recall),
		):
			trigger_recall_lost_opportunities()

		self.assertIn(due.name, recalled)
		self.assertNotIn(not_due.name, recalled)
		self.assertNotIn(already_recalled.name, recalled)


class TestOpportunityLeadForm(CRMTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_new_lead(self):
		sender = make_email()

		submit_lead_form(
			sender=sender,
			message="I want a quote",
			subject="Price Enquiry",
			full_name="Web Visitor",
			organization="Visitor Co",
			designation="CEO",
			mobile_no="03005556666",
			phone_no="0423334444",
			country="Pakistan",
		)

		lead = frappe.get_doc("Lead", {"email_id": sender})
		self.assertEqual(lead.lead_name, "Web Visitor")
		self.assertEqual(lead.company_name, "Visitor Co")
		self.assertEqual(lead.designation, "CEO")
		self.assertEqual(lead.mobile_no, "03005556666")
		self.assertEqual(lead.phone, "0423334444")
		self.assertEqual(lead.country, "Pakistan")
		self.assertEqual(lead.status, "Opportunity")

		opportunity = frappe.get_doc("Opportunity", {"party_name": lead.name})
		self.assertEqual(opportunity.opportunity_from, "Lead")
		self.assertEqual(opportunity.details, "I want a quote")
		self.assertEqual(opportunity.contact_email, sender)

		communication = get_last_communication(opportunity.name)
		self.assertEqual(communication.sender, sender)
		self.assertEqual(communication.subject, "Price Enquiry")

	def test_lead_name_from_email(self):
		sender = make_email("jane.doe")
		submit_lead_form(sender=sender)
		self.assertEqual(
			frappe.db.get_value("Lead", {"email_id": sender}, "lead_name"), sender.split("@")[0].title(),
		)

	def test_invalid_email(self):
		self.assertRaises(frappe.ValidationError, submit_lead_form, sender="")
		self.assertRaises(frappe.InvalidEmailAddressError, submit_lead_form, sender="not-an-email")

	def test_existing_lead_is_updated(self):
		lead = make_lead(lead_name="Old Name", email_id=make_email(), mobile_no="03001110000")

		submit_lead_form(
			sender=lead.email_id,
			full_name="New Name",
			organization="New Co",
			designation="Manager",
			phone_no="0421112222",
			mobile_no="03002220000",
		)

		lead.reload()
		self.assertEqual(lead.lead_name, "New Name")
		self.assertEqual(lead.company_name, "New Co")
		self.assertEqual(lead.designation, "Manager")
		self.assertEqual(lead.phone, "0421112222")
		self.assertEqual(lead.mobile_no, "03002220000")
		self.assertEqual(lead.mobile_no_2, "03001110000")
		self.assertEqual(frappe.db.count("Lead", {"email_id": lead.email_id}), 1)
		self.assertEqual(frappe.db.count("Opportunity", {"party_name": lead.name}), 1)

	def test_existing_lead_without_mobile_no(self):
		lead = make_lead(email_id=make_email())

		submit_lead_form(sender=lead.email_id, mobile_no="03009990000")

		lead.reload()
		self.assertEqual(lead.mobile_no, "03009990000")
		self.assertFalse(lead.mobile_no_2)

	def test_existing_lead_without_changes(self):
		lead = make_lead(lead_name="Same Name", email_id=make_email(), mobile_no="03001110000")

		submit_lead_form(sender=lead.email_id, mobile_no="03001110000")

		lead.reload()
		self.assertEqual(lead.lead_name, "Same Name")
		self.assertFalse(lead.mobile_no_2)
		self.assertEqual(frappe.db.count("Opportunity", {"party_name": lead.name}), 1)

	def test_default_lead_source_and_opportunity_type(self):
		frappe.get_doc({"doctype": "Opportunity Type", "name": "_Test Web Enquiry"}).insert(
			ignore_if_duplicate=True,
		)

		contact_us_settings = frappe.get_single("Contact Us Settings")
		contact_us_settings.default_lead_source = "Advertisement"
		contact_us_settings.append(
			"query_options", {"option": "Service Booking", "opportunity_type": "_Test Web Enquiry"},
		)
		contact_us_settings.save()

		sender = make_email()
		submit_lead_form(sender=sender, subject="Service Booking")

		lead = frappe.get_doc("Lead", {"email_id": sender})
		self.assertEqual(lead.source, "Advertisement")
		self.assertEqual(
			frappe.db.get_value("Opportunity", {"party_name": lead.name}, "opportunity_type"),
			"_Test Web Enquiry",
		)

	def test_opportunity_args(self):
		sender = make_email()
		submit_lead_form(
			sender=sender,
			opportunity_args=json.dumps(
				{
					"lead_classification": "Hot",
					"not_a_field": "ignored",
				},
			),
		)

		lead = frappe.db.get_value("Lead", {"email_id": sender})
		self.assertEqual(
			frappe.db.get_value("Opportunity", {"party_name": lead}, "lead_classification"), "Hot",
		)


def get_opportunity(**kwargs):
	opportunity = frappe.get_doc({"doctype": "Opportunity", "opportunity_from": "Lead"})
	opportunity.update(kwargs)

	if not opportunity.party_name:
		opportunity.party_name = make_lead().name

	return opportunity


def make_opportunity(**kwargs):
	opportunity = get_opportunity(**kwargs)
	opportunity.insert()
	return opportunity


def make_lost_reason():
	lost_reason = "_Test Lost Reason " + frappe.generate_hash(length=8)
	frappe.get_doc({"doctype": "Opportunity Lost Reason", "lost_reason": lost_reason}).insert()
	return lost_reason


def set_modified(doc, modified):
	frappe.db.set_value(doc.doctype, doc.name, "modified", modified, update_modified=False)


def get_last_communication(opportunity):
	name = frappe.db.get_value(
		"Communication",
		{"reference_doctype": "Opportunity", "reference_name": opportunity},
		order_by="creation desc",
	)
	return frappe.get_doc("Communication", name)


def make_email(prefix="web.visitor"):
	return f"{prefix}.{frappe.generate_hash(length=8)}@example.com"


def submit_lead_form(**kwargs):
	frappe.set_user("Guest")
	try:
		return make_opportunity_from_lead_form(**kwargs)
	finally:
		frappe.set_user("Administrator")
