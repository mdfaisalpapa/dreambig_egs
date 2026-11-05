# Copyright (c) 2026, Mohammed Faisal and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, now_datetime


class EGSCheckInLog(Document):
	def before_insert(self):
		"""Set default values if submitted from Web Form."""
		if not self.timestamp:
			self.timestamp = now_datetime()
		if not self.check_in_round:
			last_round = (
				frappe.db.get_value(
					"EGS Check-in Log",
					{"student_reference": self.student_reference},
					"check_in_round",
					order_by="check_in_round desc",
				)
				or 0
			)
			self.check_in_round = last_round + 1

	def after_insert(self):
		"""Controller method triggered after document insertion."""
		handle_after_insert(self)


def after_insert(doc, method=None):
	"""
	Hook function callable via Frappe doc_events.
	Delegates to handle_after_insert.
	"""
	handle_after_insert(doc)


def handle_after_insert(doc):
	"""
	Handles logic when an EGS Check-in Log is inserted:
	1. If student_response is 'I need help', sets triage_route to 'Stuck'
	   and persists via doc.db_update().
	2. Creates an EGS Escalation Ticket (and a ToDo) assigned to the Teacher-Mentor
	   (Designated Anchor) linked to the student's university_college.
	"""
	# Idempotency guard to prevent duplicate executions if both controller method
	# and doc_events hook trigger
	if getattr(doc.flags, "_after_insert_processed", False):
		return
	doc.flags._after_insert_processed = True

	if doc.student_response == "I need help":
		# Set the triage_route field on the current log to 'Stuck' and call .db_update()
		doc.triage_route = "Stuck"
		doc.db_update()

		# Retrieve the student record and linked university_college
		student = frappe.db.get_value(
			"EGS Student Participant",
			doc.student_reference,
			["student_name", "university_college", "phone_number"],
			as_dict=True,
		)

		university_college = student.get("university_college") if student else None
		designated_anchor = None
		if university_college:
			# Designated Teacher-Mentor (Anchor) linked in EGS Institution
			designated_anchor = frappe.db.get_value(
				"EGS Institution",
				university_college,
				"designated_anchor",
			)

		# Check for a coordinator linked to the institution
		coordinator = None
		if university_college:
			coordinator = frappe.db.get_value(
				"EGS Coordinator",
				{"institution": university_college},
				["name", "full_name", "erpnext_user", "email"],
				as_dict=True,
			)

		resolution_notes = (
			f"Student {student.get('student_name', doc.student_reference)} requested help "
			f"during check-in round {doc.check_in_round}."
		)
		if designated_anchor:
			resolution_notes += f" Assigned Teacher-Mentor (Anchor): {designated_anchor}."

		# Create custom EGS Escalation Ticket using frappe.get_doc
		escalation_ticket = frappe.get_doc(
			{
				"doctype": "EGS Escalation Ticket",
				"student_reference": doc.student_reference,
				"triggering_check_in": doc.name,
				"escalation_route": "Stuck",
				"assigned_coordinator": coordinator.get("name") if coordinator else None,
				"status": "Open",
				"resolution_notes": resolution_notes,
			}
		)
		escalation_ticket.insert(ignore_permissions=True)

		# Create a standard ToDo assigned to the Teacher-Mentor / Coordinator user
		allocated_user = (
			(coordinator.get("erpnext_user") if coordinator else None)
			or frappe.session.user
		)
		todo = frappe.get_doc(
			{
				"doctype": "ToDo",
				"allocated_to": allocated_user,
				"reference_type": "EGS Escalation Ticket",
				"reference_name": escalation_ticket.name,
				"description": (
					f"Assistance needed: Student {student.get('student_name', doc.student_reference)} "
					f"requested help in Check-in Round {doc.check_in_round}. "
					f"Teacher-Mentor: {designated_anchor or 'Unassigned'}."
				),
				"status": "Open",
			}
		)
		todo.insert(ignore_permissions=True)


def check_silent_students():
	"""
	Scheduled job function to monitor student check-in frequency.
	Queries EGS Student Participant, checks if they have any EGS Check-in Log
	in the last 60 days, and if not, flags them for escalation to their Cohort Captain.
	"""
	sixty_days_ago = add_days(now_datetime(), -60)

	# Fetch distinct students who have checked in within the last 60 days
	active_students = frappe.get_all(
		"EGS Check-in Log",
		filters={"timestamp": [">=", sixty_days_ago]},
		pluck="student_reference",
		distinct=True,
	)

	# Query students who have NOT checked in within the last 60 days
	filters = {}
	if active_students:
		filters["name"] = ["not in", list(set(active_students))]

	silent_students = frappe.get_all(
		"EGS Student Participant",
		filters=filters,
		fields=["name", "student_name", "university_college", "phone_number"],
	)

	# Avoid re-escalating students who already have an open Silent escalation ticket
	existing_silent_tickets = set(
		frappe.get_all(
			"EGS Escalation Ticket",
			filters={
				"escalation_route": "Silent",
				"status": "Open",
			},
			pluck="student_reference",
		)
	)

	for student in silent_students:
		if student.name in existing_silent_tickets:
			continue

		# Find Cohort Captain linked to the student's university_college
		cohort_captain = None
		if student.university_college:
			cohort_captain = frappe.db.get_value(
				"EGS Coordinator",
				{
					"role": "Cohort Captain",
					"institution": student.university_college,
				},
				["name", "full_name", "erpnext_user", "email"],
				as_dict=True,
			)

		# Fallback to general Cohort Captain if none specific to the institution
		if not cohort_captain:
			cohort_captain = frappe.db.get_value(
				"EGS Coordinator",
				{"role": "Cohort Captain"},
				["name", "full_name", "erpnext_user", "email"],
				as_dict=True,
			)

		# Find the student's most recent check-in log, or create an initial triage log
		latest_check_in = frappe.db.get_value(
			"EGS Check-in Log",
			{"student_reference": student.name},
			"name",
			order_by="timestamp desc",
		)

		if not latest_check_in:
			silent_log = frappe.get_doc(
				{
					"doctype": "EGS Check-in Log",
					"student_reference": student.name,
					"check_in_round": 0,
					"timestamp": now_datetime(),
					"triage_route": "Silent",
				}
			)
			silent_log.insert(ignore_permissions=True)
			latest_check_in = silent_log.name

		# Create the escalation ticket for the Cohort Captain
		ticket = frappe.get_doc(
			{
				"doctype": "EGS Escalation Ticket",
				"student_reference": student.name,
				"triggering_check_in": latest_check_in,
				"escalation_route": "Silent",
				"assigned_coordinator": cohort_captain.get("name") if cohort_captain else None,
				"status": "Open",
				"resolution_notes": (
					f"Student {student.student_name} ({student.name}) has had no check-in logs "
					f"in the last 60 days. Escalated to Cohort Captain "
					f"{cohort_captain.get('full_name', 'Unassigned') if cohort_captain else 'Unassigned'}."
				),
			}
		)
		ticket.insert(ignore_permissions=True)

		# Assign a ToDo to the Cohort Captain's system user if available
		if cohort_captain and cohort_captain.get("erpnext_user"):
			frappe.get_doc(
				{
					"doctype": "ToDo",
					"allocated_to": cohort_captain.erpnext_user,
					"reference_type": "EGS Escalation Ticket",
					"reference_name": ticket.name,
					"description": (
						f"Silent Student Escalation: {student.student_name} ({student.name}) "
						f"has no check-ins for the last 60 days."
					),
					"status": "Open",
				}
			).insert(ignore_permissions=True)
