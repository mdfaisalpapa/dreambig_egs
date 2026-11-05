# Copyright (c) 2026, Mohammed Faisal and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	"""
	Execute Script Report: EGS Action Dashboard.
	Returns columns and data for Open Escalation Tickets joined with Student Participants.
	"""
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"label": _("Ticket ID"),
			"fieldname": "ticket_id",
			"fieldtype": "Link",
			"options": "EGS Escalation Ticket",
			"width": 160,
		},
		{
			"label": _("Student Name"),
			"fieldname": "student_name",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("University/College"),
			"fieldname": "university_college",
			"fieldtype": "Link",
			"options": "EGS Institution",
			"width": 200,
		},
		{
			"label": _("Escalation Route"),
			"fieldname": "escalation_route",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": _("Assigned Coordinator"),
			"fieldname": "assigned_coordinator",
			"fieldtype": "Link",
			"options": "EGS Coordinator",
			"width": 180,
		},
	]


def get_data(filters):
	conditions = ["ticket.status = 'Open'"]
	values = {}

	if filters.get("university_college"):
		conditions.append("student.university_college = %(university_college)s")
		values["university_college"] = filters["university_college"]

	if filters.get("escalation_route"):
		conditions.append("ticket.escalation_route = %(escalation_route)s")
		values["escalation_route"] = filters["escalation_route"]

	where_clause = " AND ".join(conditions)

	query = f"""
		SELECT
			ticket.name AS ticket_id,
			student.student_name AS student_name,
			student.university_college AS university_college,
			ticket.escalation_route AS escalation_route,
			ticket.assigned_coordinator AS assigned_coordinator
		FROM
			`tabEGS Escalation Ticket` ticket
		INNER JOIN
			`tabEGS Student Participant` student
		ON
			ticket.student_reference = student.name
		WHERE
			{where_clause}
		ORDER BY
			ticket.creation DESC
	"""

	return frappe.db.sql(query, values, as_dict=True)
