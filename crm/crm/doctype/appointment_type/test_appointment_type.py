# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.utils import add_days, combine_datetime, formatdate, get_datetime, getdate, nowdate

from crm.tests.utils import CRMTestCase


class TestAppointmentType(CRMTestCase):
	def test_negative_duration(self):
		self.assertRaises(frappe.ValidationError, make_appointment_type, appointment_duration=-30)

	def test_negative_slot_duration(self):
		slots = [get_slot(nowdate(), "09:00", "10:00", duration=-30)]
		self.assertRaises(frappe.ValidationError, make_appointment_type, slots=slots)

	def test_number_of_agents_must_be_positive(self):
		self.assertRaises(frappe.ValidationError, make_appointment_type, number_of_agents=0)

	def test_number_of_agents_from_service_advisors(self):
		from crm.crm.doctype.sales_person.test_sales_person import make_sales_person

		advisors = [make_sales_person().name, make_sales_person().name]
		appointment_type = make_appointment_type(
			number_of_agents=5,
			service_advisors=[{"service_advisor": d} for d in advisors],
		)
		self.assertEqual(appointment_type.number_of_agents, 2)
		self.assertEqual(appointment_type.get_service_advisors(), advisors)

	def test_slot_from_time_after_to_time(self):
		slots = [get_slot(nowdate(), "12:00", "10:00")]
		self.assertRaises(frappe.ValidationError, make_appointment_type, slots=slots)

	def test_slot_range_must_be_multiple_of_duration(self):
		slots = [get_slot(nowdate(), "09:00", "10:30")]
		self.assertRaises(frappe.ValidationError, make_appointment_type, appointment_duration=60, slots=slots)

		make_appointment_type(appointment_duration=30, slots=slots)

	def test_slot_duration_is_required(self):
		slots = [get_slot(nowdate(), "09:00", "10:00")]
		self.assertRaises(frappe.ValidationError, make_appointment_type, appointment_duration=0, slots=slots)

	def test_timeslots_without_availability(self):
		appointment_type = make_appointment_type()
		self.assertIsNone(appointment_type.get_timeslots(nowdate()))
		self.assertTrue(appointment_type.is_in_timeslot(combine_datetime(nowdate(), "03:00")))

	def test_timeslots(self):
		date = add_days(nowdate(), 1)
		appointment_type = make_appointment_type(
			appointment_duration=60,
			slots=[
				get_slot(date, "14:00", "15:00"),
				get_slot(date, "09:00", "11:00"),
				get_slot(date, "16:00", "17:00", duration=30),
			],
		)

		self.assertEqual(
			appointment_type.get_timeslots(date),
			[
				(get_dt(date, "09:00"), get_dt(date, "10:00")),
				(get_dt(date, "10:00"), get_dt(date, "11:00")),
				(get_dt(date, "14:00"), get_dt(date, "15:00")),
				(get_dt(date, "16:00"), get_dt(date, "16:30")),
				(get_dt(date, "16:30"), get_dt(date, "17:00")),
			],
		)

		# No availability set for the next day of the week
		self.assertEqual(appointment_type.get_timeslots(add_days(date, 1)), [])

	def test_dated_slots_replace_weekly_slots(self):
		date = add_days(nowdate(), 1)
		appointment_type = make_appointment_type(
			appointment_duration=60,
			slots=[
				get_slot(date, "09:00", "10:00"),
				get_slot(date, "12:00", "13:00", from_date=date, to_date=date),
			],
		)

		self.assertEqual(
			appointment_type.get_timeslots(date), [(get_dt(date, "12:00"), get_dt(date, "13:00"))]
		)
		self.assertEqual(
			appointment_type.get_timeslots(add_days(date, 7)),
			[(get_dt(add_days(date, 7), "09:00"), get_dt(add_days(date, 7), "10:00"))],
		)

	def test_is_in_timeslot(self):
		date = add_days(nowdate(), 1)
		appointment_type = make_appointment_type(slots=[get_slot(date, "09:00", "12:00")])

		self.assertTrue(appointment_type.is_in_timeslot(get_dt(date, "09:00"), get_dt(date, "10:00")))
		self.assertTrue(appointment_type.is_in_timeslot(get_dt(date, "11:00"), duration=60))
		self.assertFalse(appointment_type.is_in_timeslot(get_dt(date, "11:30"), get_dt(date, "12:30")))
		self.assertFalse(appointment_type.is_in_timeslot(get_dt(date, "08:00"), get_dt(date, "09:00")))
		self.assertFalse(appointment_type.is_in_timeslot(get_dt(add_days(date, 1), "09:00"), duration=60))


def make_appointment_type(slots=None, **kwargs):
	appointment_type = frappe.get_doc(
		{
			"doctype": "Appointment Type",
			"appointment_type_name": "_Test Appointment Type " + frappe.generate_hash(length=8),
			"appointment_duration": 60,
			"number_of_agents": 1,
			"advance_booking_days": 0,
		}
	)
	appointment_type.update(kwargs)
	appointment_type.set("availability_of_slots", slots or [])
	appointment_type.insert()
	return appointment_type


def get_slot(date, from_time, to_time, **kwargs):
	return {
		"day_of_week": formatdate(getdate(date), "EEEE"),
		"from_time": from_time,
		"to_time": to_time,
		**kwargs,
	}


def get_dt(date, time):
	return get_datetime(combine_datetime(date, time))
