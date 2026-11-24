from frappe import _

from crm.setup.install_fixtures import create_default_records


def get_setup_stages(args=None):
	stages = [
		{
			"status": _("Installing CRM presets"),
			"fail_msg": _("Failed to install CRM presets"),
			"tasks": [
				{
					"fn": stage_fixtures,
					"args": args,
					"fail_msg": _("Failed to install presets"),
				},
			],
		},
	]

	return stages


def stage_fixtures(args):
	create_default_records(args.get("country"))
