# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils.nestedset import NestedSet, get_root_of


class Territory(NestedSet):
	nsm_parent_field = 'parent_territory'

	def validate(self):
		if not self.parent_territory:
			self.parent_territory = get_root_of("Territory")

	def on_update(self):
		super().on_update()
		self.validate_one_root()


def get_territory_subtree(territory, cache=True):
	def generator():
		return frappe.get_all("Territory", filters={"name": ["subtree of", territory]}, pluck="name")

	if cache:
		return frappe.local_cache("get_territory_subtree", territory, generator)
	else:
		return generator()


def on_doctype_update():
	frappe.db.add_index("Territory", ["lft", "rgt"])
