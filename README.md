<div align="center">
	<h1>ParaLogic CRM</h1>
	<h3>Leads, opportunities, campaigns and appointments for the Frappe Framework</h3>
</div>

<div align="center">
	<a target="_blank" href="#license" title="License: GPL v3"><img src="https://img.shields.io/badge/License-GPLv3-success.svg"></a>
	<a target="_blank" href="https://www.python.org/downloads/" title="Python version"><img src="https://img.shields.io/badge/python-%3E=_3.11-success.svg"></a>
	<a href="https://github.com/ParaLogicTech/crm/actions/workflows/server-tests.yml"><img src="https://github.com/ParaLogicTech/crm/actions/workflows/server-tests.yml/badge.svg?branch=version-15"></a>
	<a href="https://github.com/ParaLogicTech/crm/actions/workflows/linters.yml"><img src="https://github.com/ParaLogicTech/crm/actions/workflows/linters.yml/badge.svg"></a>
</div>

> [!IMPORTANT]
> **This is not [Frappe CRM](https://github.com/frappe/crm).** Both apps are named `crm`, so they can't be installed
> on the same bench.

ParaLogic CRM is the CRM of ParaLogic's apps. It works on its own, as the CRM behind a website app, or under
ParaLogic's ERPNext fork, which builds on it.

## What's in it

- **CRM**: Lead (with follow-ups), Opportunity, the Territory and Sales Person trees, Campaigns and Email Campaigns,
  Appointments (time slots, reminders, missed-appointment marking), Contracts and Customer Feedback.
- **Communication**: Call Log with an incoming-call popup, Communication Medium and SMS Center.
- **Reports**: Lead Conversion Time, Lead Owner Efficiency, Campaign Efficiency, Lost Opportunity, Appointment
  Sheet, and more.
- **Setup**: the setup wizard creates default Lead Sources, Opportunity Types, Market Segments, Sales Stages,
  Industry Types, and the root Territory and Sales Person.

## Use with a website

crm loads `crm-web.bundle.js` on every website page, so a website app can send its forms to crm without its own
server code.

- **Lead form**: `crm.send_message(opts, btn)` posts to `crm.crm.doctype.opportunity.opportunity.make_opportunity_from_lead_form`,
  which guests can call (POST only, rate limited). Each submission:
  - forwards the message by email, like frappe's Contact Us page;
  - creates a Lead for the sender's email address, or fills in details an existing Lead is missing (it never
    overwrites them, since anyone can submit any address);
  - creates an open Opportunity for the Lead. Its Lead Source comes from `default_lead_source` in Contact Us
    Settings, and its Opportunity Type from the Contact Query Option matching the subject. crm adds both fields.
- **Extra Opportunity fields**: a form can send more fields in `opportunity_args`. Only fields listed in the
  `allowed_lead_form_opportunity_fields` hook are set. crm allows `source`, `campaign` and `information_source`;
  a website app can add its own in its `hooks.py`:

  ```python
  allowed_lead_form_opportunity_fields = ["lead_classification"]
  ```
- **Newsletter**: `crm.subscribe_to_newsletter(opts, btn)` and `crm.bind_newsletter_subscription($input, $button, opts)`
  subscribe an email address through frappe's newsletter.

The arguments each function takes are documented in [website_utils.js](crm/public/js/website_utils.js).

## With and without ERPNext

crm sits between the framework and ERP: ParaLogic's [frappe fork](https://github.com/ParaLogicTech/frappe) → crm →
ParaLogic's [ERPNext fork](https://github.com/ParaLogicTech/erpnext). It installs and runs without ERPNext, and CI
tests it that way.

A few features still use ERPNext DocTypes and are unavailable without it: the incoming-call popup (its recipients are
Employees), SMS Center's Customer, Supplier, Sales Partner and Employee receivers, and the Appointment Sheet report.
Moving them onto crm's own DocTypes is planned.

## Installation

crm requires [ParaLogic's frappe fork](https://github.com/ParaLogicTech/frappe); it won't run on stock Frappe.
Create a bench from the fork as described in its README, then:

```bash
bench get-app https://github.com/ParaLogicTech/crm --branch version-15
bench --site <site> install-app crm
```

Python 3.11+. `version-15` is the only maintained branch.

## Origin

crm was split out of ERPNext v15 in 2023: the CRM module, Territory and Sales Person moved here so they can be used
without ERP. That code was written by [Frappe Technologies](https://frappe.io) and the ERPNext contributors; ParaLogic
has developed it further since. Stock ERPNext's CRM documentation describes where it started, not how it works now.

## Reporting issues

- **Bugs**: open an issue on [ParaLogicTech/crm](https://github.com/ParaLogicTech/crm/issues).
- **Security issues**: don't open a public issue. Report them privately through
  [GitHub's private vulnerability reporting](https://github.com/ParaLogicTech/crm/security/advisories/new).
  See [SECURITY.md](SECURITY.md).

## Contributing

1. Branch from `version-15` and open a pull request against `version-15` on this repository.
2. Run `pre-commit install` once in your checkout. ruff and ESLint fix what they can and keep the layout you write;
   there is no formatter.
3. Add or update tests: the test suite is maintained and must pass in CI. Run it on a site with frappe and crm
   installed: `bench --site <site> run-tests --app crm`.
4. A pull request that needs an unmerged frappe change names it in its description, on a line of its own:
   "Depends on" followed by the frappe pull request (`ParaLogicTech/frappe` and its number, joined by `#`). CI then
   tests against that branch.
5. Commit messages follow [Conventional Commits](https://www.conventionalcommits.org) (`fix: …`, `feat: …`).

## License

GNU General Public License v3, see [license.txt](license.txt). Code that came from ERPNext keeps its copyright with
Frappe Technologies Pvt. Ltd. and its contributors.
