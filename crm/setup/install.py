import frappe

from crm.setup.install_fixtures import create_default_records


def after_install():
	# install fixtures from installer rather than setup wizard if setup is already completed
	if frappe.db.get_single_value("System Settings", "setup_complete"):
		create_default_records(frappe.db.get_single_value("System Settings", "country"))


def before_tests():
	from frappe.utils.install import complete_setup_wizard

	frappe.clear_cache()

	# completing the setup wizard also runs crm's setup stage, which creates the default records
	if not frappe.is_setup_complete():
		complete_setup_wizard()

	create_default_records(frappe.db.get_single_value("System Settings", "country"))
	frappe.db.commit()
