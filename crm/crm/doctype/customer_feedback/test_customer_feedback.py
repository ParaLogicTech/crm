# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.utils import getdate

from crm.crm.doctype.appointment.test_appointment import make_appointment
from crm.crm.doctype.customer_feedback.customer_feedback import CustomerFeedback, submit_customer_feedback
from crm.crm.doctype.lead.test_lead import make_lead
from crm.crm.doctype.opportunity.test_opportunity import make_opportunity
from crm.crm.doctype.sales_person.test_sales_person import make_sales_person
from crm.tests.utils import CRMTestCase

# Links to ERPNext DocTypes, which don't exist on a site with only crm
test_ignore = ["Employee"]


class TestCustomerFeedback(CRMTestCase):
	def test_party_details_from_lead(self):
		lead = make_lead(
			lead_name="Ayesha Khan",
			company_name="Khan Textiles",
			email_id="ayesha@example.com",
			mobile_no="03002223344",
		)

		feedback = make_customer_feedback(party_name=lead.name)
		self.assertEqual(feedback.customer_name, "Khan Textiles")
		self.assertEqual(feedback.title, "Khan Textiles")
		self.assertEqual(feedback.contact_display, "Ayesha Khan")
		self.assertEqual(feedback.contact_email, "ayesha@example.com")
		self.assertEqual(feedback.contact_mobile, "03002223344")

	def test_feedback_from_must_be_lead(self):
		self.assertRaises(frappe.ValidationError, CustomerFeedback.validate_feedback_from, "Customer")
		CustomerFeedback.validate_feedback_from("Lead")

	def test_sales_person_from_user(self):
		sales_person = make_sales_person(user_id=frappe.session.user, contact_email="sp@example.com")

		feedback = make_customer_feedback()
		self.assertEqual(feedback.sales_person, sales_person.name)
		self.assertEqual(feedback.sales_person_email, "sp@example.com")

	def test_status(self):
		feedback = make_customer_feedback()
		self.assertEqual(feedback.status, "Pending")

		feedback.contact_remarks = "Called, no answer"
		feedback.save()
		self.assertEqual(feedback.status, "Pending")

		feedback.customer_feedback = "Very happy with the service"
		feedback.save()
		self.assertEqual(feedback.status, "Completed")

	def test_sub_type_mandatory(self):
		feedback_type = make_feedback_type(feedback_sub_type_mandatory=1)
		sub_type = make_feedback_sub_type(feedback_type)

		self.assertRaises(frappe.ValidationError, make_customer_feedback, feedback_type=feedback_type)
		make_customer_feedback(feedback_type=feedback_type, feedback_sub_type=sub_type)

	def test_status_mandatory(self):
		feedback_type = make_feedback_type(feedback_status_mandatory=1)
		status = make_feedback_status(feedback_type)

		self.assertRaises(frappe.ValidationError, make_customer_feedback, feedback_type=feedback_type)
		make_customer_feedback(feedback_type=feedback_type, feedback_status=status)

	def test_sub_type_of_another_feedback_type(self):
		complaint = make_feedback_type()
		praise = make_feedback_type()
		praise_sub_type = make_feedback_sub_type(praise)

		self.assertRaises(
			frappe.ValidationError,
			make_customer_feedback,
			feedback_type=complaint,
			feedback_sub_type=praise_sub_type,
		)

	def test_status_of_another_feedback_type(self):
		complaint = make_feedback_type()
		praise = make_feedback_type()
		praise_status = make_feedback_status(praise)
		any_type_status = make_feedback_status(None)

		self.assertRaises(
			frappe.ValidationError,
			make_customer_feedback,
			feedback_type=complaint,
			feedback_status=praise_status,
		)
		make_customer_feedback(feedback_type=complaint, feedback_status=any_type_status)

	def test_sub_type_is_cleared_without_feedback_type(self):
		sub_type = make_feedback_sub_type(make_feedback_type())

		feedback = make_customer_feedback(feedback_sub_type=sub_type)
		self.assertIsNone(feedback.feedback_sub_type)

	def test_communications(self):
		opportunity = make_opportunity()
		feedback = make_customer_feedback(
			party_name=opportunity.party_name,
			reference_doctype="Opportunity",
			reference_name=opportunity.name,
			contact_remarks="Left a voicemail",
		)

		remarks = get_communications(feedback.name)
		self.assertEqual(len(remarks), 1)
		self.assertEqual(remarks[0].subject, f"Customer Feedback Remarks ({opportunity.name})")
		self.assertEqual(remarks[0].content, "Left a voicemail")
		self.assertEqual(remarks[0].communication_type, "Feedback")
		self.assertFalse(remarks[0].timeline_links)

		feedback.customer_feedback = "Delivery was late"
		feedback.save()

		communications = get_communications(feedback.name)
		self.assertEqual(len(communications), 2)
		self.assertEqual(communications[-1].subject, f"Customer Feedback ({opportunity.name})")
		self.assertEqual(
			{(d.link_doctype, d.link_name) for d in communications[-1].timeline_links},
			{("Opportunity", opportunity.name), ("Lead", opportunity.party_name)},
		)

	def test_communication_only_when_text_changes(self):
		feedback = make_customer_feedback(customer_feedback="Good")
		self.assertEqual(len(get_communications(feedback.name)), 1)

		feedback.feedback_source = make_feedback_source()
		feedback.save()
		self.assertEqual(len(get_communications(feedback.name)), 1)

		feedback.customer_feedback = "Good, but slow"
		feedback.save()
		self.assertEqual(len(get_communications(feedback.name)), 2)


