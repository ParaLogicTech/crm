# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import today, getdate, cint, clean_whitespace, comma_or, cstr, validate_email_address
from frappe.model.mapper import get_mapped_doc
from frappe.email.inbox import link_communication_to_document
from frappe.utils.status_updater import StatusUpdater
from frappe.model.document import Document
from crm.crm.doctype.sales_person.sales_person import get_sales_person_from_user
from crm.crm.utils import _get_contact_details, render_address, get_primary_address, get_primary_contact
from frappe.rate_limiter import rate_limit
import json


subject_field = "title"
sender_field = "contact_email"


class Opportunity(StatusUpdater):
	selling_or_buying = "selling"

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.force_party_fields = [
			'customer_name', 'tax_id', 'tax_cnic', 'tax_strn', 'territory',
			'address_display', 'contact_display', 'contact_email', 'contact_mobile', 'contact_phone'
		]

	def get_feed(self):
		return _("From {0}").format(self.get("customer_name") or self.get('party_name'))

	def validate(self):
		self.set_missing_values()
		self.validate_contact_no()
		self.validate_follow_up()
		self.set_status()
		self.set_title()

	def after_insert(self):
		self.update_lead_status()

	def after_delete(self):
		self.update_lead_status(status="Interested")

	@classmethod
	def get_allowed_party_types(cls):
		return ["Lead"]

	@classmethod
	def validate_opportunity_from(cls, opportunity_from):
		allowed_party_types = cls.get_allowed_party_types()
		if opportunity_from not in allowed_party_types:
			frappe.throw(_("Opportunity From must be {0}").format(comma_or(allowed_party_types)))

	def set_title(self):
		self.title = self.customer_name
		if self.contact_display and self.contact_display != self.customer_name:
			self.title = "{0} ({1})".format(self.contact_display, self.customer_name)

	def set_status(self, update=False, status=None, update_modified=True):
		previous_status = self.status

		if status:
			self.status = status

		has_active_quotation = self.has_active_quotation()

		if self.is_converted():
			self.status = "Converted"
		elif self.status == "Closed":
			self.status = "Closed"
		elif self.status == "Lost" or (not has_active_quotation and self.has_lost_quotation()):
			self.status = "Lost"
		elif self.get("next_follow_up") and getdate(self.next_follow_up) >= getdate():
			self.status = "To Follow Up"
		elif has_active_quotation:
			self.status = "Quotation"
		elif self.has_communication():
			self.status = "Replied"
		else:
			self.status = "Open"

		self.add_status_comment(previous_status)

		if update:
			self.db_set('status', self.status, update_modified=update_modified)

	def set_sales_person_from_user(self):
		if not self.get('sales_person') and self.is_new():
			self.sales_person = get_sales_person_from_user()

	def set_missing_values(self):
		self.conversion_document = frappe.get_cached_value("Opportunity Type", self.opportunity_type, "conversion_document")
		self.set_sales_person_from_user()
		self.set_customer_details()
		self.set_sales_person_details()

	def set_customer_details(self):
		customer_details = get_customer_details(self.as_dict())
		for k, v in customer_details.items():
			if self.meta.has_field(k) and (not self.get(k) or k in self.force_party_fields):
				self.set(k, v)

	def set_sales_person_details(self):
		self.sales_person_mobile_no = None
		self.sales_person_email = None

		if not self.sales_person:
			return

		sales_person = frappe.get_cached_doc("Sales Person", self.sales_person)
		self.sales_person_mobile_no = sales_person.contact_mobile
		self.sales_person_email = sales_person.contact_email

	def validate_contact_no(self):
		if self.flags.ignore_mandatory:
			return

		contact_no_mandatory = cint(frappe.db.get_single_value("CRM Settings", "opportunity_contact_no_mandatory"))
		if contact_no_mandatory and not (self.contact_phone or self.contact_mobile):
			frappe.throw(_("Contact No is mandatory"))

	def validate_follow_up(self):
		self.next_follow_up = self.get_next_follow_up_date()

		for d in self.get('contact_schedule'):
			if not d.get('contact_date') and not d.get('schedule_date'):
				frappe.throw(_("Row #{0}: Please set Contact or Schedule Date in follow up".format(d.idx)))

			if d.is_new() and not d.get('contact_date') and getdate(d.get('schedule_date')) < getdate(today()):
				frappe.throw(_("Row #{0}: Can't schedule a follow up for past dates".format(d.idx)))

	def get_next_follow_up_date(self):
		pending_follow_ups = [d for d in self.get("contact_schedule") if d.schedule_date and not d.contact_date]
		pending_follow_ups = sorted(pending_follow_ups, key=lambda d: (getdate(d.schedule_date), d.idx))

		future_follow_ups = [d for d in pending_follow_ups if getdate(d.schedule_date) >= getdate()]

		next_follow_up = None
		if future_follow_ups:
			next_follow_up = future_follow_ups[0]
		elif pending_follow_ups:
			next_follow_up = pending_follow_ups[-1]

		return getdate(next_follow_up.schedule_date) if next_follow_up else None

	def add_next_follow_up(self, schedule_date, to_discuss=None):
		schedule_date = getdate(schedule_date)

		dup = [d for d in self.get('contact_schedule') if getdate(d.get('schedule_date')) == schedule_date]

		if dup:
			dup = dup[0]
			if (dup.to_discuss and to_discuss != dup.to_discuss) or (not dup.to_discuss and not to_discuss):
				frappe.throw(_("Row #{0}: Follow Up already scheduled for {1}".format(dup.idx, frappe.format(dup.schedule_date))))
			else:
				dup.to_discuss = to_discuss
		else:
			self.append('contact_schedule', {
				'schedule_date': schedule_date,
				'to_discuss': to_discuss,
				'sales_person': get_sales_person_from_user(),
			})

	def set_follow_up_contact_date(self, contact_date):
		follow_up = [f for f in self.get("contact_schedule") if not f.contact_date]
		if follow_up:
			follow_up[0].contact_date = getdate(contact_date)
			return follow_up[0]

	@frappe.whitelist()
	def set_is_lost(self, is_lost, lost_reasons_list=None, detailed_reason=None):
		is_lost = cint(is_lost)

		if is_lost and self.is_converted():
			frappe.throw(_("Cannot declare as Lost because Opportunity is already converted"))

		self.set_next_document_is_lost(is_lost, lost_reasons_list, detailed_reason)

		if is_lost:
			self.set_status(update=True, status="Lost")
			self.db_set("order_lost_reason", detailed_reason)
			self.lost_reasons = []
			for reason in lost_reasons_list:
				self.append('lost_reasons', reason)
		else:
			self.set_status(update=True, status="Open")
			self.db_set('order_lost_reason', None)
			self.lost_reasons = []

		self.update_lead_status()
		self.update_child_table("lost_reasons")
		self.notify_update()

	def set_next_document_is_lost(self, is_lost, lost_reasons_list=None, detailed_reason=None):
		pass

	def update_lead_status(self, status=None):
		if self.opportunity_from == "Lead" and self.party_name:
			doc = frappe.get_doc("Lead", self.party_name)
			doc.set_status(update=True, status=status)
			doc.notify_update()

	def has_active_quotation(self):
		return False

	def has_lost_quotation(self):
		return False

	def is_converted(self):
		if self.is_new():
			return False

		appointment = frappe.db.get_value("Appointment", {
			"opportunity": self.name,
			"docstatus": (">", 0),
		})

		if appointment:
			return True

		return False

	def has_communication(self):
		if self.is_new():
			return False

		return frappe.db.get_value("Communication", filters={
			'reference_doctype': self.doctype,
			'reference_name': self.name,
			'communication_type': ['!=', 'Automated Message']
		})


