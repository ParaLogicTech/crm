# Agent instructions

This repository is **ParaLogic CRM**, a Frappe app split out of ERPNext v15. It is **not Frappe CRM**
(frappe/crm), and it is no longer stock ERPNext's CRM module. Documentation for either one, and your own knowledge
of them, doesn't describe this app: read the code in this repository.

It runs on [ParaLogic's frappe fork](https://github.com/ParaLogicTech/frappe), not stock Frappe. That fork's
FORK.md lists how it differs from upstream Frappe.

## Where it sits

frappe fork → **crm** → ParaLogic's ERPNext fork → product and client apps. Dependencies point downward:

- crm must not import from, or refer to, erpnext or any app above it. ERP behaviour belongs in erpnext, which
  extends crm through hooks.
- Some features still use ERPNext DocTypes (Employee, Customer, Supplier, …). They're behind guards that skip them
  when ERPNext isn't installed, or are only Link fields. Don't add new ones: new code works without ERPNext.

## Website API

`make_opportunity_from_lead_form` (guest, POST) and the `crm.*` functions in `crm/public/js/website_utils.js` are
called by website apps. Keep their arguments and behaviour backward compatible. Guests can send any value, so a new
field they may set goes through the `allowed_lead_form_opportunity_fields` hook, never straight from the request.

## Rules for changes

- **Branch** from `version-15` and target `version-15` in pull requests.
- **Style**: tabs, double quotes. ruff `check --fix` and ESLint (with ESLint Stylistic) fix code but don't reformat
  it, so line breaks are the author's choice (aim for 120 characters). Hug brackets, put `and`/`or` at the start of
  a continued line, and add a trailing comma after the last item of a multi-line call, list or dict.
- **Tests**: the test suite is maintained and CI must pass. Add or update tests for every change, and run them with
  `bench --site <test-site> run-tests --app crm` on a site with only frappe and crm installed.
- **Cross-repo changes**: a pull request that needs an unmerged frappe change names that pull request in its
  description on a "Depends on" line; CI tests against its branch.
- **Whitelisted methods**: new or changed ones get type hints that match what callers send (frappe validates them).
- **Patches** go in `crm/patches.txt` and must be idempotent. Keep old patches.
- **DocType changes**: save through the Desk or `bench console` in developer mode, which exports the JSON. Don't
  hand-edit DocType JSON.
- **Commit messages** follow Conventional Commits (`fix: …`, `feat: …`, `docs: …`), one subject line.
- **No customer details**: don't name clients or quote client data in code, comments, commits or pull requests.
  Describe cases generically.
