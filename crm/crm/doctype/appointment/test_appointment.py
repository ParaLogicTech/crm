# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests.utils import change_settings
from frappe.utils import (
	add_days,
	formatdate,
	get_datetime,
	get_time,
	getdate,
	now_datetime,
	nowdate,
)

from crm.crm.doctype.appointment.appointment import (
	Appointment,
	auto_mark_missed,
	count_appointments_in_slot,
	get_appointment_timeslots,
	get_appointment_timeslots_for_daterange,
	get_appointments_for_missed_notification,
	get_appointments_for_reminder_notification,
	get_events,
	get_rescheduled_appointment,
	link_with_opportunity,
	send_appointment_missed_notifications,
	send_appointment_reminder_notifications,
	update_status,
)
from crm.crm.doctype.appointment_type.test_appointment_type import get_dt, get_slot, make_appointment_type
from crm.crm.doctype.lead.test_lead import make_lead
from crm.crm.doctype.opportunity.opportunity import make_appointment as make_appointment_from_opportunity
from crm.crm.doctype.opportunity.opportunity import submit_communication_with_action
from crm.crm.doctype.opportunity.test_opportunity import make_opportunity
from crm.crm.doctype.sales_person.test_sales_person import make_sales_person
from crm.tests.utils import CRMTestCase