@frappe.whitelist()
def get_customer_details(args):
	from frappe.model.base_document import get_controller

	if isinstance(args, str):
		args = json.loads(args)

	args = frappe._dict(args)
	out = frappe._dict()

	if not args.opportunity_from or not args.party_name:
		frappe.throw(_("Party is mandatory"))

	opportunity_controller = get_controller("Opportunity")
	opportunity_controller.validate_opportunity_from(args.opportunity_from)

	party = frappe.get_cached_doc(args.opportunity_from, args.party_name)

	# Customer Name
	if party.doctype == "Lead":
		out.customer_name = party.company_name or party.lead_name
	else:
		out.customer_name = party.get("customer_name")

	# Tax IDs
	out.tax_id = party.get('tax_id')
	out.tax_cnic = party.get('tax_cnic')
	out.tax_strn = party.get('tax_strn')

	lead = party if party.doctype == "Lead" else None

	# Address
	out.customer_address = args.customer_address
	if not out.customer_address and party.doctype != "Lead":
		out.customer_address = get_primary_address(party.doctype, party.name)

	out.address_display = render_address(out.customer_address, lead=lead)

	# Contact
	out.contact_person = args.contact_person
	if not out.contact_person and party.doctype != "Lead":
		out.contact_person = get_primary_contact(party.doctype, party.name)

	out.update(_get_contact_details(out.contact_person, lead=lead))

	out.territory = party.get("territory")
	out.campaign = party.get("campaign")

	if party.get("sales_person"):
		out.sales_person = party.get("sales_person")

	if party.get("source") and party.meta.get_options("source") == "Lead Source":
		out.source = party.get("source")

	return out


