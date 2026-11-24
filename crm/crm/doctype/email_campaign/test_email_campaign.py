# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.utils import add_days, getdate, nowdate

from crm.crm.doctype.email_campaign.email_campaign import (
	process_email_campaigns,
	send_email_to_leads_or_contacts,
	set_email_campaign_status,
)
from crm.crm.doctype.lead.test_lead import make_lead
from crm.tests.utils import CRMTestCase


class TestEmailCampaign(CRMTestCase):
	def test_end_date_from_campaign_schedule(self):
		campaign = make_campaign(schedule=[(0, make_email_template()), (5, make_email_template())])

		email_campaign = make_email_campaign(campaign=campaign, start_date=add_days(nowdate(), 1))
		self.assertEqual(getdate(email_campaign.end_date), getdate(add_days(nowdate(), 6)))

	def test_campaign_without_schedule(self):
		campaign = make_campaign(schedule=[])
		self.assertRaises(frappe.ValidationError, make_email_campaign, campaign=campaign)

	def test_start_date_in_the_past(self):
		self.assertRaises(frappe.ValidationError, make_email_campaign, start_date=add_days(nowdate(), -1))

	def test_lead_without_email(self):
		lead = make_lead(email_id=None)
		self.assertRaises(frappe.ValidationError, make_email_campaign, recipient=lead.name)

	def test_duplicate_campaign_for_recipient(self):
		campaign = make_campaign()
		lead = make_lead(email_id="duplicate.campaign@example.com")

		first = make_email_campaign(campaign=campaign, recipient=lead.name)
		self.assertRaises(frappe.ValidationError, make_email_campaign, campaign=campaign, recipient=lead.name)

		# Allowed again once the first one is no longer running
		first.db_set("status", "Unsubscribed")
		make_email_campaign(campaign=campaign, recipient=lead.name, start_date=add_days(nowdate(), 1))

		# A campaign that hasn't started yet also counts
		self.assertRaises(frappe.ValidationError, make_email_campaign, campaign=campaign, recipient=lead.name)

	def test_status(self):
		campaign = make_campaign(schedule=[(0, make_email_template()), (3, make_email_template())])

		scheduled = make_email_campaign(campaign=campaign, start_date=add_days(nowdate(), 1))
		self.assertEqual(scheduled.status, "Scheduled")

		in_progress = make_email_campaign(campaign=campaign, start_date=nowdate())
		self.assertEqual(in_progress.status, "In Progress")

		# The campaign's last email was sent yesterday
		in_progress.start_date = add_days(nowdate(), -4)
		in_progress.end_date = add_days(nowdate(), -1)
		in_progress.update_status()
		self.assertEqual(in_progress.status, "Completed")

	def test_set_email_campaign_status(self):
		campaign = make_campaign(schedule=[(0, make_email_template()), (3, make_email_template())])
		starting = make_email_campaign(campaign=campaign, start_date=add_days(nowdate(), 1))
		finished = make_email_campaign(campaign=campaign)
		unsubscribed = make_email_campaign(campaign=campaign, start_date=add_days(nowdate(), 1))

		# Simulate the days passing
		starting.db_set("start_date", nowdate())
		finished.db_set({"start_date": add_days(nowdate(), -4), "end_date": add_days(nowdate(), -1)})
		unsubscribed.db_set({"start_date": nowdate(), "status": "Unsubscribed"})

		set_email_campaign_status()

		self.assertEqual(frappe.db.get_value("Email Campaign", starting.name, "status"), "In Progress")
		self.assertEqual(frappe.db.get_value("Email Campaign", finished.name, "status"), "Completed")
		self.assertEqual(frappe.db.get_value("Email Campaign", unsubscribed.name, "status"), "Unsubscribed")

	def test_unsubscribe(self):
		email_campaign = make_email_campaign()

		frappe.get_doc(
			{
				"doctype": "Email Unsubscribe",
				"email": "unsubscribe@example.com",
				"reference_doctype": "Email Campaign",
				"reference_name": email_campaign.name,
			}
		).insert(ignore_permissions=True)

		self.assertEqual(frappe.db.get_value("Email Campaign", email_campaign.name, "status"), "Unsubscribed")


