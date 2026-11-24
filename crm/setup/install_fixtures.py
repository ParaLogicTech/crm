import frappe
from frappe import _

lead_sources = [
	"Existing Customer",
	"Reference",
	"Advertisement",
	"Cold Calling",
	"Exhibition",
	"Mass Mailing",
	"Customer's Vendor",
	"Campaign",
	"Walk In",
]

opportunity_types = [
	"Sales",
	"Support",
]

market_segments = [
	"Lower Income",
	"Middle Income",
	"Upper Income",
]

sales_stages = [
	"Prospecting",
	"Qualification",
	"Needs Analysis",
	"Value Proposition",
	"Identifying Decision Makers",
	"Perception Analysis",
	"Proposal/Price Quote",
	"Negotiation/Review",
]

industry_types = [
	"Accounting",
	"Advertising",
	"Aerospace",
	"Agriculture",
	"Airline",
	"Apparel & Accessories",
	"Automotive",
	"Banking",
	"Biotechnology",
	"Broadcasting",
	"Brokerage",
	"Chemical",
	"Computer",
	"Consulting",
	"Consumer Products",
	"Cosmetics",
	"Defense",
	"Department Stores",
	"Education",
	"Electronics",
	"Energy",
	"Entertainment & Leisure",
	"Executive Search",
	"Financial Services",
	"Food, Beverage & Tobacco",
	"Grocery",
	"Health Care",
	"Internet Publishing",
	"Investment Banking",
	"Legal",
	"Manufacturing",
	"Motion Picture & Video",
	"Music",
	"Newspaper Publishers",
	"Online Auctions",
	"Pension Funds",
	"Pharmaceuticals",
	"Private Equity",
	"Publishing",
	"Real Estate",
	"Retail & Wholesale",
	"Securities & Commodity Exchanges",
	"Service",
	"Soap & Detergent",
	"Software",
	"Sports",
	"Technology",
	"Telecommunications",
	"Television",
	"Transportation",
	"Venture Capital",
]


def get_default_records(country):
	return {
		"Lead Source": [{"doctype": "Lead Source", "source_name": _(d)} for d in lead_sources],
		"Opportunity Type": [{"doctype": "Opportunity Type", "name": _(d)} for d in opportunity_types],
		"Market Segment": [{"doctype": "Market Segment", "market_segment": _(d)} for d in market_segments],
		"Sales Stage": [{"doctype": "Sales Stage", "stage_name": _(d)} for d in sales_stages],
		"Industry Type": [{"doctype": "Industry Type", "industry": _(d)} for d in industry_types],
		"Sales Person": [
			{"doctype": "Sales Person", "sales_person_name": _("Sales Team"), "is_group": 1, "parent_sales_person": ""},
		],
		"Territory": [
			{"doctype": "Territory", "territory_name": _("All Territories"), "is_group": 1,
				"name": _("All Territories"), "parent_territory": ""},
			{"doctype": "Territory", "territory_name": country.replace("'", ""), "is_group": 0,
				"parent_territory": _("All Territories")},
			{"doctype": "Territory", "territory_name": _("Rest Of The World"), "is_group": 0,
				"parent_territory": _("All Territories")},
		],
	}


def create_default_records(country):
	data = get_default_records(country)

	for doctype, records in data.items():
		if frappe.db.count(doctype):
			continue

		for d in records:
			doc = frappe.get_doc(d)
			doc.insert(ignore_permissions=True, ignore_if_duplicate=True)