@frappe.whitelist()
def make_appointment(source_name, target_doc=None):
	def set_missing_values(source, target):
		default_appointment_type = frappe.get_cached_value("Opportunity Type", source.opportunity_type, "default_appointment_type")
		if default_appointment_type:
			target.appointment_type = default_appointment_type

		target.run_method("set_missing_values")

	mapper = {
		"Opportunity": {
			"doctype": "Appointment",
			"field_map": {
				"name": "opportunity",
				"opportunity_from": "appointment_for",
				"applies_to_vehicle": "applies_to_vehicle",
				"applies_to_serial_no": "applies_to_serial_no",
				"vehicle_last_odometer": "vehicle_last_odometer",
				"campaign": "campaign",
				"sales_person": "sales_person",
			}
		}
	}

	frappe.utils.call_hook_method("update_appointment_from_opportunity_mapper", mapper, "Appointment")

	target_doc = get_mapped_doc("Opportunity", source_name, mapper, target_doc, set_missing_values)

	return target_doc


@frappe.whitelist()
def set_multiple_status(names, status):
	names = json.loads(names)
	for name in names:
		opp = frappe.get_doc("Opportunity", name)
		opp.status = status
		opp.save()


def auto_mark_opportunity_as_lost():
	if not frappe.db.get_single_value("CRM Settings", "auto_mark_opportunity_as_lost"):
		return

	mark_opportunity_lost_after_days = frappe.db.get_single_value("CRM Settings", "mark_opportunity_lost_after_days")
	if cint(mark_opportunity_lost_after_days) < 1:
		return

	lost_reasons_list = []
	lost_reason = frappe.db.get_single_value("CRM Settings", "opportunity_auto_lost_reason")
	if lost_reason:
		lost_reasons_list.append({'lost_reason': lost_reason})

	opportunities = frappe.db.sql("""
		SELECT name FROM tabOpportunity
		WHERE status IN ('Open', 'Replied', 'Quotation')
		AND modified < DATE_SUB(CURDATE(), INTERVAL %s DAY)
	""", (mark_opportunity_lost_after_days), as_dict=True)

	for opportunity in opportunities:
		doc = frappe.get_doc("Opportunity", opportunity.get("name"))
		try:
			doc.set_is_lost(True, lost_reasons_list=lost_reasons_list)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			traceback = frappe.get_traceback()
			doc.log_error(
				title=_("Error: auto_mark_opportunity_as_lost for Opportunity: {}").format(doc.name),
				message=traceback,
			)
			frappe.db.commit()


@frappe.whitelist()
def schedule_follow_up(name, schedule_date, to_discuss=None):
	if not schedule_date:
		frappe.throw(_("Schedule Date is mandatory"))

	schedule_date = getdate(schedule_date)
	if schedule_date < getdate():
		frappe.throw(_("Can't schedule a follow up for past dates"))

	opp = frappe.get_doc("Opportunity", name)
	opp.add_next_follow_up(schedule_date, to_discuss)
	opp.save()


