# Copyright (c) 2026, Dream Big and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class EGSCareerGoal(Document):
	def validate(self):
		if not self.student_reference:
			frappe.throw(_("Student Reference is mandatory."))

		if not self.finalized_career_goal:
			frappe.throw(_("Finalized Career Goal is mandatory."))

		if not self.current_5ds_stage:
			self.current_5ds_stage = "DECIDE"

	def on_update(self):
		"""
		Bidirectionally syncs back to EGS Student Participant if modified in Desk.
		"""
		if getattr(self.flags, "ignore_student_sync", False):
			return

		if not self.student_reference or not frappe.db.exists("EGS Student Participant", self.student_reference):
			return

		try:
			student = frappe.get_doc("EGS Student Participant", self.student_reference)
			changed = False

			if student.final_chosen_career_goal != self.finalized_career_goal:
				student.final_chosen_career_goal = self.finalized_career_goal
				changed = True

			if self.personal_vision_statement and student.personal_vision_statement != self.personal_vision_statement:
				student.personal_vision_statement = self.personal_vision_statement
				changed = True

			if self.a_promise_to_self and getattr(student, "a_promise_to_self", None) != self.a_promise_to_self:
				student.a_promise_to_self = self.a_promise_to_self
				changed = True

			if self.deadline and getattr(student, "date_of_decision", None) != self.deadline:
				student.date_of_decision = self.deadline
				changed = True

			if getattr(student, "current_5ds_stage", None) != self.current_5ds_stage:
				student.current_5ds_stage = self.current_5ds_stage
				changed = True

			if changed:
				student.flags.ignore_career_goal_sync = True
				student.save(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(f"Error syncing EGS Career Goal to Student Participant {self.student_reference}: {e}", "Career Goal Sync")