class TestEmailCampaignSending(CRMTestCase):
	def setUp(self):
		super().setUp()
		make_outgoing_email_account()

	def test_send_emails_due_today(self):
		day_0 = make_email_template(subject="Welcome {{ doc.lead_name }}")
		day_2 = make_email_template(subject="Following up, {{ doc.lead_name }}")
		campaign = make_campaign(schedule=[(0, day_0), (2, day_2)])

		lead = make_lead(lead_name="Campaign Lead", email_id="campaign.lead@example.com")
		started_today = make_email_campaign(campaign=campaign, recipient=lead.name)
		started_2_days_ago = make_email_campaign(
			campaign=campaign, recipient=make_lead(email_id="early@example.com").name
		)
		started_2_days_ago.db_set("start_date", add_days(nowdate(), -2))

		send_email_to_leads_or_contacts()

		self.assertEqual(
			get_sent_emails(started_today.name), [("Welcome Campaign Lead", "campaign.lead@example.com")]
		)
		self.assertEqual(
			[subject.split(",")[0] for subject, recipient in get_sent_emails(started_2_days_ago.name)],
			["Following up"],
		)

	def test_first_email_on_start_date(self):
		campaign = make_campaign(schedule=[(0, make_email_template(subject="Day one"))])
		email_campaign = make_email_campaign(campaign=campaign, start_date=add_days(nowdate(), 1))
		self.assertEqual(email_campaign.status, "Scheduled")

		# The start date arrives
		email_campaign.db_set("start_date", nowdate())
		process_email_campaigns()

		self.assertEqual(frappe.db.get_value("Email Campaign", email_campaign.name, "status"), "In Progress")
		self.assertEqual(
			[subject for subject, recipient in get_sent_emails(email_campaign.name)], ["Day one"]
		)

	def test_no_emails_for_inactive_campaigns(self):
		campaign = make_campaign()
		scheduled = make_email_campaign(campaign=campaign, start_date=add_days(nowdate(), 1))
		unsubscribed = make_email_campaign(campaign=campaign)
		unsubscribed.db_set("status", "Unsubscribed")

		send_email_to_leads_or_contacts()

		self.assertEqual(get_sent_emails(scheduled.name), [])
		self.assertEqual(get_sent_emails(unsubscribed.name), [])

	def test_send_email_to_contact(self):
		contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": "Campaign Contact",
				"email_ids": [{"email_id": "campaign.contact@example.com", "is_primary": 1}],
			}
		).insert()
		campaign = make_campaign(schedule=[(0, make_email_template(subject="Hello {{ doc.first_name }}"))])

		email_campaign = make_email_campaign(
			campaign=campaign, email_campaign_for="Contact", recipient=contact.name
		)
		send_email_to_leads_or_contacts()

		self.assertEqual(
			get_sent_emails(email_campaign.name),
			[("Hello Campaign Contact", "campaign.contact@example.com")],
		)


def make_email_template(subject="_Test Campaign Email", response="Hello {{ doc.name }}"):
	return (
		frappe.get_doc(
			{
				"doctype": "Email Template",
				"name": "_Test Email Template " + frappe.generate_hash(length=8),
				"subject": subject,
				"response": response,
			}
		)
		.insert()
		.name
	)


def make_campaign(schedule=None):
	if schedule is None:
		schedule = [(0, make_email_template())]

	return (
		frappe.get_doc(
			{
				"doctype": "Campaign",
				"campaign_name": "_Test Email Campaign " + frappe.generate_hash(length=8),
				"campaign_schedules": [
					{"send_after_days": days, "email_template": template} for days, template in schedule
				],
			}
		)
		.insert()
		.name
	)


def make_email_campaign(campaign=None, recipient=None, start_date=None, **kwargs):
	email_campaign = frappe.get_doc(
		{
			"doctype": "Email Campaign",
			"campaign_name": campaign or make_campaign(),
			"email_campaign_for": "Lead",
			"start_date": start_date or nowdate(),
			"sender": "Administrator",
		}
	)
	email_campaign.update(kwargs)
	email_campaign.recipient = (
		recipient or make_lead(email_id=f"{frappe.generate_hash(length=8)}@example.com").name
	)
	email_campaign.insert()
	return email_campaign


def make_outgoing_email_account():
	frappe.get_doc(
		{
			"doctype": "Email Account",
			"email_account_name": "_Test Campaign Email Account",
			"email_id": "campaigns@example.com",
			"enable_outgoing": 1,
			"default_outgoing": 1,
			"smtp_server": "smtp.example.com",
			"no_smtp_authentication": 1,
		}
	).insert(ignore_if_duplicate=True)


def get_sent_emails(email_campaign):
	return [
		(d.subject, d.recipients)
		for d in frappe.get_all(
			"Communication",
			filters={"reference_doctype": "Email Campaign", "reference_name": email_campaign},
			fields=["subject", "recipients"],
		)
	]
