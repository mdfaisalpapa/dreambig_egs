import frappe
from frappe import _
from dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant import get_all_career_pathways

no_cache = 1


def get_context(context):
	frappe.local.no_cache = True
	context.no_cache = 1
	context.show_sidebar = False
	context.title = _("My DREAM BIG Journey")

	student_id = frappe.form_dict.get("id")
	access_key = frappe.form_dict.get("key")

	if not student_id or not access_key:
		context.is_valid = False
		context.error_message = _("Access link is missing credentials. Please use the link sent to your email or recover it.")
		return

	# Fetch student record
	student = frappe.db.get_value(
		"EGS Student Participant",
		student_id,
		[
			"name",
			"student_name",
			"student_email",
			"phone_number",
			"guardian_phone_number",
			"city",
			"university_college",
			"event",
			"course",
			"cohort_year",
			"event_status",
			"food_coupon_issued",
			"food_coupon_code",
			"access_token",
			"final_chosen_career_goal",
			"personal_vision_statement",
			"date_of_decision",
			"current_5ds_stage",
			"a_promise_to_self",
			"reason_for_goal_change",
		],
		as_dict=True,
	)

	if not student or student.access_token != access_key:
		context.is_valid = False
		context.error_message = _("Invalid or expired access link. Please verify your link or request a new one.")
		return

	context.is_valid = True
	context.student = student
	context.student_id = student_id
	context.access_key = access_key
	context.all_pathways = get_all_career_pathways()

	# Fetch linked event if available
	context.event = None
	if student.event:
		context.event = frappe.db.get_value(
			"EGS Event",
			student.event,
			["name", "event_name", "event_date", "venue", "city", "allow_digital_food_coupons"],
			as_dict=True,
		)

	# Fetch Top 5 Career Choices from child table
	choices = frappe.get_all(
		"EGS Student Career Choice",
		filters={"parent": student_id, "parenttype": "EGS Student Participant"},
		fields=["career_pathway", "notes"],
		order_by="idx asc",
	)
	context.career_choices = choices
	context.selected_pathway_names = [c.career_pathway for c in choices]

	# Fetch DECIDE Stage / Career Goal record if any
	career_goals = frappe.get_all(
		"EGS Career Goal",
		filters={"student_reference": student_id},
		fields=[
			"name",
			"finalized_career_goal",
			"current_5ds_stage",
			"deadline",
			"personal_vision_statement",
			"a_promise_to_self",
		],
		order_by="creation desc",
		limit=1,
	)
	context.career_goal = career_goals[0] if career_goals else None

	# Fetch Commitments for Stage 4: DEVELOP
	commitments = []
	if context.career_goal:
		commitments = frappe.get_all(
			"EGS Commitment",
			filters={"career_goal_reference": context.career_goal.name},
			fields=[
				"name",
				"action_required",
				"due_date",
				"progress_status",
				"reported_barrier",
				"creation",
			],
			order_by="due_date asc, creation asc",
		)
	context.commitments = commitments

	raw_stage = student.get("current_5ds_stage")
	if raw_stage:
		active_stage = raw_stage
	elif student.get("event_status") == "Checked-In":
		active_stage = "DISCOVER"
	else:
		active_stage = "DREAM"

	context.active_stage = active_stage
	context.effective_5ds_stage = active_stage

	# Map stage names to numeric rank (1-5) for past-stage lock checks
	stage_rank_map = {
		"DREAM": 1,
		"DISCOVER": 2,
		"DECIDE": 3,
		"DEVELOP": 4,
		"DEVELOP/PREPARE": 4,
		"DELIVER": 5,
	}
	context.stage_rank_map = stage_rank_map
	context.current_stage_num = stage_rank_map.get(active_stage, 1)

	context.today_date = frappe.utils.today()