class TestAppointment(CRMTestCase):
	def test_party_details_from_lead(self):
		lead = make_lead(
			lead_name="Hamza Iqbal",
			company_name="Iqbal Logistics",
			email_id="hamza@example.com",
			mobile_no="03001239876",
		)

		appointment = make_appointment(party_name=lead.name)
		self.assertEqual(appointment.customer_name, "Iqbal Logistics")
		self.assertEqual(appointment.contact_display, "Hamza Iqbal")
		self.assertEqual(appointment.contact_email, "hamza@example.com")
		self.assertEqual(appointment.contact_mobile, "03001239876")

	def test_appointment_for_must_be_lead(self):
		self.assertRaises(frappe.ValidationError, Appointment.validate_appointment_for, "Customer")
		Appointment.validate_appointment_for("Lead")

	def test_scheduled_date_time(self):
		date = add_days(nowdate(), 2)
		appointment_type = make_appointment_type(appointment_duration=45)

		appointment = make_appointment(
			appointment_type=appointment_type.name, scheduled_dt=get_dt(date, "10:00"),
		)
		self.assertEqual(appointment.scheduled_dt, get_dt(date, "10:00"))
		self.assertEqual(appointment.end_dt, get_dt(date, "10:45"))
		self.assertEqual(appointment.appointment_duration, 45)
		self.assertEqual(appointment.scheduled_day_of_week, formatdate(date, "EEEE"))

		appointment = make_appointment(
			appointment_type=appointment_type.name,
			scheduled_dt=get_dt(date, "11:00"),
			appointment_duration=20,
		)
		self.assertEqual(appointment.end_dt, get_dt(date, "11:20"))

	def test_status_lifecycle(self):
		appointment = make_appointment()
		self.assertEqual(appointment.status, "Draft")

		appointment.submit()
		self.assertEqual(appointment.status, "Open")
		self.assertTrue(appointment.confirmation_dt)

		update_status(appointment.name, "Checked In")
		appointment.reload()
		self.assertEqual(appointment.status, "Checked In")
		self.assertTrue(appointment.check_in_dt)
		self.assertEqual(appointment.check_in_user, frappe.session.user)

		update_status(appointment.name, "Closed")
		appointment.reload()
		self.assertEqual(appointment.status, "Closed")
		self.assertTrue(appointment.is_closed)

		update_status(appointment.name, "Open")
		appointment.reload()
		self.assertEqual(appointment.status, "Open")
		self.assertFalse(appointment.is_closed)
		self.assertFalse(appointment.is_checked_in)
		self.assertIsNone(appointment.check_in_dt)

		appointment.cancel()
		self.assertEqual(appointment.status, "Cancelled")

	def test_missed_status(self):
		past = make_appointment(scheduled_dt=get_dt(add_days(nowdate(), -1), "10:00"), submit=True)
		self.assertEqual(past.status, "Missed")

		future = make_appointment(submit=True)
		update_status(future.name, "Missed")
		self.assertEqual(frappe.db.get_value("Appointment", future.name, "status"), "Missed")

	def test_calendar_event(self):
		advisor = make_sales_person()
		appointment_type = make_appointment_type(create_calendar_event=1)

		appointment = make_appointment(appointment_type=appointment_type.name, service_advisor=advisor.name)
		self.assertFalse(appointment.calendar_event)

		appointment.submit()
		event = frappe.get_doc("Event", appointment.calendar_event)
		self.assertEqual(event.subject, f"Appointment with {appointment.customer_name}")
		self.assertEqual(event.starts_on, appointment.scheduled_dt)
		self.assertEqual(event.ends_on, appointment.end_dt)
		self.assertEqual(
			{(d.reference_doctype, d.reference_docname) for d in event.event_participants},
			{("Lead", appointment.party_name), ("Sales Person", advisor.name)},
		)

	def test_no_calendar_event(self):
		appointment = make_appointment(submit=True)
		self.assertFalse(appointment.calendar_event)

	def test_past_timeslot(self):
		yesterday = get_dt(add_days(nowdate(), -1), "10:00")

		appointment_type = make_appointment_type(validate_past_timeslot=1)
		self.assertRaises(
			frappe.ValidationError,
			make_appointment,
			appointment_type=appointment_type.name,
			scheduled_dt=yesterday,
		)

		appointment_type = make_appointment_type(validate_past_timeslot=0)
		make_appointment(appointment_type=appointment_type.name, scheduled_dt=yesterday)

	def test_timeslot_outside_availability(self):
		date = add_days(nowdate(), 2)
		slots = [get_slot(date, "09:00", "12:00")]

		appointment_type = make_appointment_type(validate_availability=1, slots=slots)
		make_appointment(appointment_type=appointment_type.name, scheduled_dt=get_dt(date, "10:00"))
		self.assertRaises(
			frappe.ValidationError,
			make_appointment,
			appointment_type=appointment_type.name,
			scheduled_dt=get_dt(date, "13:00"),
		)

		appointment_type = make_appointment_type(validate_availability=0, slots=slots)
		make_appointment(appointment_type=appointment_type.name, scheduled_dt=get_dt(date, "13:00"))

	def test_advance_booking_days(self):
		appointment_type = make_appointment_type(validate_availability=1, advance_booking_days=1)

		make_appointment(
			appointment_type=appointment_type.name, scheduled_dt=get_dt(add_days(nowdate(), 1), "10:00"),
		)
		self.assertRaises(
			frappe.ValidationError,
			make_appointment,
			appointment_type=appointment_type.name,
			scheduled_dt=get_dt(add_days(nowdate(), 2), "10:00"),
		)

	def test_slot_capacity(self):
		date = add_days(nowdate(), 2)
		appointment_type = make_appointment_type(validate_availability=1, number_of_agents=1)

		# Draft appointments don't take up a slot
		make_appointment(appointment_type=appointment_type.name, scheduled_dt=get_dt(date, "10:00"))
		make_appointment(
			appointment_type=appointment_type.name, scheduled_dt=get_dt(date, "10:00"), submit=True,
		)

		self.assertRaises(
			frappe.ValidationError,
			make_appointment,
			appointment_type=appointment_type.name,
			scheduled_dt=get_dt(date, "10:30"),
		)
		make_appointment(appointment_type=appointment_type.name, scheduled_dt=get_dt(date, "11:00"))

	def test_service_advisor_not_allowed_for_appointment_type(self):
		allowed = make_sales_person()
		other = make_sales_person()
		appointment_type = make_appointment_type(
			validate_service_advisor_availability=1,
			service_advisors=[{"service_advisor": allowed.name}],
		)

		make_appointment(appointment_type=appointment_type.name, service_advisor=allowed.name)
		self.assertRaises(
			frappe.ValidationError,
			make_appointment,
			appointment_type=appointment_type.name,
			service_advisor=other.name,
		)

	def test_service_advisor_double_booked(self):
		date = add_days(nowdate(), 2)
		advisor = make_sales_person()
		make_appointment(scheduled_dt=get_dt(date, "10:00"), service_advisor=advisor.name, submit=True)

		appointment_type = make_appointment_type(validate_service_advisor_availability=1)
		self.assertRaises(
			frappe.ValidationError,
			make_appointment,
			appointment_type=appointment_type.name,
			scheduled_dt=get_dt(date, "10:30"),
			service_advisor=advisor.name,
		)
		make_appointment(
			appointment_type=appointment_type.name,
			scheduled_dt=get_dt(date, "11:00"),
			service_advisor=advisor.name,
		)

	def test_service_advisor_mandatory(self):
		appointment_type = make_appointment_type(service_advisor_mandatory=1)

		appointment = make_appointment(appointment_type=appointment_type.name)
		self.assertRaises(frappe.ValidationError, appointment.submit)

		appointment.reload()
		appointment.service_advisor = make_sales_person().name
		appointment.submit()

	def test_appointment_source_without_mandatory_service_advisor(self):
		appointment_type = make_appointment_type(service_advisor_mandatory=1)
		source = make_appointment_source(service_advisor_non_mandatory=1)

		make_appointment(appointment_type=appointment_type.name, appointment_source=source, submit=True)

	def test_appointment_source_disables_notifications(self):
		source = make_appointment_source(disable_automated_notifications=1)

		self.assertTrue(make_appointment(appointment_source=source).disable_automated_notifications)
		self.assertFalse(make_appointment().disable_automated_notifications)

	def test_service_advisor_from_user(self):
		own = make_sales_person(user_id=frappe.session.user)
		other = make_sales_person()
		appointment_type = make_appointment_type(service_advisor_validate_self=1)

		appointment = make_appointment(appointment_type=appointment_type.name)
		self.assertEqual(appointment.service_advisor, own.name)
		self.assertEqual(appointment.sales_person, own.name)

		self.assertRaises(
			frappe.ValidationError,
			make_appointment,
			appointment_type=appointment_type.name,
			service_advisor=other.name,
		)

	def test_reschedule(self):
		date = add_days(nowdate(), 2)
		appointment_type = make_appointment_type(validate_availability=1, number_of_agents=1)
		previous = make_appointment(
			appointment_type=appointment_type.name,
			scheduled_dt=get_dt(date, "10:00"),
			voice_of_customer="Engine noise",
			submit=True,
		)

		rescheduled = get_rescheduled_appointment(previous.name)
		self.assertEqual(rescheduled.previous_appointment, previous.name)
		self.assertEqual(rescheduled.party_name, previous.party_name)
		self.assertEqual(rescheduled.appointment_type, previous.appointment_type)
		self.assertEqual(rescheduled.voice_of_customer, "Engine noise")
		self.assertFalse(rescheduled.scheduled_dt)

		rescheduled.scheduled_date = add_days(date, 1)
		rescheduled.scheduled_time = "11:00:00"
		rescheduled.insert()
		self.assertEqual(rescheduled.previous_appointment_dt, previous.scheduled_dt)

		rescheduled.submit()
		previous.reload()
		self.assertEqual(previous.status, "Rescheduled")
		self.assertEqual(rescheduled.status, "Open")

		# A rescheduled appointment frees its time slot
		self.assertEqual(
			count_appointments_in_slot(previous.scheduled_dt, previous.end_dt, appointment_type.name), 0,
		)
		make_appointment(appointment_type=appointment_type.name, scheduled_dt=get_dt(date, "10:00"))

	def test_reschedule_requires_open_previous_appointment(self):
		draft = make_appointment()
		self.assertRaises(frappe.ValidationError, make_appointment, previous_appointment=draft.name)

		closed = make_appointment(submit=True)
		update_status(closed.name, "Closed")
		self.assertRaises(frappe.ValidationError, make_appointment, previous_appointment=closed.name)

		cancelled = make_appointment(submit=True)
		cancelled.cancel()
		self.assertRaises(frappe.ValidationError, make_appointment, previous_appointment=cancelled.name)

	def test_clean_remarks(self):
		appointment = make_appointment(
			remarks="  Customer   will be late ", voice_of_customer=" Brake   issue ",
		)
		self.assertEqual(appointment.remarks, "Customer will be late")
		self.assertEqual(appointment.voice_of_customer, "Brake issue")

	def test_auto_mark_missed(self):
		overdue = make_appointment(submit=True)
		just_overdue = make_appointment(submit=True)
		due_today = make_appointment(submit=True)

		# Simulate appointments that were never checked in
		overdue.db_set("scheduled_date", add_days(nowdate(), -2))
		just_overdue.db_set("scheduled_date", add_days(nowdate(), -1))
		due_today.db_set("scheduled_date", nowdate())

		with change_settings("Appointment Booking Settings", auto_mark_missed_days=1):
			auto_mark_missed()

		self.assertEqual(frappe.db.get_value("Appointment", overdue.name, "status"), "Missed")
		self.assertEqual(frappe.db.get_value("Appointment", just_overdue.name, "status"), "Missed")
		self.assertEqual(frappe.db.get_value("Appointment", due_today.name, "status"), "Open")

	def test_get_appointment_timeslots(self):
		date = add_days(nowdate(), 2)
		advisors = [make_sales_person().name, make_sales_person().name]
		appointment_type = make_appointment_type(
			service_advisors=[{"service_advisor": d} for d in advisors],
			slots=[get_slot(date, "09:00", "12:00")],
		)
		make_appointment(
			appointment_type=appointment_type.name,
			scheduled_dt=get_dt(date, "10:00"),
			service_advisor=advisors[0],
			submit=True,
		)
		# Drafts are not booked
		make_appointment(appointment_type=appointment_type.name, scheduled_dt=get_dt(date, "11:00"))

		out = get_appointment_timeslots(date, appointment_type.name, include_available_agents=True)
		self.assertEqual(
			[(d.timeslot_start, d.booked, d.available) for d in out.timeslots],
			[(get_dt(date, "09:00"), 0, 2), (get_dt(date, "10:00"), 1, 1), (get_dt(date, "11:00"), 0, 2)],
		)
		self.assertEqual(out.timeslots[1].available_agents, [advisors[1]])
		self.assertEqual(out.timeslots[0].available_agents, advisors)

	def test_get_appointment_timeslots_for_daterange(self):
		date = add_days(nowdate(), 2)
		appointment_type = make_appointment_type(number_of_agents=1, slots=[get_slot(date, "09:00", "11:00")])
		make_appointment(
			appointment_type=appointment_type.name, scheduled_dt=get_dt(date, "09:00"), submit=True,
		)

		out = get_appointment_timeslots_for_daterange(appointment_type.name, date, add_days(date, 1))
		self.assertEqual(
			[(d.date, d.no_of_timeslots, d.available_timeslots) for d in out],
			[(getdate(date), 2, 1), (getdate(add_days(date, 1)), 0, 0)],
		)

		self.assertRaises(
			frappe.ValidationError,
			get_appointment_timeslots_for_daterange,
			appointment_type.name,
			date,
			add_days(date, -1),
		)

	def test_get_events(self):
		date = add_days(nowdate(), 2)
		submitted = make_appointment(scheduled_dt=get_dt(date, "10:00"), submit=True)
		cancelled = make_appointment(scheduled_dt=get_dt(date, "11:00"), submit=True)
		cancelled.cancel()

		events = [d.name for d in get_events(date, add_days(date, 1))]
		self.assertIn(submitted.name, events)
		self.assertNotIn(cancelled.name, events)

	def test_validate_notification(self):
		appointment = make_appointment()
		self.assertFalse(appointment.validate_notification("Appointment Confirmation"))
		self.assertRaises(
			frappe.ValidationError,
			appointment.validate_notification,
			"Appointment Confirmation",
			throw=True,
		)

		appointment.submit()
		self.assertTrue(appointment.validate_notification("Appointment Confirmation"))
		self.assertTrue(appointment.validate_notification("Appointment Reminder"))
		self.assertFalse(appointment.validate_notification("Appointment Missed"))
		self.assertFalse(appointment.validate_notification("Appointment Cancellation"))

		appointment.cancel()
		self.assertTrue(appointment.validate_notification("Appointment Cancellation"))
		self.assertFalse(appointment.validate_notification("Appointment Confirmation"))

	def test_no_confirmation_after_appointment_has_started(self):
		started = now_datetime() - timedelta(minutes=5)
		if getdate(started) != getdate():
			self.skipTest("Appointment would start yesterday")

		appointment = make_appointment(scheduled_dt=started, appointment_duration=60, submit=True)
		self.assertEqual(appointment.status, "Open")
		self.assertFalse(appointment.validate_notification("Appointment Confirmation"))
		self.assertFalse(appointment.validate_notification("Appointment Reminder"))

	def test_appointments_for_reminder_notification(self):
		tomorrow = get_dt(add_days(nowdate(), 1), "10:00")
		appointment = make_appointment(scheduled_dt=tomorrow, submit=True)
		disabled = make_appointment(
			scheduled_dt=tomorrow,
			appointment_source=make_appointment_source(disable_automated_notifications=1),
			submit=True,
		)
		later = make_appointment(scheduled_dt=get_dt(add_days(nowdate(), 2), "10:00"), submit=True)
		for d in (appointment, disabled, later):
			d.db_set("confirmation_dt", add_days(now_datetime(), -1))

		settings = {
			"appointment_reminder_days_before": 1,
			"appointment_reminder_time": "00:00:00",
			"appointment_reminder_confirmation_hours": 0,
		}
		with change_settings("Appointment Booking Settings", settings):
			to_remind = get_appointments_for_reminder_notification(nowdate())

		self.assertIn(appointment.name, to_remind)
		self.assertNotIn(disabled.name, to_remind)
		self.assertNotIn(later.name, to_remind)

	def test_appointments_for_missed_notification(self):
		missed = make_appointment(scheduled_dt=get_dt(add_days(nowdate(), -1), "10:00"), submit=True)
		missed.db_set("confirmation_dt", get_dt(add_days(nowdate(), -2), "10:00"))
		self.assertEqual(missed.status, "Missed")

		with change_settings("Appointment Booking Settings", auto_mark_missed_days=1):
			self.assertIn(missed.name, get_appointments_for_missed_notification(nowdate()))

		with change_settings("Appointment Booking Settings", auto_mark_missed_days=0):
			self.assertEqual(get_appointments_for_missed_notification(nowdate()), [])


