from . import __version__ as app_version

app_name = "crm"
app_title = "CRM"
app_publisher = "ParaLogic"
app_description = "ParaLogic CRM"
app_email = "info@paralogic.io"
app_license = "GNU General Public License (v3)"

app_include_js = "crm.bundle.js"
app_include_css = "crm.bundle.css"

web_include_js = "crm-web.bundle.js"

after_install = "crm.setup.install.after_install"
setup_wizard_stages = "crm.setup.setup_wizard.get_setup_stages"

boot_session = "crm.boot.boot_session"

doctype_js = {
	"Communication": "overrides/communication_hooks.js",
	"Event": "overrides/event_hooks.js",
}

doc_events = {
	"Contact": {
		"after_insert": "crm.communication.doctype.call_log.call_log.set_caller_information",
	},
	"Lead": {
		"after_insert": "crm.communication.doctype.call_log.call_log.set_caller_information"
	},
	"Email Unsubscribe": {
		"after_insert": "crm.crm.doctype.email_campaign.email_campaign.unsubscribe_recipient"
	}
}

fixtures = [
	{
		"doctype": "Custom Field",
		"filters": {
			"name": ["in", [
				"Contact Us Settings-default_lead_source",
				"Contact Query Option-opportunity_type",
				"Appointment Type-validate_duplicate_appointment"
			]]
		}
	},
]

scheduler_events = {
	"all": [
		"crm.crm.doctype.appointment.appointment.send_appointment_reminder_notifications",
	],
	"daily": [
		"crm.crm.doctype.opportunity.opportunity.auto_mark_opportunity_as_lost",
		"crm.crm.doctype.appointment.appointment.auto_mark_missed",
		"crm.crm.doctype.contract.contract.update_status_for_contracts",
		"crm.crm.doctype.email_campaign.email_campaign.send_email_to_leads_or_contacts",
		"crm.crm.doctype.email_campaign.email_campaign.set_email_campaign_status",
	]
}

standard_queries = {
	"Lead": "crm.queries.lead_query",
}

treeviews = ["Territory", "Sales Person"]

calendars = ["Appointment"]

default_mail_footer = ""

email_append_to = ["Lead", "Opportunity"]

sounds = [
	{"name": "incoming-call", "src": "/assets/crm/sounds/incoming-call.mp3", "volume": 0.2},
	{"name": "call-disconnect", "src": "/assets/crm/sounds/call-disconnect.mp3", "volume": 0.2},
]

user_data_fields = [
	{
		"doctype": "Lead",
		"match_field": "email_id",
		"personal_fields": [
			"lead_name",
			"phone", "mobile_no", "mobile_no_2", "fax", "website",
			"address_line1", "address_line2", "city", "state",
		],
	},
	{
		"doctype": "Opportunity",
		"match_field": 'contact_email',
		"personal_fields": [
			"customer_name", "contact_display",
			"contact_mobile", "contact_phone", "contact_phone",
			"address_display"
		],
	}
]

global_search_doctypes = {
	"Default": [
		{"doctype": "Lead", "index": 0},
		{"doctype": "Opportunity", "index": 1},
	]
}
