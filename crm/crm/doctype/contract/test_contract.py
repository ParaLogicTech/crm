# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.utils import add_days, nowdate

from crm.crm.doctype.contract.contract import update_status_for_contracts
from crm.crm.doctype.lead.test_lead import make_lead
from crm.tests.utils import CRMTestCase


class TestContract(CRMTestCase):
	def test_end_date_before_start_date(self):
		contract = get_contract(start_date=nowdate(), end_date=add_days(nowdate(), -1))
		self.assertRaises(frappe.ValidationError, contract.insert)

	def test_end_date_without_start_date(self):
		contract = make_contract(end_date=add_days(nowdate(), 10))
		self.assertEqual(contract.status, "Unsigned")

	def test_unsigned_contract_status(self):
		contract = make_contract(start_date=add_days(nowdate(), -1), end_date=add_days(nowdate(), 1))
		self.assertEqual(contract.status, "Unsigned")

	def test_active_signed_contract_status(self):
		contract = make_contract(
			is_signed=1, start_date=add_days(nowdate(), -1), end_date=add_days(nowdate(), 1)
		)
		self.assertEqual(contract.status, "Active")

	def test_signed_contract_without_end_date_is_active(self):
		contract = make_contract(is_signed=1, start_date=add_days(nowdate(), -30))
		self.assertEqual(contract.status, "Active")

	def test_past_inactive_signed_contract_status(self):
		contract = make_contract(
			is_signed=1, start_date=add_days(nowdate(), -2), end_date=add_days(nowdate(), -1)
		)
		self.assertEqual(contract.status, "Inactive")

	def test_future_inactive_signed_contract_status(self):
		contract = make_contract(
			is_signed=1, start_date=add_days(nowdate(), 1), end_date=add_days(nowdate(), 2)
		)
		self.assertEqual(contract.status, "Inactive")

	def test_contract_without_fulfilment(self):
		contract = make_contract()
		self.assertEqual(contract.fulfilment_status, "N/A")

	def test_contract_with_no_fulfilment_terms(self):
		contract = make_contract(requires_fulfilment=1)
		self.assertEqual(contract.fulfilment_status, "Unfulfilled")

	def test_unfulfilled_contract_status(self):
		contract = make_contract(requires_fulfilment=1, fulfilment_terms=get_fulfilment_terms(0, 0))
		self.assertEqual(contract.fulfilment_status, "Unfulfilled")

	def test_partially_fulfilled_contract_status(self):
		contract = make_contract(requires_fulfilment=1, fulfilment_terms=get_fulfilment_terms(1, 0))
		self.assertEqual(contract.fulfilment_status, "Partially Fulfilled")

	def test_fulfilled_contract_status(self):
		contract = make_contract(requires_fulfilment=1, fulfilment_terms=get_fulfilment_terms(1, 1))
		self.assertEqual(contract.fulfilment_status, "Fulfilled")

	def test_lapsed_contract_status(self):
		contract = make_contract(
			requires_fulfilment=1,
			fulfilment_deadline=add_days(nowdate(), -1),
			fulfilment_terms=get_fulfilment_terms(1, 0),
		)
		self.assertEqual(contract.fulfilment_status, "Lapsed")

	def test_fulfilled_contract_after_deadline_is_not_lapsed(self):
		contract = make_contract(
			requires_fulfilment=1,
			fulfilment_deadline=add_days(nowdate(), -1),
			fulfilment_terms=get_fulfilment_terms(1, 1),
		)
		self.assertEqual(contract.fulfilment_status, "Fulfilled")

	def test_fulfilment_status_updates_after_submit(self):
		contract = make_contract(requires_fulfilment=1, fulfilment_terms=get_fulfilment_terms(0, 0))
		contract.submit()

		contract.fulfilment_terms[0].fulfilled = 1
		contract.save()
		self.assertEqual(contract.fulfilment_status, "Partially Fulfilled")

		contract.fulfilment_terms[1].fulfilled = 1
		contract.save()
		self.assertEqual(contract.fulfilment_status, "Fulfilled")

	def test_signing_after_submit_updates_status(self):
		contract = make_contract(start_date=add_days(nowdate(), -1))
		contract.submit()
		self.assertEqual(contract.status, "Unsigned")

		contract.is_signed = 1
		contract.save()
		self.assertEqual(contract.status, "Active")

	def test_naming(self):
		lead = make_lead()
		template = make_contract_template()

		first = make_contract(party_name=lead.name)
		second = make_contract(party_name=lead.name)
		with_template = make_contract(party_name=lead.name, contract_template=template.name)

		self.assertEqual(first.name, lead.name)
		self.assertEqual(second.name, f"{lead.name} - 1")
		self.assertEqual(with_template.name, f"{lead.name} - {template.name} Agreement")

	def test_update_status_for_contracts(self):
		contract = make_contract(
			is_signed=1, start_date=add_days(nowdate(), -10), end_date=add_days(nowdate(), 10)
		)
		contract.submit()
		self.assertEqual(contract.status, "Active")

		# Simulate the contract period ending
		contract.db_set("end_date", add_days(nowdate(), -1))
		update_status_for_contracts()
		self.assertEqual(frappe.db.get_value("Contract", contract.name, "status"), "Inactive")


def get_contract(**kwargs):
	contract = frappe.new_doc("Contract")
	contract.party_type = "Lead"
	contract.contract_terms = "This is a test contract."
	contract.update(kwargs)

	if not contract.party_name:
		contract.party_name = make_lead().name

	return contract


def make_contract(**kwargs):
	contract = get_contract(**kwargs)
	contract.insert()
	return contract


def get_fulfilment_terms(*fulfilled):
	return [
		{"requirement": f"Test requirement {i}", "fulfilled": is_fulfilled}
		for i, is_fulfilled in enumerate(fulfilled, 1)
	]


def make_contract_template():
	return frappe.get_doc(
		{
			"doctype": "Contract Template",
			"title": "_Test Contract Template " + frappe.generate_hash(length=8),
			"contract_terms": "Template terms",
		}
	).insert()