class TestAppointmentOpportunity(CRMTestCase):
	def test_make_appointment_from_opportunity(self):
		appointment_type = make_appointment_type()
		opportunity_type = frappe.get_doc(
			{
				"doctype": "Opportunity Type",
				"name": "_Test Appointment Opportunity Type",
				"default_appointment_type": appointment_type.name,
			},
		).insert(ignore_if_duplicate=True)
		sales_person = make_sales_person(is_service_advisor=0)
		opportunity = make_opportunity(opportunity_type=opportunity_type.name, sales_person=sales_person.name)

		appointment = make_appointment_from_opportunity(opportunity.name)
		self.assertEqual(appointment.opportunity, opportunity.name)
		self.assertEqual(appointment.appointment_for, "Lead")
		self.assertEqual(appointment.party_name, opportunity.party_name)
		self.assertEqual(appointment.appointment_type, appointment_type.name)
		self.assertEqual(appointment.sales_person, sales_person.name)

	def test_submitted_appointment_converts_opportunity(self):
		opportunity = make_opportunity()

		appointment = make_appointment(opportunity=opportunity.name, party_name=opportunity.party_name)
		self.assertEqual(frappe.db.get_value("Opportunity", opportunity.name, "status"), "Open")

		appointment.submit()
		self.assertEqual(frappe.db.get_value("Opportunity", opportunity.name, "status"), "Converted")
		self.assertEqual(frappe.db.get_value("Lead", opportunity.party_name, "status"), "Converted")

		opportunity.reload()
		self.assertRaises(frappe.ValidationError, opportunity.set_is_lost, 1, [])

	def test_cancelled_appointment_keeps_opportunity_converted(self):
		# Intended: the Opportunity stays converted while a cancelled Appointment is amended
		opportunity = make_opportunity()
		appointment = make_appointment(
			opportunity=opportunity.name, party_name=opportunity.party_name, submit=True,
		)

		appointment.cancel()
		self.assertEqual(frappe.db.get_value("Opportunity", opportunity.name, "status"), "Converted")
		self.assertEqual(frappe.db.get_value("Lead", opportunity.party_name, "status"), "Converted")

	def test_create_appointment_communication_action(self):
		opportunity = make_opportunity()

		out = submit_communication_with_action("Customer will visit", "Create Appointment", opportunity.name)
		self.assertEqual(out.appointment_doc.opportunity, opportunity.name)
		self.assertEqual(out.appointment_doc.party_name, opportunity.party_name)

	def test_link_with_opportunity(self):
		sales_person = make_sales_person(is_service_advisor=0)
		opportunity = make_opportunity(sales_person=sales_person.name)
		appointment = make_appointment(party_name=opportunity.party_name, submit=True)

		link_with_opportunity(appointment.name, opportunity.name)
		appointment.reload()
		self.assertEqual(appointment.opportunity, opportunity.name)
		self.assertEqual(appointment.sales_person, sales_person.name)
		self.assertEqual(frappe.db.get_value("Opportunity", opportunity.name, "status"), "Converted")

		self.assertRaises(
			frappe.ValidationError, link_with_opportunity, appointment.name, make_opportunity().name,
		)

	def test_link_with_opportunity_after_appointment_date(self):
		opportunity = make_opportunity(transaction_date=add_days(nowdate(), 5))
		appointment = make_appointment(party_name=opportunity.party_name, submit=True)

		self.assertRaises(frappe.ValidationError, link_with_opportunity, appointment.name, opportunity.name)

	def test_link_with_opportunity_links_rescheduled_appointment(self):
		opportunity = make_opportunity()
		previous = make_appointment(party_name=opportunity.party_name, submit=True)
		rescheduled = make_appointment(
			party_name=opportunity.party_name,
			previous_appointment=previous.name,
			scheduled_dt=get_dt(add_days(nowdate(), 3), "10:00"),
			submit=True,
		)

		link_with_opportunity(previous.name, opportunity.name)
		self.assertEqual(
			frappe.db.get_value("Appointment", rescheduled.name, "opportunity"), opportunity.name,
		)


