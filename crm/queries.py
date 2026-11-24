import frappe
from frappe.desk.reportview import get_filters_cond, get_match_cond
from frappe.utils import unique


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def lead_query(doctype, txt, searchfield, start, page_len, filters):
	fields = get_fields("Lead", ["name", "lead_name", "company_name"])

	searchfields = frappe.get_meta("Lead").get_search_fields()
	searchfields = " or ".join([field + " like %(txt)s" for field in searchfields])

	return frappe.db.sql("""
		select {fields}
		from `tabLead`
		where docstatus < 2
			and ({scond})
			{fcond} {mcond}
		order by
			if(locate(%(_txt)s, name), locate(%(_txt)s, name), 99999),
			if(locate(%(_txt)s, lead_name), locate(%(_txt)s, lead_name), 99999),
			if(locate(%(_txt)s, company_name), locate(%(_txt)s, company_name), 99999),
			modified desc,
			name, lead_name
		limit %(start)s, %(page_len)s""".format(**{
			"fields": ", ".join(fields),
			"scond": searchfields,
			"key": searchfield,
			"mcond": get_match_cond(doctype),
			"fcond": get_filters_cond(doctype, filters, []).replace("%", "%%"),
		}), {
			"txt": "%%%s%%" % txt,
			"_txt": txt.replace("%", ""),
			"start": start,
			"page_len": page_len,
		})


def get_fields(doctype, fields=None):
	if not fields:
		fields = []

	meta = frappe.get_meta(doctype)
	fields.extend(meta.get_search_fields())

	if meta.title_field and meta.title_field.strip() not in fields:
		fields.insert(1, meta.title_field.strip())

	return unique(fields)
