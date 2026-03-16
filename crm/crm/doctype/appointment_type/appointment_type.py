# -*- coding: utf-8 -*-
# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
import datetime
from frappe import _
from frappe.utils import getdate, combine_datetime, cint, get_datetime
from frappe.model.document import Document


class AppointmentType(Document):
	def validate(self):
		self.validate_appointment_duration()
		self.validate_number_of_agents()
		self.validate_availability_of_slots()

	def validate_appointment_duration(self):
		self.appointment_duration = cint(self.appointment_duration)
		if cint(self.appointment_duration) < 0:
			frappe.throw(_("Default Duration cannot be negative"))

		for d in self.availability_of_slots:
			if cint(d.duration) < 0:
				frappe.throw(_("Row #{0}: Slot Duration cannot be negative").format(d.idx))

	def validate_number_of_agents(self):
		if self.get('sales_persons'):
			self.number_of_agents = len(self.sales_persons)

		if cint(self.number_of_agents) <= 0:
			frappe.throw(_("Number of Available Agents must be a positive number"))

	def validate_availability_of_slots(self):
		for record in self.availability_of_slots:
			duration = cint(record.duration or self.appointment_duration)
			from_time = combine_datetime("1970-01-01", record.from_time)
			to_time = combine_datetime("1970-01-01", record.to_time)

			if not duration:
				frappe.throw(_("Row #{0}: Duration cannot be 0, please set default duration or slot duration").format(
					record.idx
				))

			if from_time > to_time:
				frappe.throw(_("Row #{0}: <b>From Time</b> cannot be later than <b>To Time</b> on {1}").format(
					record.idx, record.day_of_week
				))

			timedelta = to_time - from_time
			if timedelta.total_seconds() % (duration * 60):
				frappe.throw(_("Row #{0}: The difference between From Time and To Time must be a multiple of duration of {1} minutes").format(
					record.idx, frappe.bold(duration)
				))

	def is_in_timeslot(self, start_dt, end_dt=None, duration=None):
		start_dt = get_datetime(start_dt)

		timeslot_range = self.get_timeslot_range(start_dt)
		if timeslot_range is None:
			return True

		if end_dt:
			duration = end_dt - start_dt
		elif cint(duration) > 0:
			duration = datetime.timedelta(minutes=duration)
			end_dt = start_dt + duration

		# if no availability data then allow
		if timeslot_range is None:
			return True

		for range_start, range_end, dur in timeslot_range:
			in_range = True
			if not time_in_range(range_start, range_end, start_dt):
				in_range = False

			if end_dt and not time_in_range(range_start, range_end, end_dt):
				in_range = False

			if in_range:
				return True

		return False

	def get_timeslots(self, date):
		timeslot_range = self.get_timeslot_range(date)
		if timeslot_range is None:
			return None

		timeslots = []
		for start_dt, end_dt, duration in timeslot_range:
			timeslot_start = start_dt

			duration_delta = datetime.timedelta(minutes=duration)
			if duration <= 0:
				continue

			while timeslot_start + duration_delta <= end_dt:
				timeslot_end = timeslot_start + duration_delta
				timeslots.append((timeslot_start, timeslot_end))
				timeslot_start += duration_delta

		timeslots = sorted(timeslots, key=lambda d: (d[0], d[1]))
		return timeslots

	def get_timeslot_range(self, date):
		if not self.get('availability_of_slots'):
			return None

		date = getdate(date)
		day_of_week = frappe.utils.formatdate(date, "EEEE")

		timeslot_rows = []

		for d in self.availability_of_slots:
			if d.day_of_week != day_of_week:
				continue
			if d.from_date and date < getdate(d.from_date):
				continue
			if d.to_date and date > getdate(d.to_date):
				continue

			timeslot_rows.append(d)

		has_date_filter = any(d for d in timeslot_rows if d.from_date or d.to_date)
		if has_date_filter:
			timeslot_rows = [d for d in timeslot_rows if d.from_date or d.to_date]

		timeslot_range = [(
			combine_datetime(date, d.from_time),
			combine_datetime(date, d.to_time),
			cint(d.duration or self.appointment_duration)
		) for d in timeslot_rows]

		return timeslot_range

	def is_holiday(self, date):
		return False

	def get_holidays(self, from_date, to_date):
		return []

	def get_sales_persons(self):
		return [d.sales_person for d in self.sales_persons]


def time_in_range(start, end, x):
	"""Return true if x is in the range [start, end]"""
	if start <= end:
		return start <= x <= end
	else:
		return start <= x or x <= end
