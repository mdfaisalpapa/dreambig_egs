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
			"chosen_career_domain",
			"assigned_career_coordinator",
			"registered_coordinator_goal",
			"chosen_career_domain_2",
			"assigned_career_coordinator_2",
			"registered_coordinator_goal_2",
			"narrow_goal_1",
			"narrow_goal_2",
			"ap_session_registered",
			"ap_session_registration_date",
			"success_framework_score",
			"sf_daily_newspaper",
			"sf_routine_discipline",
			"sf_skill_learning",
			"sf_pyq_syllabus_reviewed",
			"sf_peer_forum_active",
			"sf_coordinator_clarity",
			"sf_coordinator_discipline",
			"sf_coordinator_mindset",
			"sf_coordinator_notes",
			"sf_last_evaluated_date",
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
	# If student hasn't reached DECIDE, stage is DREAM until event check-in AND 5 goals chosen
	if raw_stage in ("DECIDE", "DEVELOP", "DEVELOP/PREPARE", "DELIVER"):
		active_stage = raw_stage
	elif raw_stage == "DISCOVER":
		active_stage = "DISCOVER"
	elif student.get("event_status") == "Checked-In" and len(choices) >= 5:
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

	# Calculate timeline from event date
	context.days_since_event = 0
	context.months_since_event = 0
	if context.event and context.event.get("event_date"):
		evt_date = context.event.get("event_date")
		if isinstance(evt_date, str):
			evt_date = frappe.utils.getdate(evt_date[:10])
		elif hasattr(evt_date, "date"):
			evt_date = evt_date.date()
		today_d = frappe.utils.getdate(frappe.utils.today())
		delta_days = (today_d - evt_date).days
		context.days_since_event = max(delta_days, 0)
		context.months_since_event = round(context.days_since_event / 30.0, 1)

	# 10 Broad Career Domains from Brochure Page 5, Para 5
	career_domains = [
		"Higher Education & Research (India)",
		"Higher Education & Research Abroad",
		"Civil Services (UPSC CSE)",
		"UPSC Specialized Services",
		"State/Provincial Civil Services",
		"Judiciary/Legal Profession",
		"Entrepreneurship, Business and Institution Building",
		"Arts, Journalism, Sports, and Creative Careers",
		"Defence and Uniformed Services",
		"Any Other",
	]
	context.career_domains = career_domains

	# Coordinators list grouped by domain
	coordinators = frappe.get_all(
		"EGS Coordinator",
		fields=["name", "coordinator_name", "career_domain", "institution", "contact_number", "designation", "role"],
		order_by="career_domain asc, coordinator_name asc",
	)
	context.coordinators = coordinators

	# Available Online Sessions
	sessions = frappe.get_all(
		"EGS Online Session",
		fields=["name", "session_title", "organizer", "career_domain", "session_datetime", "meeting_platform", "meeting_link", "status", "speakers_summary", "session_notes"],
		order_by="session_datetime asc",
	)
	# Fetch student's registered sessions
	registered_session_ids = []
	if student_id:
		regs = frappe.get_all(
			"EGS Session Registration",
			filters={"student": student_id},
			fields=["session"],
		)
		registered_session_ids = [r.session for r in regs]

	for s in sessions:
		s["is_registered"] = s.name in registered_session_ids
	context.online_sessions = sessions

	# Career-specific Peer Forums (matching student's domain or top goals)
	peer_forums = frappe.get_all(
		"EGS Peer Forum",
		filters={"is_active": 1},
		fields=["name", "forum_name", "career_domain", "platform", "invite_link", "student_ambassador", "ambassador_contact", "forum_description"],
		order_by="career_domain asc",
	)

	# Partition peer forums: relevant to student's 5 shortlisted goals or front-runners vs other domains
	shortlisted_texts = [c.career_pathway.lower() for c in choices]
	if student.get("narrow_goal_1"):
		shortlisted_texts.append(student.get("narrow_goal_1").lower())
	if student.get("narrow_goal_2"):
		shortlisted_texts.append(student.get("narrow_goal_2").lower())
	if student.get("chosen_career_domain"):
		shortlisted_texts.append(student.get("chosen_career_domain").lower())
	if student.get("chosen_career_domain_2"):
		shortlisted_texts.append(student.get("chosen_career_domain_2").lower())

	relevant_forums = []
	other_forums = []

	for pf in peer_forums:
		d_lower = (pf.career_domain or "").lower()
		fn_lower = (pf.forum_name or "").lower()
		# check if domain or forum name relates to any of the shortlisted pathways
		is_match = any(
			(txt in d_lower or d_lower in txt or any(w in fn_lower for w in txt.split() if len(w) > 4))
			for txt in shortlisted_texts
		)
		if is_match:
			relevant_forums.append(pf)
		else:
			other_forums.append(pf)

	# If no specific match, show all in relevant to avoid empty state
	if not relevant_forums:
		relevant_forums = peer_forums
		other_forums = []

	context.peer_forums = peer_forums
	context.relevant_peer_forums = relevant_forums
	context.other_peer_forums = other_forums

	# Calculate current Success Framework score dynamically if not yet set or to ensure freshness
	from dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant import calculate_success_framework_score
	current_sf_score = calculate_success_framework_score(student)
	if student.get("success_framework_score") != current_sf_score:
		frappe.db.set_value("EGS Student Participant", student_id, "success_framework_score", current_sf_score, update_modified=False)
		student["success_framework_score"] = current_sf_score
	context.success_framework_score = current_sf_score

	# Final chosen goal metadata, dedicated peer forum, and assigned DB coordinator for Stage 3 & 4
	context.final_goal_doc = None
	context.final_goal_forum = None
	context.final_goal_coordinator = None
	final_goal_name = student.get("final_chosen_career_goal") or (context.career_goal and context.career_goal.get("finalized_career_goal"))
	if final_goal_name:
		fg_doc = frappe.db.get_value(
			"EGS Career Pathway",
			final_goal_name,
			["name", "career_title", "career_category", "career_group", "domain", "education_requirements", "standard_preparation_timeline"],
			as_dict=True,
		)
		context.final_goal_doc = fg_doc
		# Find peer forum matching the final chosen goal domain or name
		fg_match_texts = [final_goal_name.lower()]
		if fg_doc:
			if fg_doc.get("career_category"):
				fg_match_texts.append(fg_doc.career_category.lower())
			if fg_doc.get("career_group"):
				fg_match_texts.append(fg_doc.career_group.lower())
			if fg_doc.get("domain"):
				fg_match_texts.append(fg_doc.domain.lower())

		for pf in peer_forums:
			d_low = (pf.career_domain or "").lower()
			fn_low = (pf.forum_name or "").lower()
			if any(txt in d_low or d_low in txt or any(w in fn_low for w in txt.split() if len(w) > 4) for txt in fg_match_texts):
				context.final_goal_forum = pf
				break

		# Auto-match or fetch assigned DB Coordinator for the finalized career pathway
		assigned_coord_name = student.get("assigned_career_coordinator")
		if assigned_coord_name:
			context.final_goal_coordinator = frappe.db.get_value(
				"EGS Coordinator",
				assigned_coord_name,
				["name", "coordinator_name", "career_domain", "institution", "contact_number", "designation", "role"],
				as_dict=True,
			)
		if not context.final_goal_coordinator and coordinators:
			for coord in coordinators:
				cd_low = (coord.career_domain or "").lower()
				cn_low = (coord.coordinator_name or "").lower()
				if any(txt in cd_low or cd_low in txt or any(w in cn_low for w in txt.split() if len(w) > 4) for txt in fg_match_texts):
					context.final_goal_coordinator = coord
					break

	context.today_date = frappe.utils.today()