@frappe.whitelist()
def submit_communication_with_action(remarks, action, opportunity, follow_up_date=None, lost_reason=None):
	contact_date = getdate()
	remarks = clean_whitespace(remarks)

	if not opportunity:
		frappe.throw(_('Opportunity not provided'))

	if isinstance(opportunity, Document):
		opp = opportunity
	else:
		opp = frappe.get_doc('Opportunity', opportunity)

	if action and opp.status in ['Lost', 'Converted'] and action not in ("Submit Remarks Only", "Schedule Follow Up"):
		frappe.throw(_("Opportunity is already {0}").format(opp.status))

	opp.set_follow_up_contact_date(contact_date)

	if action == "Schedule Follow Up":
		follow_up_date = getdate(follow_up_date)
		if follow_up_date < getdate():
			frappe.throw(_("Can't schedule a follow up for past dates"))

		opp.add_next_follow_up(follow_up_date, to_discuss=remarks)

		if opp.status == "Lost":
			opp.set_is_lost(False)

	out = frappe._dict()

	if action == "Mark As Lost":
		lost_reason_list = json.loads(lost_reason or "[]")
		opp.set_is_lost(True, lost_reasons_list=lost_reason_list, detailed_reason=remarks)

	elif action == "Mark As Closed":
		opp.set_status(status="Closed", update=True)

	opp.flags.ignore_mandatory = True
	opp.save()

	out.opportunity = opp.name

	if action == "Create Appointment":
		appointment_doc = make_appointment(opp.name)
		out['appointment_doc'] = appointment_doc

	submit_communication(opp, contact_date, remarks, update_follow_up=False)

	return out


@frappe.whitelist()
def submit_communication(opportunity, contact_date, remarks, update_follow_up=True):
	from frappe.model.document import Document

	if not remarks:
		frappe.throw(_('Remarks are mandatory for Communication'))

	remarks = clean_whitespace(remarks)

	if not opportunity:
		frappe.throw(_('Opportunity not provided'))

	if isinstance(opportunity, Document):
		opp = opportunity
	else:
		opp = frappe.get_doc("Opportunity", opportunity)

	comm = frappe.new_doc("Communication")
	comm.reference_doctype = opp.doctype
	comm.reference_name = opp.name
	comm.reference_owner = opp.owner

	comm.sender = frappe.session.user
	comm.sent_or_received = 'Received'
	comm.subject = "Opportunity Communication"
	comm.content = remarks
	comm.communication_type = "Feedback"

	comm.append("timeline_links", {
		"link_doctype": opp.opportunity_from,
		"link_name": opp.party_name,
	})

	comm.insert(ignore_permissions=True)

	if cint(update_follow_up):
		if opp.set_follow_up_contact_date(contact_date):
			opp.save()


@frappe.whitelist()
def get_events(start, end, filters=None):
	from frappe.desk.calendar import get_event_conditions
	conditions = get_event_conditions("Opportunity", filters)

	data = frappe.db.sql("""
		select
			`tabOpportunity`.name, `tabOpportunity`.customer_name, `tabOpportunity`.status,
			`tabLead Follow Up`.schedule_date
		from
			`tabOpportunity`
		inner join
			`tabLead Follow Up` on `tabOpportunity`.name = `tabLead Follow Up`.parent
		where
			ifnull(`tabLead Follow Up`.schedule_date, '0000-00-00') != '0000-00-00'
			and `tabLead Follow Up`.schedule_date between %(start)s and %(end)s
			and `tabLead Follow Up`.parenttype = 'Opportunity'
			{conditions}
		""".format(conditions=conditions), {
			"start": start,
			"end": end
		}, as_dict=True, update={"allDay": 1})

	return data