class TestSubmitCustomerFeedback(CRMTestCase):
	def test_feedback_for_opportunity(self):
		opportunity = make_opportunity()

		out = submit_customer_feedback(
			"Opportunity", opportunity.name, "Remark", "Customer asked to call later",
		)
		self.assertEqual(out["contact_remarks"], "Customer asked to call later")
		self.assertIsNone(out["customer_feedback"])
		self.assertEqual(getdate(out["contact_dt"]), getdate())
		self.assertIsNone(out["feedback_dt"])

		out = submit_customer_feedback("Opportunity", opportunity.name, "Feedback", "Satisfied")
		self.assertEqual(out["customer_feedback"], "Satisfied")
		self.assertEqual(out["contact_remarks"], "Customer asked to call later")
		self.assertEqual(getdate(out["feedback_dt"]), getdate())

		feedbacks = frappe.get_all(
			"Customer Feedback",
			filters={"reference_doctype": "Opportunity", "reference_name": opportunity.name},
			fields=["feedback_from", "party_name", "status"],
		)
		self.assertEqual(
			feedbacks,
			[{"feedback_from": "Lead", "party_name": opportunity.party_name, "status": "Completed"}],
		)

	def test_feedback_for_appointment(self):
		appointment = make_appointment(submit=True)

		submit_customer_feedback("Appointment", appointment.name, "Feedback", "Great visit")
		feedback = frappe.get_doc("Customer Feedback", {"reference_name": appointment.name})
		self.assertEqual(feedback.feedback_from, "Lead")
		self.assertEqual(feedback.party_name, appointment.party_name)

	def test_empty_message(self):
		opportunity = make_opportunity()
		self.assertRaises(
			frappe.ValidationError, submit_customer_feedback, "Opportunity", opportunity.name, "Feedback", "",
		)

	def test_missing_reference(self):
		self.assertRaises(
			frappe.ValidationError,
			submit_customer_feedback,
			"Opportunity",
			"_Test Missing Opportunity",
			"Feedback",
			"Hi",
		)

	def test_reference_without_party(self):
		campaign = frappe.get_doc({"doctype": "Campaign", "campaign_name": "_Test Feedback Campaign"}).insert(
			ignore_if_duplicate=True,
		)
		self.assertRaisesRegex(
			frappe.ValidationError,
			"Could not determine party",
			submit_customer_feedback,
			"Campaign",
			campaign.name,
			"Feedback",
			"Hi",
		)


def make_customer_feedback(**kwargs):
	feedback = frappe.get_doc({"doctype": "Customer Feedback", "feedback_from": "Lead"})
	feedback.update(kwargs)

	if not feedback.party_name:
		feedback.party_name = make_lead().name

	feedback.insert()
	return feedback


def make_feedback_type(**kwargs):
	return (
		frappe.get_doc(
			{
				"doctype": "Feedback Type",
				"feedback_type": "_Test Feedback Type " + frappe.generate_hash(length=8),
				**kwargs,
			},
		)
		.insert()
		.name
	)


def make_feedback_sub_type(feedback_type):
	return (
		frappe.get_doc(
			{
				"doctype": "Feedback Sub Type",
				"feedback_sub_type": "_Test Feedback Sub Type " + frappe.generate_hash(length=8),
				"feedback_type": feedback_type,
			},
		)
		.insert()
		.name
	)


def make_feedback_status(feedback_type):
	return (
		frappe.get_doc(
			{
				"doctype": "Feedback Status",
				"feedback_status": "_Test Feedback Status " + frappe.generate_hash(length=8),
				"feedback_type": feedback_type,
			},
		)
		.insert()
		.name
	)


def make_feedback_source():
	return (
		frappe.get_doc(
			{
				"doctype": "Feedback Source",
				"feedback_source": "_Test Feedback Source " + frappe.generate_hash(length=8),
			},
		)
		.insert()
		.name
	)


def get_communications(feedback):
	names = frappe.get_all(
		"Communication",
		filters={"reference_doctype": "Customer Feedback", "reference_name": feedback},
		order_by="creation",
		pluck="name",
	)
	return [frappe.get_doc("Communication", name) for name in names]
