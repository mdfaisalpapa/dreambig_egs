import json
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today


class EGSEvent(Document):
	def validate(self):
		if self.registration_deadline and self.event_date:
			reg_str = str(self.registration_deadline)[:10]
			evt_str = str(self.event_date)[:10]
			if reg_str > evt_str:
				frappe.throw(_("Registration deadline cannot be after the event date."))


def format_event_date(dt):
	if not dt:
		return ""
	if hasattr(dt, "strftime"):
		return dt.strftime("%d %b %Y, %I:%M %p")
	try:
		from datetime import datetime
		dt_str = str(dt)[:19]
		if len(dt_str) == 10:
			dt_obj = datetime.strptime(dt_str, "%Y-%m-%d")
			return dt_obj.strftime("%d %b %Y")
		else:
			dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
			return dt_obj.strftime("%d %b %Y, %I:%M %p")
	except Exception:
		return str(dt)


@frappe.whitelist(allow_guest=True)
def get_open_events_by_city(
	doctype=None,
	txt="",
	searchfield="name",
	start=0,
	page_len=50,
	filters=None,
	city=None,
	**kwargs,
):
	"""Return open events strictly filtered by city and status='Open for Registration'.

	Compatible with:
	- Web Form Autocomplete dynamic filtering via RPC
	- Web Form Autocomplete execute_query_if_exists (args: {txt, city})
	- Desk / Link field custom query (doctype, txt, searchfield, start, page_len, filters)
	- Direct function calls with city or filters kwargs

	Irrespective of the student's chosen institution, any student can register
	for active events in their selected city.
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

	db_filters = {
		"status": "Open for Registration"
	}
	if target_city:
		db_filters["city"] = target_city

	today_date = today()

	events = frappe.get_all(
		"EGS Event",
		filters=db_filters,
		fields=[
			"name",
			"event_name",
			"event_date",
			"registration_deadline",
			"venue",
			"city",
			"allow_digital_checkins",
			"allow_digital_food_coupons",
		],
		order_by="event_date asc",
		ignore_permissions=True,
	)

	txt = (txt or "").strip().lower()
	valid_events = []
	for e in events:
		# Check deadline >= today if set
		if e.registration_deadline and str(e.registration_deadline)[:10] < today_date:
			continue

		label = e.event_name if e.event_name else e.name
		if e.event_name and e.event_name != e.name:
			label = f"{e.event_name} ({e.name})"

		formatted_dt = format_event_date(e.event_date)
		venue_str = e.venue or ""

		# Compose human-readable description for dropdown display
		desc_parts = []
		if formatted_dt:
			desc_parts.append(f"📅 {formatted_dt}")
		if venue_str:
			desc_parts.append(f"📍 {venue_str}")
		description = "  •  ".join(desc_parts)

		# Text filter if user typed in autocomplete (matches name, label, date, or venue)
		searchable = f"{e.name} {label} {formatted_dt} {venue_str}".lower()
		if txt and txt not in searchable:
			continue

		valid_events.append(frappe._dict({
			"value": e.name,
			"label": label,
			"description": description,
			"name": e.name,
			"event_name": e.event_name or e.name,
			"event_date": str(e.event_date) if e.event_date else "",
			"formatted_date": formatted_dt,
			"venue": venue_str,
			"city": e.city or "",
			"allow_digital_checkins": e.allow_digital_checkins,
			"allow_digital_food_coupons": e.allow_digital_food_coupons,
		}))

	return valid_events


@frappe.whitelist(allow_guest=True)
def get_events_query(
	doctype=None,
	txt="",
	searchfield="name",
	start=0,
	page_len=50,
	filters=None,
	city=None,
	**kwargs,
):
	"""Link field and Web Form autocomplete query handler.

	Strictly filters EGS Event by city and status='Open for Registration'.
	"""
	events = get_open_events_by_city(
		doctype=doctype,
		txt=txt,
		searchfield=searchfield,
		start=start,
		page_len=page_len,
		filters=filters,
		city=city,
		**kwargs,
	)

	# If invoked by Desk search_link (where doctype is provided and tuples are expected by build_for_autosuggest)
	as_dict = kwargs.get("as_dict")
	req_path = getattr(frappe.request, "path", "") if hasattr(frappe, "request") and frappe.request else ""
	if doctype and not as_dict and "search_link" in req_path:
		return [(e["value"], e["label"], e["description"] or e["venue"]) for e in events]

	return events