REMINDER_SETTINGS = {
	"appointment_reminder_days_before": 1,
	"appointment_reminder_time": "00:00:00",
	"appointment_reminder_confirmation_hours": 0,
}


class TestAppointmentNotifications(CRMTestCase):
	"""crm decides when to notify by running notify_appointment_* methods. Notifications and other apps'
	doc_events do the sending, so these tests record the methods instead."""

	def setUp(self):
		super().setUp()
		self.notified = []
		self.failing_appointment = None
		original_run_method = Appointment.run_method

		def run_method(doc, method, *args, **kwargs):
			if not method.startswith("notify_"):
				return original_run_method(doc, method, *args, **kwargs)

			self.notified.append((doc.name, method))
			if doc.name == self.failing_appointment:
				raise frappe.ValidationError("SMS gateway unavailable")

		patcher = patch.object(Appointment, "run_method", run_method)
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_confirmation_on_submit(self):
		appointment = make_appointment(submit=True)
		self.assertEqual(self.notified, [(appointment.name, "notify_appointment_confirmation")])

	def test_cancellation_on_cancel(self):
		appointment = make_appointment(submit=True)
		appointment.cancel()
		self.assertEqual(self.notified[-1], (appointment.name, "notify_appointment_cancellation"))

	def test_no_automated_notifications_for_source(self):
		source = make_appointment_source(disable_automated_notifications=1)

		appointment = make_appointment(appointment_source=source, submit=True)
		appointment.cancel()
		self.assertEqual(self.notified, [])

	def test_reminders(self):
		tomorrow = get_dt(add_days(nowdate(), 1), "10:00")
		due = make_confirmed_appointment(tomorrow)
		later = make_confirmed_appointment(get_dt(add_days(nowdate(), 2), "10:00"))
		self.notified.clear()

		with change_settings("Appointment Booking Settings", REMINDER_SETTINGS), reminders_enabled():
			run_scheduler_job(send_appointment_reminder_notifications)
			self.assertEqual(self.notified, [(due.name, "notify_appointment_reminder")])
			self.assertNotIn(later.name, [name for name, method in self.notified])

			# Already sent today
			run_scheduler_job(send_appointment_reminder_notifications)
			self.assertEqual(len(self.notified), 1)

	def test_no_reminders_before_reminder_time(self):
		make_confirmed_appointment(get_dt(add_days(nowdate(), 1), "10:00"))
		self.notified.clear()

		settings = {**REMINDER_SETTINGS, "appointment_reminder_time": "23:59:59"}
		with change_settings("Appointment Booking Settings", settings), reminders_enabled():
			run_scheduler_job(send_appointment_reminder_notifications)

		self.assertEqual(self.notified, [])

	def test_no_reminders_without_reminder_notification(self):
		make_confirmed_appointment(get_dt(add_days(nowdate(), 1), "10:00"))
		self.notified.clear()

		with (
			change_settings("Appointment Booking Settings", REMINDER_SETTINGS),
			reminders_enabled(False),
		):
			run_scheduler_job(send_appointment_reminder_notifications)

		self.assertEqual(self.notified, [])

	def test_failed_reminder_does_not_stop_the_others(self):
		tomorrow = get_dt(add_days(nowdate(), 1), "10:00")
		failing = make_confirmed_appointment(tomorrow)
		other = make_confirmed_appointment(tomorrow + timedelta(hours=1))
		self.notified.clear()
		self.failing_appointment = failing.name

		# Error Log is a MyISAM table, so the test's rollback doesn't remove it
		self.addCleanup(
			frappe.db.delete,
			"Error Log",
			{"reference_doctype": "Appointment", "reference_name": failing.name},
		)

		with change_settings("Appointment Booking Settings", REMINDER_SETTINGS), reminders_enabled():
			run_scheduler_job(send_appointment_reminder_notifications)

		self.assertIn((other.name, "notify_appointment_reminder"), self.notified)
		self.assertTrue(
			frappe.db.exists(
				"Error Log",
				{
					"reference_doctype": "Appointment",
					"reference_name": failing.name,
					"method": "Error sending Appointment Reminder Notification",
				},
			),
		)

	def test_missed_notifications(self):
		missed = make_confirmed_appointment(get_dt(add_days(nowdate(), -1), "10:00"))
		self.assertEqual(frappe.db.get_value("Appointment", missed.name, "status"), "Missed")
		self.notified.clear()

		with (
			change_settings("Appointment Booking Settings", auto_mark_missed_days=1),
			patch("crm.crm.doctype.appointment.appointment.has_notification", return_value=True),
		):
			run_scheduler_job(send_appointment_missed_notifications)

		self.assertEqual(self.notified, [(missed.name, "notify_appointment_missed")])

	def test_no_missed_notifications_without_auto_mark_missed(self):
		make_confirmed_appointment(get_dt(add_days(nowdate(), -1), "10:00"))
		self.notified.clear()

		with (
			change_settings("Appointment Booking Settings", auto_mark_missed_days=0),
			patch("crm.crm.doctype.appointment.appointment.has_notification", return_value=True),
		):
			run_scheduler_job(send_appointment_missed_notifications)

		self.assertEqual(self.notified, [])

	def test_reminder_schedule(self):
		scheduled_dt = get_dt(add_days(nowdate(), 2), "10:00")
		settings = {**REMINDER_SETTINGS, "appointment_reminder_time": "09:00:00"}

		with change_settings("Appointment Booking Settings", settings):
			draft = make_appointment(scheduled_dt=scheduled_dt)
			submitted = make_appointment(scheduled_dt=scheduled_dt + timedelta(hours=1), submit=True)

			with reminders_enabled():
				self.assertIsNone(draft.get_reminder_schedule())
				self.assertEqual(submitted.get_reminder_schedule(), get_dt(add_days(nowdate(), 1), "09:00"))

			with reminders_enabled(False):
				self.assertIsNone(submitted.get_reminder_schedule())