@frappe.whitelist()
def create_opportunity_from_communication(communication, ignore_communication_links=False):
	from crm.crm.doctype.lead.lead import make_lead_from_communication
	doc = frappe.get_doc("Communication", communication)

	lead = doc.reference_name if doc.reference_doctype == "Lead" else None
	if not lead:
		lead = make_lead_from_communication(communication, ignore_communication_links=True)

	opportunity_from = "Lead"

	opportunity = frappe.get_doc({
		"doctype": "Opportunity",
		"opportunity_from": opportunity_from,
		"party_name": lead
	}).insert(ignore_permissions=True)

	link_communication_to_document(doc, "Opportunity", opportunity.name, ignore_communication_links)

	return opportunity.name


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=10, seconds=60 * 60)
def make_opportunity_from_lead_form(
	sender,
	message="",
	subject="Website Query",
	full_name="",
	organization="",
	designation="",
	mobile_no="",
	phone_no="",
	country="",
	opportunity_args=None
):
	# Forward Email Message
	from frappe.www.contact import send_message as website_send_message

	if not sender:
		frappe.throw(_("Please enter your email address"))

	sender = validate_email_address(sender, throw=True)

	opportunity_args = json.loads(opportunity_args) if opportunity_args else {}

	forward_message_args = {
		"full_name": full_name,
		"organization": organization,
		"mobile_no": mobile_no,
		"phone_no": phone_no,
		"country": country,
	}

	for key, value in opportunity_args.items():
		if not forward_message_args.get(key):
			forward_message_args[key] = value

	website_send_message(sender=sender, subject=subject, message=message, args=forward_message_args,
		create_communication=False)

	default_lead_source = frappe.db.get_single_value("Contact Us Settings", "default_lead_source")

	# Create/Update Lead
	lead = frappe.db.get_value('Lead', {"email_id": sender})
	if not lead:
		new_lead = frappe.new_doc("Lead")
		new_lead.update({
			"email_id": sender,
			"lead_name": full_name or sender.split('@')[0].title(),
			"company_name": organization,
			"designation": designation,
			"phone": phone_no,
			"mobile_no": mobile_no,
			"source": default_lead_source,
		})

		if country:
			new_lead.country = country

		new_lead.flags.ignore_mandatory = True
		new_lead.insert(ignore_permissions=True)
		lead = new_lead.name
	else:
		old_lead = frappe.get_doc("Lead", lead)
		old_lead_changed = False
		if full_name:
			old_lead.lead_name = full_name or sender.split('@')[0].title()
			old_lead_changed = True
		if organization:
			old_lead.company_name = organization
			old_lead_changed = True
		if phone_no:
			old_lead.phone = phone_no
			old_lead_changed = True
		if designation:
			old_lead.designation = designation
			old_lead_changed = True

		# Set current number as primary and set old as secondary
		if mobile_no and old_lead.mobile_no and old_lead.mobile_no != mobile_no:
			old_lead.mobile_no_2 = old_lead.mobile_no
			old_lead.mobile_no = mobile_no
			old_lead_changed = True

		if old_lead_changed:
			old_lead.flags.ignore_mandatory = True
			old_lead.save(ignore_permissions=True)

	# Create Opportunity
	opportunity = frappe.new_doc("Opportunity")

	for k, v in opportunity_args.items():
		if opportunity.meta.has_field(k):
			opportunity.set(k, v)

	opportunity.update({
		"opportunity_from": 'Lead',
		"party_name": lead,
		"status": 'Open',
		"title": subject,
		"details": message,
		"contact_email": sender,
	})

	opportunity_type = get_opportunity_type_from_query_option(subject)
	if opportunity_type:
		opportunity.opportunity_type = opportunity_type

	opportunity.flags.ignore_mandatory = True
	opportunity.insert(ignore_permissions=True)

	# Create Communication
	comm = frappe.get_doc({
		"doctype": "Communication",
		"subject": subject,
		"content": message,
		"sender": sender,
		"sent_or_received": "Received",
		"reference_doctype": 'Opportunity',
		"reference_name": opportunity.name,
		"timeline_links": [
			{"link_doctype": opportunity.opportunity_from, "link_name": opportunity.party_name}
		]
	})
	comm.insert(ignore_permissions=True)

	return "okay"


def get_opportunity_type_from_query_option(option):
	option = cstr(option)
	if not option:
		return None

	contact_us_settings = frappe.get_cached_doc("Contact Us Settings", None)
	row = [d for d in contact_us_settings.query_options if d.option == option]

	if not row:
		return None

	return row[0].opportunity_type
