import frappe
from frappe.tests.utils import FrappeTestCase


class CRMTestCase(FrappeTestCase):
	"""Rolls back each test's changes, not just each class's, so tests don't see each other's records"""

	def setUp(self):
		super().setUp()
		frappe.db.savepoint("crm_test")
		self.addCleanup(self.rollback_test_changes)

	def rollback_test_changes(self):
		frappe.db.rollback(save_point="crm_test")
		frappe.db.value_cache = {}

	def set_default_country(self, country):
		"""Sets the site's country (used for regional validations and phone number formats) for this test"""
		previous_country = frappe.db.get_default("country")
		frappe.db.set_default("country", country)
		self.addCleanup(frappe.db.set_default, "country", previous_country)
