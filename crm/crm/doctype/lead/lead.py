# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.utils import validate_email_address, cint, cstr, comma_and, has_gravatar, clean_whitespace
from frappe.model.mapper import get_mapped_doc
from frappe.utils.status_updater import StatusUpdater
from frappe.contacts.address_and_contact import load_address_and_contact
from frappe.email.inbox import link_communication_to_document

sender_field = "email_id"


class Lead(StatusUpdater):
	def __init__(self, *args, **kwargs):
		super(Lead, self).__init__(*args, **kwargs)
		self.status_map = [
			["Lost Opportunity", "is_lost_opportunity"],
			["Opportunity", "is_opportunity"],
			["Converted", "is_converted"],
		]

	def get_feed(self):
		return '{0}: {1}'.format(_(self.status), self.lead_name)

	def onload(self):
		load_address_and_contact(self)

	def validate(self):
		self.validate_lead_name()
		self.validate_organization_lead()
		self.validate_email_address()
		self.validate_mobile_no()
		self.validate_tax_id()
		# self.check_email_id_is_unique()
		self.set_gravatar()
		self.set_status()

	def validate_lead_name(self):
		self.lead_name = clean_whitespace(self.lead_name)
		self.company_name = clean_whitespace(self.company_name)

		if not self.lead_name:
			# Check for leads being created through data import
			if not self.company_name and not self.flags.ignore_mandatory:
				frappe.throw(_("A Lead requires either a person's name or an organization's name"))

			self.lead_name = self.company_name

	def validate_organization_lead(self):
		if cint(self.organization_lead):
			self.lead_name = self.company_name
			self.gender = None
			self.salutation = None

	def validate_email_address(self):
		self.email_id = cstr(self.email_id).strip()
		if self.email_id:
			if not self.flags.ignore_email_validation:
				validate_email_address(self.email_id, True)

	def validate_mobile_no(self):
		from frappe.regional.regional import validate_mobile_no
		if self.get('mobile_no_2') and not self.get('mobile_no'):
			self.mobile_no = self.mobile_no_2
			self.mobile_no_2 = ""

		validate_mobile_no(self.get('mobile_no'))
		validate_mobile_no(self.get('mobile_no_2'))

	def validate_tax_id(self):
		from frappe.regional.regional import validate_tax_ids
		validate_tax_ids(self.get('tax_id'), self.get('tax_cnic'), self.get('tax_strn'))

	def check_email_id_is_unique(self):
		if self.email_id:
			# validate email is unique
			duplicate_leads = frappe.db.sql_list("""
				select name
				from `tabLead`
				where email_id = %s and name != %s
			""", (self.email_id, self.name))

			if duplicate_leads:
				frappe.throw(_("Email Address must be unique, Lead already exists for {0}")
					.format(comma_and(duplicate_leads)), frappe.DuplicateEntryError)

	def set_gravatar(self):
		if self.email_id:
			if self.is_new() or not self.image:
				self.image = has_gravatar(self.email_id)

	def is_opportunity(self):
		return self.has_opportunity()

	def has_opportunity(self):
		if self.is_new():
			return False

		return frappe.db.get_value("Opportunity", {
			"opportunity_from": "Lead", "party_name": self.name, "status": ["!=", "Lost"]
		})

	def is_lost_opportunity(self):
		return self.has_lost_opportunity()

	def has_lost_opportunity(self):
		if self.is_new():
			return False

		return frappe.db.get_value("Opportunity", {
			"opportunity_from": "Lead", "party_name": self.name, "status": ["=", "Lost"]
		})

	def is_converted(self):
		return self.has_converted_opportunity()

	def has_converted_opportunity(self):
		if self.is_new():
			return False

		return frappe.db.get_value("Opportunity", {
			"opportunity_from": "Lead", "party_name": self.name, "status": ["=", "Converted"]
		})


@frappe.whitelist()
def make_opportunity(source_name, target_doc=None):
	def set_missing_values(source, target):
		target.opportunity_from = 'Lead'
		target.run_method("set_missing_values")

	target_doc = get_mapped_doc("Lead", source_name, {
		"Lead": {
			"doctype": "Opportunity",
			"field_map": {
				"name": "party_name",
			}
		}
	}, target_doc, set_missing_values)

	return target_doc


@frappe.whitelist()
def get_lead_contact_details(lead):
	if not lead:
		return frappe._dict()

	return _get_lead_contact_details(lead, check_permissions=True)


def _get_lead_contact_details(lead, check_permissions=False):
	if isinstance(lead, str):
		lead = frappe.get_doc("Lead", lead)
		if check_permissions:
			lead.check_permissions()

	out = frappe._dict({
		"contact_email": lead.get('email_id'),
		"contact_mobile": lead.get('mobile_no'),
		"contact_mobile_2": lead.get('mobile_no_2'),
		"contact_phone": lead.get('phone'),
	})

	if cint(lead.organization_lead):
		out["contact_display"] = ""
		out["contact_designation"] = ""
	else:
		out["contact_display"] = " ".join(filter(None, [lead.get("salutation"), lead.get("lead_name")]))
		out["contact_designation"] = lead.get('designation')

	return out


def get_lead_address_details(lead, check_permissions=False):
	if not lead:
		lead = frappe._dict()

	if isinstance(lead, str):
		lead = frappe.get_doc("Lead", lead)
		if check_permissions:
			lead.check_permissions()

	lead_address_fields = ['address_line1', 'address_line2', 'city', 'state', 'country']
	lead_address_details = frappe._dict()
	for f in lead_address_fields:
		lead_address_details[f] = lead.get(f)

	if not lead_address_details.get('address_line1'):
		lead_address_details = frappe._dict()

	return lead_address_details


@frappe.whitelist()
def make_lead_from_communication(communication, ignore_communication_links=False):
	""" raise a issue from email """

	doc = frappe.get_doc("Communication", communication)
	lead_name = None
	if doc.sender:
		lead_name = frappe.db.get_value("Lead", {"email_id": doc.sender})
	if not lead_name and doc.phone_no:
		lead_name = frappe.db.get_value("Lead", {"mobile_no": doc.phone_no})
	if not lead_name:
		lead = frappe.get_doc({
			"doctype": "Lead",
			"lead_name": doc.sender_full_name,
			"email_id": doc.sender,
			"mobile_no": doc.phone_no
		})
		lead.flags.ignore_mandatory = True
		lead.flags.ignore_permissions = True
		lead.insert()

		lead_name = lead.name

	link_communication_to_document(doc, "Lead", lead_name, ignore_communication_links)
	return lead_name


def get_lead_with_phone_number(number):
	if not number: return

	leads = frappe.get_all('Lead', or_filters={
		'phone': ['like', '%{}'.format(number)],
		'mobile_no': ['like', '%{}'.format(number)]
	}, limit=1)

	lead = leads[0].name if leads else None

	return lead