def make_confirmed_appointment(scheduled_dt):
	"""A submitted appointment that was confirmed two days before it's scheduled"""
	appointment = make_appointment(scheduled_dt=scheduled_dt, submit=True)
	appointment.db_set("confirmation_dt", get_datetime(scheduled_dt) - timedelta(days=2))
	return appointment


def reminders_enabled(enabled=True):
	return patch("crm.crm.doctype.appointment.appointment.automated_reminder_enabled", return_value=enabled)


def run_scheduler_job(job):
	# The jobs commit (and roll back on errors) after each appointment, which would end the test's transaction
	with patch.object(frappe.db, "commit"), patch.object(frappe.db, "rollback"):
		job()


def get_appointment(appointment_type=None, scheduled_dt=None, **kwargs):
	scheduled_dt = get_datetime(scheduled_dt or get_dt(add_days(nowdate(), 2), "10:00"))

	appointment = frappe.get_doc(
		{
			"doctype": "Appointment",
			"appointment_for": "Lead",
			"appointment_type": appointment_type or make_appointment_type().name,
			"scheduled_date": getdate(scheduled_dt),
			"scheduled_time": get_time(scheduled_dt),
		},
	)
	appointment.update(kwargs)

	if not appointment.party_name:
		appointment.party_name = make_lead().name

	return appointment


def make_appointment(submit=False, **kwargs):
	appointment = get_appointment(**kwargs)
	appointment.insert()

	if submit:
		appointment.submit()

	return appointment


def make_appointment_source(**kwargs):
	source = frappe.get_doc(
		{
			"doctype": "Appointment Source",
			"source_name": "_Test Appointment Source " + frappe.generate_hash(length=8),
		},
	)
	source.update(kwargs)
	source.insert()
	return source.name
