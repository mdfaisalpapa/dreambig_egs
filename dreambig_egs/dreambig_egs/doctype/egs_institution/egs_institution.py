# Copyright (c) 2026, Dream Big and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.model.document import Document
from frappe.utils import cint


class EGSInstitution(Document):
	pass


@frappe.whitelist(allow_guest=True)
def get_institutions_by_city(
	doctype=None,
	txt="",
	searchfield="name",
	start=0,
	page_len=50,
	filters=None,
	city=None,
	**kwargs,
):
	"""Return institutions strictly filtered by city.

	Compatible with:
	- Web Form Autocomplete dynamic filtering via RPC
	- Web Form Autocomplete execute_query_if_exists (args: {txt, city})
	- Desk / Link field custom query (doctype, txt, searchfield, start, page_len, filters)
	- Direct function calls with city or filters kwargs
	"""
	if isinstance(filters, str):
		try:
			filters = json.loads(filters)
		except Exception:
			filters = {}

	target_city = city
	if not target_city and isinstance(filters, dict):
		target_city = filters.get("city")
	if not target_city and kwargs.get("city"):
		target_city = kwargs.get("city")

	db_filters = {}
	if target_city:
		db_filters["city"] = target_city
	else:
		# If no city is specified, return empty list to enforce city selection
		return []

	txt = (txt or "").strip()
	if txt:
		db_filters["name"] = ["like", f"%{txt}%"]

	institutions = frappe.get_all(
		"EGS Institution",
		filters=db_filters,
		fields=["name", "city"],
		order_by="name asc",
		limit_start=cint(start) if start else 0,
		limit_page_length=cint(page_len) if page_len else 50,
		ignore_permissions=True,
	)

	return [{"value": row["name"], "label": row["name"]} for row in institutions]
