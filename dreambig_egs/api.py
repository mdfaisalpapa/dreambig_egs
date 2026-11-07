# Copyright (c) 2026, Dream Big and contributors
# For license information, please see license.txt

import frappe
from dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant import (
	revert_5ds_stage as _revert_5ds_stage,
	submit_decide_stage as _submit_decide_stage,
	save_career_goals as _save_career_goals,
	event_checkin as _event_checkin,
	get_student_career_choices as _get_student_career_choices,
	advance_to_develop as _advance_to_develop,
	add_egs_commitment as _add_egs_commitment,
	step_back_stage as _step_back_stage,
	advance_to_deliver as _advance_to_deliver,
)


@frappe.whitelist(allow_guest=True)
def revert_5ds_stage(student_id, reason, token=None):
	"""
	Reverts a student's 5Ds stage from DECIDE back to DISCOVER,
	clears their finalized career goal, and logs the reason for change.
	"""
	return _revert_5ds_stage(student_id=student_id, reason=reason, token=token)


@frappe.whitelist(allow_guest=True)
def submit_decide_stage(student_id, token, final_chosen_career_goal, personal_vision_statement, a_promise_to_self=None, date_of_decision=None):
	return _submit_decide_stage(
		student_id=student_id,
		token=token,
		final_chosen_career_goal=final_chosen_career_goal,
		personal_vision_statement=personal_vision_statement,
		a_promise_to_self=a_promise_to_self,
		date_of_decision=date_of_decision,
	)


@frappe.whitelist(allow_guest=True)
def save_career_goals(student_id, token, goals):
	return _save_career_goals(student_id=student_id, token=token, goals=goals)


@frappe.whitelist(allow_guest=True)
def event_checkin(student_id, token):
	return _event_checkin(student_id=student_id, token=token)


@frappe.whitelist(allow_guest=True)
def get_student_career_choices(student_id, token):
	return _get_student_career_choices(student_id=student_id, token=token)


@frappe.whitelist(allow_guest=True)
def advance_to_develop(student_id, token):
	"""
	Advances a student's 5Ds stage from DECIDE to DEVELOP/PREPARE.
	"""
	return _advance_to_develop(student_id=student_id, token=token)


@frappe.whitelist(allow_guest=True)
def add_egs_commitment(student_id, token, data):
	"""
	Adds a new EGS Commitment milestone under the student's finalized career goal.
	"""
	return _add_egs_commitment(student_id=student_id, token=token, data=data)


@frappe.whitelist(allow_guest=True)
def step_back_stage(student_id, token, target_stage):
	"""
	Cascading step-back across 5Ds stages (e.g., DELIVER -> DEVELOP/PREPARE, DEVELOP -> DECIDE).
	Cleanly wipes the data belonging to the stage being exited.
	"""
	return _step_back_stage(student_id=student_id, token=token, target_stage=target_stage)


@frappe.whitelist(allow_guest=True)
def advance_to_deliver(student_id, token):
	"""
	Advances a student's 5Ds stage from DEVELOP to DELIVER.
	"""
	return _advance_to_deliver(student_id=student_id, token=token)

