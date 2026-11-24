# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils.nestedset import NestedSetChildExistsError

from crm.crm.doctype.territory.territory import get_territory_subtree
from crm.tests.utils import CRMTestCase

test_records = frappe.get_test_records("Territory")

test_ignore = ["Item Group"]


class TestTerritory(CRMTestCase):
	def test_parent_defaults_to_root(self):
		territory = make_territory(parent_territory=None)
		self.assertEqual(territory.parent_territory, "All Territories")

	def test_tree_position(self):
		region = make_territory(is_group=1)
		city = make_territory(parent_territory=region.name)
		region.reload()

		self.assertTrue(region.lft < city.lft < city.rgt < region.rgt)

	def test_territory_subtree(self):
		region = make_territory(is_group=1)
		district = make_territory(parent_territory=region.name, is_group=1)
		city = make_territory(parent_territory=district.name)
		other = make_territory()

		subtree = get_territory_subtree(region.name, cache=False)
		self.assertCountEqual(subtree, [region.name, district.name, city.name])
		self.assertNotIn(other.name, subtree)

		self.assertEqual(get_territory_subtree(city.name, cache=False), [city.name])

	def test_territory_subtree_is_cached(self):
		region = make_territory(is_group=1)
		self.assertEqual(get_territory_subtree(region.name), [region.name])

		city = make_territory(parent_territory=region.name)
		self.assertEqual(get_territory_subtree(region.name), [region.name])
		self.assertCountEqual(get_territory_subtree(region.name, cache=False), [region.name, city.name])

	def test_cannot_delete_territory_with_children(self):
		region = make_territory(is_group=1)
		make_territory(parent_territory=region.name)

		self.assertRaises(NestedSetChildExistsError, frappe.delete_doc, "Territory", region.name)


def make_territory(**kwargs):
	territory = frappe.get_doc(
		{
			"doctype": "Territory",
			"territory_name": "_Test Territory " + frappe.generate_hash(length=8),
			"parent_territory": "All Territories",
		},
	)
	territory.update(kwargs)
	territory.insert()
	return territory
