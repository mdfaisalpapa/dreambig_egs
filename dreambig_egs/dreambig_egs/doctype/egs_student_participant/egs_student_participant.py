# Copyright (c) 2026, Dream Big and contributors
# For license information, please see license.txt

import random
import re
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url

CAREER_PATHWAYS = [
	"path_emp_govt_public",
	"path_emp_govt_reg",
	"path_emp_finance",
	"path_emp_scientific",
	"path_emp_academic",
	"path_emp_inventions",
	"path_emp_prof_biz",
	"path_emp_arts_sports",
	"path_emp_religious",
	"path_emp_political",
	"path_emp_un_global",
	"path_biz_institution",
	"path_biz_social",
	"path_biz_finance",
	"path_biz_mfg_trade",
	"path_biz_entrepreneur",
	"path_biz_consulting",
	"path_biz_law_hr",
	"path_biz_tech",
]


class EGSStudentParticipant(Document):
	def before_insert(self):
		if not self.access_token:
			self.access_token = frappe.generate_hash(length=15)

	def after_insert(self):
		self.send_magic_link(is_welcome=True)

	def send_magic_link(self, is_welcome=False):
		if not self.access_token:
			self.access_token = frappe.generate_hash(length=15)
			self.save(ignore_permissions=True)

		portal_url = f"{get_url()}/my-dream-big?id={self.name}&key={self.access_token}"
		subject = (
			"Welcome to DREAM BIG! Your Personalized Access Link"
			if is_welcome
			else "Your DREAM BIG Journey Access Link"
		)

		message = f"""
        <p>Dear {self.student_name},</p>
        <p>{'Welcome to the <b>EARLY GOAL SETTING: DREAM BIG</b> initiative!' if is_welcome else 'Here is the secure link to access your dashboard.'}</p>
        <p>To track your progress, update your career goals, and access your 5Ds framework, click the button below. <b>Please bookmark this link or 'Add to Home Screen' on your mobile device.</b></p>
        <br>
        <a href="{portal_url}" style="background-color: #0056b3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Access My Journey Dashboard</a>
        <br><br>
        <p>Motto: No student should be left unguided and no one should be left behind.</p>
        <p>Warm regards,<br>The DREAM BIG Team</p>
        """
		if self.student_email:
			try:
				frappe.sendmail(
					recipients=[self.student_email],
					subject=subject,
					message=message,
					delayed=True,
				)
			except Exception as e:
				frappe.clear_last_message()
				frappe.log_error(f"Failed to send magic link email to {self.student_email}: {e}", "Magic Link Sendmail")

	def validate(self):
		self.validate_phone_numbers()
		self.validate_city_and_institution()
		self.validate_and_assign_event()
		self.validate_career_goals()

	def validate_and_assign_event(self):
		from dreambig_egs.dreambig_egs.doctype.egs_event.egs_event import get_open_events_by_city

		# 1. If event is not yet specified, auto-assign from open events in student's city
		if not self.event:
			if self.city:
				open_events = get_open_events_by_city(city=self.city)
				if open_events:
					first_event = open_events[0]
					self.event = (
						first_event.name
						if hasattr(first_event, "name")
						else (first_event.get("name") or first_event.get("value"))
					)
				else:
					if frappe.db.count("EGS Event") > 0:
						frappe.throw(
							_("No events are currently open for registration in {0}.").format(
								self.city
							)
						)

		# 2. If event is specified, validate it
		if self.event:
			if not frappe.db.exists("EGS Event", self.event):
				frappe.throw(_("Selected Event '{0}' does not exist.").format(self.event))

			event_doc = frappe.get_doc("EGS Event", self.event)

			# Validate status
			if event_doc.status != "Open for Registration":
				frappe.throw(
					_("Event '{0}' is not open for registration (status: {1}).").format(
						event_doc.event_name or self.event, event_doc.status
					)
				)

			# Validate matching city
			if event_doc.city and self.city and event_doc.city != self.city:
				frappe.throw(
					_(
						"Selected Event '{0}' belongs to city '{1}', which does not"
						" match your selected city '{2}'."
					).format(event_doc.event_name or self.event, event_doc.city, self.city)
				)

			# Validate registration deadline
			if event_doc.registration_deadline:
				today_date = frappe.utils.today()
				deadline_str = str(event_doc.registration_deadline)[:10]
				if deadline_str < today_date:
					frappe.throw(
						_(
							"The registration deadline ({0}) for event '{1}' has passed."
						).format(deadline_str, event_doc.event_name or self.event)
					)

	def validate_phone_numbers(self):
		ten_digit_regex = re.compile(r"^\d{10}$")

		# 1. Student Phone Number
		student_phone = (self.phone_number or "").strip()
		if not student_phone:
			frappe.throw(_("Student Phone Number is mandatory."))
		if not ten_digit_regex.match(student_phone):
			frappe.throw(_("Student Phone Number must be exactly 10 digits."))
		self.phone_number = student_phone

		# 2. Guardian Phone Number
		guardian_phone = (self.guardian_phone_number or "").strip()
		if guardian_phone:
			if not ten_digit_regex.match(guardian_phone):
				frappe.throw(_("Guardian Phone Number must be exactly 10 digits."))
			self.guardian_phone_number = guardian_phone

			# 3. Student & Guardian phones must not be identical
			if student_phone == guardian_phone:
				frappe.throw(
					_(
						"Student Phone Number and Guardian Phone Number cannot"
						" be identical."
					)
				)

	def validate_city_and_institution(self):
		if not self.city:
			frappe.throw(_("City is mandatory."))

		if not self.university_college:
			frappe.throw(_("University/College is mandatory."))

		if not frappe.db.exists("EGS Institution", self.university_college):
			frappe.throw(
				_("Selected Institution '{0}' does not exist.").format(
					self.university_college
				)
			)

		inst_city = frappe.db.get_value(
			"EGS Institution", self.university_college, "city"
		)
		if inst_city != self.city:
			frappe.throw(
				_(
					"Selected Institution '{0}' belongs to city '{1}', which"
					" does not match the selected city '{2}'."
				).format(self.university_college, inst_city, self.city)
			)

	def validate_career_goals(self):
		table_count = (
			len(self.top_5_career_goals)
			if self.get("top_5_career_goals")
			else 0
		)
		checkbox_count = sum(1 for p in CAREER_PATHWAYS if self.get(p))
		total_selected = table_count if table_count > 0 else checkbox_count

		if total_selected > 5:
			frappe.throw(
				_("Please narrow your focus to a maximum of 5 Career Goals.")
			)

	def on_update(self):
		if self.final_chosen_career_goal:
			self.sync_career_goal()

	def sync_career_goal(self):
		if getattr(self.flags, "ignore_career_goal_sync", False):
			return
		if not self.final_chosen_career_goal:
			return

		# Resolve pathway name
		pathway = self.final_chosen_career_goal
		if not frappe.db.exists("EGS Career Pathway", pathway):
			if frappe.db.exists("EGS Student Career Choice", pathway):
				pathway = frappe.db.get_value("EGS Student Career Choice", pathway, "career_pathway")
			else:
				pathway = frappe.db.get_value("EGS Career Pathway", {"career_title": pathway}, "name")

		if not pathway or not frappe.db.exists("EGS Career Pathway", pathway):
			return

		existing_goals = frappe.get_all(
			"EGS Career Goal",
			filters={"student_reference": self.name},
			order_by="creation desc",
			limit=1,
		)

		promise = getattr(self, "a_promise_to_self", None) or self.personal_vision_statement
		deadline = getattr(self, "date_of_decision", None) or frappe.utils.today()
		target_stage = getattr(self, "current_5ds_stage", None) or "DECIDE"
		if target_stage not in ("DECIDE", "DEVELOP", "DEVELOP/PREPARE", "DELIVER"):
			target_stage = "DECIDE"

		goal_doc = None
		if existing_goals:
			try:
				goal_doc = frappe.get_doc("EGS Career Goal", existing_goals[0].name)
			except Exception:
				goal_doc = None

		if goal_doc:
			goal_doc.finalized_career_goal = pathway
			goal_doc.current_5ds_stage = target_stage
			goal_doc.deadline = deadline
			goal_doc.personal_vision_statement = self.personal_vision_statement
			goal_doc.a_promise_to_self = promise
			goal_doc.flags.ignore_student_sync = True
			goal_doc.flags.ignore_version = True
			try:
				goal_doc.save(ignore_permissions=True)
			except frappe.exceptions.TimestampMismatchError:
				frappe.clear_messages()
				pass
		else:
			goal_doc = frappe.get_doc({
				"doctype": "EGS Career Goal",
				"student_reference": self.name,
				"finalized_career_goal": pathway,
				"current_5ds_stage": target_stage,
				"deadline": deadline,
				"personal_vision_statement": self.personal_vision_statement,
				"a_promise_to_self": promise,
			})
			goal_doc.flags.ignore_student_sync = True
			goal_doc.insert(ignore_permissions=True)

		if getattr(self, "current_5ds_stage", None) not in ("DECIDE", "DEVELOP", "DEVELOP/PREPARE", "DELIVER"):
			self.current_5ds_stage = target_stage
			self.db_set("current_5ds_stage", target_stage)


@frappe.whitelist(allow_guest=True)
def get_all_career_pathways():
	return frappe.get_all(
		"EGS Career Pathway",
		fields=[
			"name",
			"career_category",
			"career_group",
			"career_title",
			"brochure_index",
		],
		order_by="career_category desc, brochure_index asc, career_title asc",
	)


@frappe.whitelist(allow_guest=True)
def resend_magic_link(email):
	email = (email or "").strip()
	if not email:
		return {"status": "failed", "message": "Email is required."}

	students = frappe.get_all(
		"EGS Student Participant",
		filters={"student_email": email},
		fields=["name"],
	)
	if not students:
		return {"status": "failed", "message": "Email not found."}

	doc = frappe.get_doc("EGS Student Participant", students[0].name)
	if not doc.access_token:
		doc.access_token = frappe.generate_hash(length=15)
		doc.save(ignore_permissions=True)
	doc.send_magic_link()
	return {
		"status": "success",
		"message": "Your secure access link has been emailed to you.",
	}


def process_student_checkin(doc, qr_passcode=None):
	event = None
	if doc.event:
		event = frappe.get_doc("EGS Event", doc.event)
	elif doc.city:
		from dreambig_egs.dreambig_egs.doctype.egs_event.egs_event import get_open_events_by_city
		open_events = get_open_events_by_city(doc.city)
		if open_events:
			doc.event = open_events[0].name
			event = frappe.get_doc("EGS Event", doc.event)

	# 1. Event Date Validation: Check-in is allowed on the event date
	if event and event.event_date:
		today_str = str(frappe.utils.today())
		event_date_str = str(event.event_date)[:10]
		if today_str != event_date_str:
			frappe.throw(
				_("Event check-in is only allowed on the day of the event ({0}). Today is {1}.").format(
					event_date_str, today_str
				),
				frappe.ValidationError,
			)

	# 2. Digital check-in validation
	if event and not event.allow_digital_checkins:
		frappe.throw(
			_("Digital check-ins are not enabled for this event."),
			frappe.ValidationError,
		)

	already_checked_in = (doc.event_status == "Checked-In")
	doc.event_status = "Checked-In"
	doc.physical_attendance = 1
	# On check-in, student enters Stage 1: DREAM to shortlist 5 career goals
	if getattr(doc, "current_5ds_stage", None) in (None, ""):
		doc.current_5ds_stage = "DREAM"

	# 2. Digital food coupon issuance
	coupon_issued = False
	if event and event.allow_digital_food_coupons:
		if not doc.food_coupon_issued or not getattr(doc, "food_coupon_code", None):
			doc.food_coupon_issued = 1
			doc.food_coupon_code = f"MEAL-{frappe.generate_hash(length=6).upper()}"
			coupon_issued = True

	doc.save(ignore_permissions=True)
	frappe.db.commit()

	# 3. Send checkin confirmation
	send_checkin_confirmation(doc, event)

	return doc, already_checked_in, coupon_issued


def send_checkin_confirmation(doc, event=None):
	if not doc.student_email:
		return

	event_name = event.event_name if event else "DREAM BIG Event"
	venue = event.venue if event and event.venue else "Venue"
	coupon_info = ""
	if getattr(doc, "food_coupon_code", None):
		coupon_info = f"""
		<div style="background: #f0fdf4; border: 1px dashed #22c55e; padding: 15px; border-radius: 8px; margin: 15px 0;">
			<h4 style="color: #166534; margin: 0 0 5px 0;">Digital Food Coupon</h4>
			<p style="margin: 0; font-size: 1.2rem; font-weight: bold; color: #15803d; letter-spacing: 2px;">{doc.food_coupon_code}</p>
			<small style="color: #166534;">Show this code at the lunch counter.</small>
		</div>
		"""

	subject = f"Check-In Confirmed - {event_name}"
	message = f"""
	<p>Dear {doc.student_name},</p>
	<p>You have successfully checked in for <b>{event_name}</b> at {venue}!</p>
	<p>Your 5 DREAM BIG Career Goals (Exercise 2) are now unlocked on your dashboard.</p>
	{coupon_info}
	<p><a href="{get_url()}/my-dream-big?id={doc.name}&key={doc.access_token}" style="background-color: #0056b3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Go to My Dashboard</a></p>
	<br>
	<p>Warm regards,<br>The DREAM BIG Team</p>
	"""
	try:
		frappe.sendmail(
			recipients=[doc.student_email],
			subject=subject,
			message=message,
			delayed=True,
		)
	except Exception as e:
		frappe.clear_last_message()
		frappe.log_error(
			f"Failed to send checkin confirmation to {doc.student_email}: {e}",
			"Checkin Email",
		)


@frappe.whitelist(allow_guest=True)
def event_checkin(student_id, token):
	doc = frappe.get_doc("EGS Student Participant", student_id)
	if doc.access_token != token:
		frappe.throw("Invalid access token", frappe.PermissionError)

	doc, already_checked_in, coupon_issued = process_student_checkin(doc)
	coupon_msg = (
		f" Your digital food coupon code is: {doc.food_coupon_code}."
		if getattr(doc, "food_coupon_code", None)
		else ""
	)

	if not already_checked_in:
		return {
			"status": "success",
			"message": (
				f"Successfully checked in! You can now select your 5 DREAM BIG Goals.{coupon_msg}"
			),
			"coupon_code": getattr(doc, "food_coupon_code", None),
		}
	return {
		"status": "success",
		"message": f"Already checked in.{coupon_msg}",
		"coupon_code": getattr(doc, "food_coupon_code", None),
	}


@frappe.whitelist(allow_guest=True)
def event_checkin_by_email(email):
	email = (email or "").strip()
	if not email:
		frappe.throw("Email is required")
	students = frappe.get_all(
		"EGS Student Participant",
		filters={"student_email": email},
		fields=["name"],
	)
	if not students:
		return {"status": "error", "message": "Email not found. Please register first."}

	doc = frappe.get_doc("EGS Student Participant", students[0].name)
	if not doc.access_token:
		doc.access_token = frappe.generate_hash(length=15)
		doc.save(ignore_permissions=True)

	doc, already_checked_in, coupon_issued = process_student_checkin(doc)

	return {
		"status": "success",
		"student_id": doc.name,
		"token": doc.access_token,
		"coupon_code": getattr(doc, "food_coupon_code", None),
		"redirect_url": f"/my-dream-big?id={doc.name}&key={doc.access_token}",
	}


@frappe.whitelist(allow_guest=True)
def save_career_goals(student_id, token, goals):
	if isinstance(goals, str):
		import json
		goals = json.loads(goals)

	doc = frappe.get_doc("EGS Student Participant", student_id)
	if doc.access_token != token:
		frappe.throw("Invalid access token", frappe.PermissionError)

	if doc.event_status != "Checked-In":
		frappe.throw(
			"Event check-in required before selecting career goals.",
			frappe.ValidationError,
		)

	if not goals or len(goals) == 0:
		frappe.throw("Please select at least 1 Career Goal.")
	if len(goals) > 5:
		frappe.throw("You can select up to 5 Career Goals.")

	doc.set("top_5_career_goals", [])
	for g in goals:
		doc.append("top_5_career_goals", {"career_pathway": g})

	# If student selected 5 goals and is currently in DREAM stage, advance to Stage 2: DISCOVER
	if len(goals) == 5 and (not doc.current_5ds_stage or doc.current_5ds_stage == "DREAM"):
		doc.current_5ds_stage = "DISCOVER"

	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"status": "success",
		"message": "Your 5 Dream Big Career Goals have been saved successfully! Advanced to Stage 2: DISCOVER.",
		"stage": doc.current_5ds_stage,
	}


@frappe.whitelist(allow_guest=True)
def register_specific_session(student_id, token, session_id):
	"""
	Registers a student for a specific upcoming EGS/APSWB Online Session.
	"""
	if not student_id or not token or not session_id:
		frappe.throw(_("Missing required parameters."), frappe.PermissionError)

	doc = frappe.get_doc("EGS Student Participant", student_id)
	if doc.access_token != token:
		frappe.throw(_("Invalid access token."), frappe.PermissionError)

	if not frappe.db.exists("EGS Online Session", session_id):
		frappe.throw(_("Session not found."), frappe.DoesNotExistError)

	session_doc = frappe.get_doc("EGS Online Session", session_id)

	# Check if already registered
	existing = frappe.db.get_value(
		"EGS Session Registration",
		{"session": session_id, "student": student_id},
		"name",
	)
	if existing:
		return {
			"status": "success",
			"message": _("You are already registered for this session!"),
			"session_id": session_id,
			"meeting_link": session_doc.meeting_link,
		}

	reg = frappe.get_doc({
		"doctype": "EGS Session Registration",
		"session": session_id,
		"student": student_id,
		"registration_datetime": frappe.utils.now_datetime(),
		"attendance_status": "Registered",
	})
	reg.insert(ignore_permissions=True)

	# Mark general ap_session_registered on student profile
	doc.ap_session_registered = 1
	doc.ap_session_registration_date = frappe.utils.now_datetime()
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"status": "success",
		"message": _("Successfully registered for {0}!").format(session_doc.session_title),
		"session_id": session_id,
		"meeting_link": session_doc.meeting_link,
	}


@frappe.whitelist(allow_guest=True)
def register_ap_sessions(student_id, token):
	"""
	Registers a student for APSWB Online Alternate Sunday Interactive Sessions
	directly inside the app to track their engagement.
	"""
	if not student_id or not token:
		frappe.throw(_("Missing required parameters."), frappe.PermissionError)

	doc = frappe.get_doc("EGS Student Participant", student_id)
	if doc.access_token != token:
		frappe.throw(_("Invalid access token."), frappe.PermissionError)

	doc.ap_session_registered = 1
	doc.ap_session_registration_date = frappe.utils.now_datetime()
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {
		"status": "success",
		"message": _("Successfully registered for APSWB Alternate Sunday Sessions!"),
		"registered_date": str(doc.ap_session_registration_date),
	}


@frappe.whitelist(allow_guest=True)
def register_with_coordinator(student_id, token, career_domain=None, coordinator_id=None, registered_goal=None, goal_slot=1):
	"""
	Registers the student with their chosen DREAM BIG Career Coordinator (of 10 broad domains),
	linking to Choice 1 or Choice 2 of their front-runner narrowed career goals.
	"""
	if not student_id or not token:
		frappe.throw(_("Missing required parameters."), frappe.PermissionError)

	doc = frappe.get_doc("EGS Student Participant", student_id)
	if doc.access_token != token:
		frappe.throw(_("Invalid access token."), frappe.PermissionError)

	if not career_domain and coordinator_id:
		c_domain = frappe.db.get_value("EGS Coordinator", coordinator_id, "career_domain")
		if c_domain:
			career_domain = c_domain

	if not career_domain:
		frappe.throw(_("Please select a valid Career Coordinator or Domain."), frappe.ValidationError)

	goal_slot = int(goal_slot or 1)

	# Auto-assign matching coordinator for this domain if available
	matched_coord = coordinator_id
	if not matched_coord or not frappe.db.exists("EGS Coordinator", matched_coord):
		coords = frappe.get_all("EGS Coordinator", filters={"career_domain": career_domain}, limit=1)
		if coords:
			matched_coord = coords[0].name

	if goal_slot == 2:
		frappe.db.set_value(
			"EGS Student Participant",
			student_id,
			{
				"chosen_career_domain_2": career_domain,
				"assigned_career_coordinator_2": matched_coord,
				"registered_coordinator_goal_2": registered_goal,
			},
			update_modified=False,
		)
		doc.chosen_career_domain_2 = career_domain
		doc.assigned_career_coordinator_2 = matched_coord
		doc.registered_coordinator_goal_2 = registered_goal
	else:
		doc.chosen_career_domain = career_domain
		doc.assigned_career_coordinator = matched_coord
		doc.save(ignore_permissions=True)
		if registered_goal:
			frappe.db.set_value("EGS Student Participant", student_id, "registered_coordinator_goal", registered_goal, update_modified=False)
			doc.registered_coordinator_goal = registered_goal

	frappe.db.commit()

	assigned = matched_coord or "Assigned Domain Coordinator"
	msg = _("Registered with {0} for {1}!").format(assigned, registered_goal or career_domain)
	return {
		"status": "success",
		"message": msg,
		"goal_slot": goal_slot,
		"coordinator": assigned,
		"domain": career_domain,
		"registered_goal": registered_goal,
	}


def auto_match_coordinator_for_goal(goal_name, student_institution=None):
	"""
	Intelligently maps a career pathway to its corresponding broad domain and
	auto-matches an accomplished DREAM BIG Career Coordinator.
	"""
	if not goal_name:
		return None, None

	goal_name_lower = goal_name.lower().strip()
	pathway = frappe.db.get_value("EGS Career Pathway", goal_name, ["career_category", "career_group"], as_dict=True)
	c_group = (pathway.career_group if pathway else "").lower()

	matched_domain = None

	if any(k in goal_name_lower for k in ("civil services", "ias/ips", "upsc cse")):
		matched_domain = "Civil Services (UPSC CSE)"
	elif any(k in goal_name_lower for k in ("defence", "army", "air staff", "naval staff", "paramilitary")):
		matched_domain = "Defence and Uniformed Services"
	elif any(k in goal_name_lower for k in ("judiciary", "lawyer", "judge", "legal", "supreme court", "high court")):
		matched_domain = "Judiciary/Legal Profession"
	elif any(k in goal_name_lower for k in ("state services", "provincial", "deputy collector", "dsp")):
		matched_domain = "State/Provincial Civil Services"
	elif any(k in goal_name_lower for k in ("global", "abroad", "foreign", "world bank", "imf", "unicef", "unesco", "who")):
		matched_domain = "Higher Education & Research Abroad"
	elif any(k in goal_name_lower for k in ("consulting", "think tank", "policy")):
		matched_domain = "Consulting & Think tanks"
	elif any(k in goal_name_lower for k in ("arts", "journalism", "sports", "author", "creative")):
		matched_domain = "Arts, Journalism, Sports, and Creative Careers"
	elif any(k in goal_name_lower for k in ("unicorn", "startup", "entrepreneur", "business", "manufactur", "company", "bank", "finance", "hospital", "school")):
		matched_domain = "Entrepreneurship, Business and Institution Building"
	elif any(k in goal_name_lower for k in ("isro", "drdo", "csir", "professor", "scientist", "academic", "research", "university", "aicte", "ugc", "icmr", "icar")):
		matched_domain = "Higher Education & Research (India)"
	elif "consulting" in c_group:
		matched_domain = "Consulting & Think tanks"
	elif "entrepreneurship" in c_group or "institution" in c_group or "trade" in c_group:
		matched_domain = "Entrepreneurship, Business and Institution Building"
	elif "academic" in c_group or "scientific" in c_group or "inventions" in c_group:
		matched_domain = "Higher Education & Research (India)"
	elif "defence" in c_group:
		matched_domain = "Defence and Uniformed Services"
	elif "arts" in c_group:
		matched_domain = "Arts, Journalism, Sports, and Creative Careers"
	elif "law" in c_group:
		matched_domain = "Judiciary/Legal Profession"
	elif "govt" in c_group:
		matched_domain = "UPSC Specialized Services"
	else:
		matched_domain = "Entrepreneurship, Business and Institution Building"

	# Match coordinator for this domain (prefer same institution if available)
	coordinator_name = None
	if student_institution:
		local_coords = frappe.get_all("EGS Coordinator", filters={"career_domain": matched_domain, "institution": student_institution}, limit=1)
		if local_coords:
			coordinator_name = local_coords[0].name

	if not coordinator_name:
		coords = frappe.get_all("EGS Coordinator", filters={"career_domain": matched_domain}, limit=1)
		if coords:
			coordinator_name = coords[0].name

	return matched_domain, coordinator_name


@frappe.whitelist(allow_guest=True)
def save_narrowed_goals(student_id, token, goal_1, goal_2=None):
	"""
	Saves the 1 or 2 front-runner narrowed career choices moving towards DECIDE stage,
	and automatically matches DREAM BIG Career Coordinators for both choices.
	"""
	if not student_id or not token or not goal_1:
		frappe.throw(_("Please select at least one front-runner career goal."), frappe.ValidationError)

	doc = frappe.get_doc("EGS Student Participant", student_id)
	if doc.access_token != token:
		frappe.throw(_("Invalid access token."), frappe.PermissionError)

	doc.narrow_goal_1 = goal_1
	doc.narrow_goal_2 = goal_2 or None

	# Auto-match Coordinator 1 for Choice 1
	domain_1, coord_1 = auto_match_coordinator_for_goal(goal_1, doc.university_college)
	doc.chosen_career_domain = domain_1
	doc.assigned_career_coordinator = coord_1
	doc.registered_coordinator_goal = goal_1

	# Auto-match Coordinator 2 for Choice 2 (if selected)
	if goal_2:
		domain_2, coord_2 = auto_match_coordinator_for_goal(goal_2, doc.university_college)
		frappe.db.set_value(
			"EGS Student Participant",
			student_id,
			{
				"chosen_career_domain_2": domain_2,
				"assigned_career_coordinator_2": coord_2,
				"registered_coordinator_goal_2": goal_2,
			},
			update_modified=False,
		)
		doc.chosen_career_domain_2 = domain_2
		doc.assigned_career_coordinator_2 = coord_2
		doc.registered_coordinator_goal_2 = goal_2
	else:
		frappe.db.set_value(
			"EGS Student Participant",
			student_id,
			{
				"chosen_career_domain_2": None,
				"assigned_career_coordinator_2": None,
				"registered_coordinator_goal_2": None,
			},
			update_modified=False,
		)
		doc.chosen_career_domain_2 = None
		doc.assigned_career_coordinator_2 = None
		doc.registered_coordinator_goal_2 = None

	doc.save(ignore_permissions=True)
	frappe.db.set_value("EGS Student Participant", student_id, "registered_coordinator_goal", goal_1, update_modified=False)
	frappe.db.commit()

	return {
		"status": "success",
		"message": _("Front-runner goals saved! Coordinators automatically matched by the system."),
		"narrow_goal_1": doc.narrow_goal_1,
		"narrow_goal_2": doc.narrow_goal_2,
		"coordinator_1": coord_1,
		"domain_1": domain_1,
		"coordinator_2": doc.assigned_career_coordinator_2,
		"domain_2": doc.chosen_career_domain_2,
	}


@frappe.whitelist(allow_guest=True)
def get_courses_by_faculty(faculty):
	if not faculty:
		return []
	courses = frappe.get_all(
		"EGS Course",
		filters={"faculty": faculty},
		fields=["name as value", "course_name as label"],
	)
	return courses


@frappe.whitelist(allow_guest=True)
def send_login_credentials(email):
	student = frappe.get_all("EGS Student Participant", filters={"student_email": email}, limit=1)
	if not student:
		return {"status": "error", "message": "Email not registered. Please register first."}

	doc = frappe.get_doc("EGS Student Participant", student[0].name)

	# Generate 6-digit OTP and store in Redis for 10 minutes
	otp = str(random.randint(100000, 999999))
	frappe.cache().set_value(f"egs_login_otp_{email}", otp, expires_in_sec=600)

	# Construct Magic Link
	magic_link = f"{get_url()}/my-dream-big?id={doc.name}&key={doc.access_token}"

	# Send Email
	subject = "DREAM BIG: Your Login Credentials"
	message = f"Click here to login instantly: {magic_link}<br><br>Or manually enter this OTP on the website: <b>{otp}</b> (Valid for 10 minutes)."
	try:
		frappe.sendmail(recipients=[email], subject=subject, message=message, now=True)
	except Exception as e:
		frappe.clear_last_message()
		frappe.log_error(f"Failed to send login credentials email to {email}: {e}", "Login Credentials Sendmail")

	return {"status": "success", "message": "Credentials sent!"}


@frappe.whitelist(allow_guest=True)
def verify_login_otp(email, otp):
	cached_otp = frappe.cache().get_value(f"egs_login_otp_{email}")

	if not cached_otp or str(cached_otp.decode("utf-8") if isinstance(cached_otp, bytes) else cached_otp) != str(otp):
		return {"status": "error", "message": "Invalid or expired OTP."}

	student = frappe.get_all("EGS Student Participant", filters={"student_email": email}, limit=1)
	doc = frappe.get_doc("EGS Student Participant", student[0].name)

	# Clear OTP from memory after successful use
	frappe.cache().delete_value(f"egs_login_otp_{email}")

	return {
		"status": "success",
		"id": doc.name,
		"key": doc.access_token,
	}


@frappe.whitelist(allow_guest=True)
def get_cohort_whatsapp_link(student_id):
	student = frappe.get_doc("EGS Student Participant", student_id)

	# Search the EGS Institution's child table for a matching Course and Cohort Year
	cohorts = frappe.get_all(
		"EGS Institution Cohort",
		filters={
			"parent": student.university_college,
			"parenttype": "EGS Institution",
			"course": student.course,
			"cohort_year": student.cohort_year,
		},
		fields=["whatsapp_group_link"],
		limit=1,
	)

	if cohorts and cohorts[0].whatsapp_group_link:
		return {"status": "success", "link": cohorts[0].whatsapp_group_link}
	return {"status": "not_found"}


@frappe.whitelist(allow_guest=True)
def submit_decide_stage(
	student_id,
	token,
	final_chosen_career_goal,
	personal_vision_statement,
	a_promise_to_self=None,
	date_of_decision=None,
):
	if not student_id or not token:
		frappe.throw(_("Missing required parameters."), frappe.PermissionError)

	doc = frappe.get_doc("EGS Student Participant", student_id)
	if doc.access_token != token:
		frappe.throw(_("Invalid access token."), frappe.PermissionError)

	doc.reload()

	if not final_chosen_career_goal:
		frappe.throw(_("Please select a finalized career goal."))

	if not personal_vision_statement or not personal_vision_statement.strip():
		frappe.throw(_("Personal Vision Statement is required."))

	# Resolve pathway
	pathway = final_chosen_career_goal
	if not frappe.db.exists("EGS Career Pathway", pathway):
		if frappe.db.exists("EGS Student Career Choice", pathway):
			pathway = frappe.db.get_value("EGS Student Career Choice", pathway, "career_pathway")
		else:
			pathway = frappe.db.get_value("EGS Career Pathway", {"career_title": pathway}, "name")

	if not pathway or not frappe.db.exists("EGS Career Pathway", pathway):
		frappe.throw(_("Invalid career pathway: {0}").format(final_chosen_career_goal))

	today_date = frappe.utils.today()
	dec_date = date_of_decision or today_date
	promise = a_promise_to_self or personal_vision_statement

	doc.final_chosen_career_goal = pathway
	doc.personal_vision_statement = personal_vision_statement.strip()
	doc.a_promise_to_self = promise.strip() if promise else None
	doc.date_of_decision = dec_date
	doc.current_5ds_stage = "DECIDE"

	doc.flags.ignore_version = True
	try:
		doc.save(ignore_permissions=True)
	except frappe.exceptions.TimestampMismatchError:
		frappe.clear_messages()
		pass
	frappe.clear_document_cache("EGS Student Participant", student_id)
	frappe.clear_cache(user="Guest")
	doc.sync_career_goal()
	frappe.db.commit()

	return {
		"status": "success",
		"message": _("Congratulations! Your DECIDE stage commitment has been recorded."),
		"career_goal": pathway,
		"current_5ds_stage": "DECIDE",
	}


@frappe.whitelist(allow_guest=True)
def get_student_career_choices(student_id, token):
	if not student_id or not token:
		frappe.throw(_("Missing required parameters."), frappe.PermissionError)

	doc = frappe.get_doc("EGS Student Participant", student_id)
	if doc.access_token != token:
		frappe.throw(_("Invalid access token."), frappe.PermissionError)

	selected = [c.career_pathway for c in doc.get("top_5_career_goals", []) if c.career_pathway]
	all_pathways = get_all_career_pathways()

	return {
		"status": "success",
		"selected_choices": selected,
		"all_pathways": all_pathways,
		"current_decision": {
			"final_chosen_career_goal": doc.final_chosen_career_goal,
			"personal_vision_statement": doc.personal_vision_statement,
			"a_promise_to_self": getattr(doc, "a_promise_to_self", None),
			"date_of_decision": doc.date_of_decision,
			"current_5ds_stage": getattr(doc, "current_5ds_stage", None),
		},
	}


@frappe.whitelist(allow_guest=True)
def revert_5ds_stage(student_id, reason, token=None):
	if not student_id:
		frappe.throw(_("Student ID is mandatory."))
	if not reason or not reason.strip():
		frappe.throw(_("Please provide a reason for changing your career path."))

	doc = frappe.get_doc("EGS Student Participant", student_id)
	if token and doc.access_token != token:
		frappe.throw(_("Invalid access token."), frappe.PermissionError)

	doc.reload()

	now_str = frappe.utils.now_datetime().strftime("%Y-%m-%d %H:%M:%S")
	entry = f"[{now_str}] {reason.strip()}"
	if getattr(doc, "reason_for_goal_change", None):
		doc.reason_for_goal_change = f"{doc.reason_for_goal_change}\n\n{entry}"
	else:
		doc.reason_for_goal_change = entry

	doc.current_5ds_stage = "DISCOVER"
	doc.final_chosen_career_goal = None
	doc.personal_vision_statement = None
	doc.a_promise_to_self = None
	doc.date_of_decision = None
	doc.flags.ignore_career_goal_sync = True
	doc.flags.ignore_version = True
	try:
		doc.save(ignore_permissions=True)
	except frappe.exceptions.TimestampMismatchError:
		frappe.clear_messages()
		pass
	frappe.clear_document_cache("EGS Student Participant", student_id)
	frappe.clear_cache(user="Guest")

	# Delete linked EGS Career Goal if exists to ensure a truly clean slate
	career_goals = frappe.get_all(
		"EGS Career Goal",
		filters={"student_reference": doc.name},
	)
	for cg in career_goals:
		for com in frappe.get_all("EGS Commitment", filters={"career_goal_reference": cg.name}):
			frappe.delete_doc("EGS Commitment", com.name, ignore_permissions=True, force=True)
		frappe.delete_doc("EGS Career Goal", cg.name, ignore_permissions=True, force=True)

	frappe.db.commit()
	return {
		"status": "success",
		"message": _("Successfully returned to DISCOVER stage. You may now re-evaluate your career goals."),
		"current_5ds_stage": "DISCOVER",
	}


@frappe.whitelist(allow_guest=True)
def advance_to_develop(student_id, token):
	if not student_id or not token:
		frappe.throw(_("Missing required parameters."), frappe.PermissionError)

	doc = frappe.get_doc("EGS Student Participant", student_id)
	if doc.access_token != token:
		frappe.throw(_("Invalid access token."), frappe.PermissionError)

	doc.reload()

	if not doc.final_chosen_career_goal:
		frappe.throw(_("Cannot advance to Stage 4 without a finalized career goal in Stage 3 (DECIDE)."))

	doc.current_5ds_stage = "DEVELOP/PREPARE"
	doc.flags.ignore_career_goal_sync = True
	doc.flags.ignore_version = True
	try:
		doc.save(ignore_permissions=True)
	except frappe.exceptions.TimestampMismatchError:
		frappe.clear_messages()
		pass
	frappe.clear_document_cache("EGS Student Participant", student_id)
	frappe.clear_cache(user="Guest")

	# Sync this stage advancement to the linked EGS Career Goal record
	career_goals = frappe.get_all(
		"EGS Career Goal",
		filters={"student_reference": doc.name},
	)
	if career_goals:
		for cg in career_goals:
			cg_doc = frappe.get_doc("EGS Career Goal", cg.name)
			cg_doc.reload()
			cg_doc.current_5ds_stage = "DEVELOP/PREPARE"
			cg_doc.flags.ignore_student_sync = True
			cg_doc.flags.ignore_version = True
			try:
				cg_doc.save(ignore_permissions=True)
			except frappe.exceptions.TimestampMismatchError:
				frappe.clear_messages()
				pass
	else:
		cg_doc = frappe.get_doc({
			"doctype": "EGS Career Goal",
			"student_reference": doc.name,
			"finalized_career_goal": doc.final_chosen_career_goal,
			"current_5ds_stage": "DEVELOP/PREPARE",
			"deadline": doc.date_of_decision or frappe.utils.today(),
			"personal_vision_statement": doc.personal_vision_statement or "",
			"a_promise_to_self": getattr(doc, "a_promise_to_self", None) or "",
		})
		cg_doc.flags.ignore_student_sync = True
		cg_doc.insert(ignore_permissions=True)

	frappe.db.commit()
	return {
		"status": "success",
		"message": _("Congratulations! You have advanced to Stage 4: DEVELOP."),
		"current_5ds_stage": "DEVELOP/PREPARE",
	}


@frappe.whitelist(allow_guest=True)
def add_egs_commitment(student_id, token, data):
	if not student_id or not token:
		frappe.throw(_("Missing required parameters."), frappe.PermissionError)

	doc = frappe.get_doc("EGS Student Participant", student_id)
	if doc.access_token != token:
		frappe.throw(_("Invalid access token."), frappe.PermissionError)

	import json
	if isinstance(data, str):
		try:
			data = json.loads(data)
		except Exception:
			data = {}

	action_required = data.get("action_required")
	due_date = data.get("due_date")
	status = data.get("status") or data.get("progress_status") or "Pending"
	reported_barrier = data.get("reported_barrier")

	if not action_required or not action_required.strip():
		frappe.throw(_("Action Required is mandatory."))
	if not due_date:
		frappe.throw(_("Due Date is mandatory."))

	# Find or create linked EGS Career Goal
	career_goals = frappe.get_all(
		"EGS Career Goal",
		filters={"student_reference": doc.name},
		order_by="creation desc",
		limit=1,
	)
	if career_goals:
		career_goal_name = career_goals[0].name
	else:
		if not doc.final_chosen_career_goal:
			frappe.throw(_("Cannot create commitment without a finalized career goal."))
		cg_doc = frappe.get_doc({
			"doctype": "EGS Career Goal",
			"student_reference": doc.name,
			"finalized_career_goal": doc.final_chosen_career_goal,
			"current_5ds_stage": getattr(doc, "current_5ds_stage", None) or "DEVELOP/PREPARE",
			"deadline": doc.date_of_decision or frappe.utils.today(),
			"personal_vision_statement": doc.personal_vision_statement or "",
			"a_promise_to_self": getattr(doc, "a_promise_to_self", None) or "",
		})
		cg_doc.flags.ignore_student_sync = True
		cg_doc.insert(ignore_permissions=True)
		career_goal_name = cg_doc.name

	commitment = frappe.get_doc({
		"doctype": "EGS Commitment",
		"career_goal_reference": career_goal_name,
		"action_required": action_required.strip(),
		"due_date": due_date,
		"progress_status": status,
		"reported_barrier": reported_barrier.strip() if reported_barrier else None,
	})
	commitment.insert(ignore_permissions=True)
	frappe.db.commit()

	return {
		"status": "success",
		"message": _("Action commitment added successfully!"),
		"name": commitment.name,
	}


@frappe.whitelist(allow_guest=True)
def step_back_stage(student_id, token, target_stage):
	if not student_id or not token:
		frappe.throw(_("Missing required parameters."), frappe.PermissionError)

	doc = frappe.get_doc("EGS Student Participant", student_id)
	if doc.access_token != token:
		frappe.throw(_("Invalid access token."), frappe.PermissionError)

	doc.reload()

	target_stage = (target_stage or "").strip()
	if target_stage not in ("DECIDE", "DEVELOP", "DEVELOP/PREPARE"):
		frappe.throw(_("Invalid target stage for stepping back: {0}").format(target_stage))

	if target_stage == "DECIDE":
		doc.current_5ds_stage = "DECIDE"
		doc.flags.ignore_career_goal_sync = True
		doc.flags.ignore_version = True
		try:
			doc.save(ignore_permissions=True)
		except frappe.exceptions.TimestampMismatchError:
			frappe.clear_messages()
			pass

		# Sync linked EGS Career Goal
		career_goals = frappe.get_all(
			"EGS Career Goal",
			filters={"student_reference": doc.name},
		)
		for cg in career_goals:
			cg_doc = frappe.get_doc("EGS Career Goal", cg.name)
			cg_doc.reload()
			cg_doc.current_5ds_stage = "DECIDE"
			cg_doc.flags.ignore_student_sync = True
			cg_doc.flags.ignore_version = True
			try:
				cg_doc.save(ignore_permissions=True)
			except frappe.exceptions.TimestampMismatchError:
				frappe.clear_messages()
				pass

			# Wipe all EGS Commitment records linked to this career goal to ensure a clean slate
			commitments = frappe.get_all("EGS Commitment", filters={"career_goal_reference": cg.name})
			for com in commitments:
				frappe.delete_doc("EGS Commitment", com.name, ignore_permissions=True, force=True)

	elif target_stage in ("DEVELOP", "DEVELOP/PREPARE"):
		doc.current_5ds_stage = "DEVELOP/PREPARE"
		doc.flags.ignore_career_goal_sync = True
		doc.flags.ignore_version = True
		try:
			doc.save(ignore_permissions=True)
		except frappe.exceptions.TimestampMismatchError:
			frappe.clear_messages()
			pass

		# Sync linked EGS Career Goal
		career_goals = frappe.get_all(
			"EGS Career Goal",
			filters={"student_reference": doc.name},
		)
		for cg in career_goals:
			cg_doc = frappe.get_doc("EGS Career Goal", cg.name)
			cg_doc.reload()
			cg_doc.current_5ds_stage = "DEVELOP/PREPARE"
			cg_doc.flags.ignore_student_sync = True
			cg_doc.flags.ignore_version = True
			try:
				cg_doc.save(ignore_permissions=True)
			except frappe.exceptions.TimestampMismatchError:
				frappe.clear_messages()
				pass

		# Wipe any EGS Accomplishment records if they exist for this student
		accomplishments = frappe.get_all(
			"EGS Accomplishment",
			filters={"student_reference": doc.name},
		)
		for acc in accomplishments:
			frappe.delete_doc("EGS Accomplishment", acc.name, ignore_permissions=True, force=True)

	frappe.clear_document_cache("EGS Student Participant", student_id)
	frappe.clear_cache(user="Guest")
	frappe.db.commit()

	return {
		"status": "success",
		"message": _("Successfully returned to Stage: {0}.").format(target_stage),
		"current_5ds_stage": doc.current_5ds_stage,
	}


@frappe.whitelist(allow_guest=True)
def advance_to_deliver(student_id, token):
	if not student_id or not token:
		frappe.throw(_("Missing required parameters."), frappe.PermissionError)

	doc = frappe.get_doc("EGS Student Participant", student_id)
	if doc.access_token != token:
		frappe.throw(_("Invalid access token."), frappe.PermissionError)

	doc.reload()

	if not doc.final_chosen_career_goal:
		frappe.throw(_("Cannot advance to Stage 5 without a finalized career goal in Stage 3 (DECIDE)."))

	doc.current_5ds_stage = "DELIVER"
	doc.flags.ignore_career_goal_sync = True
	doc.flags.ignore_version = True
	try:
		doc.save(ignore_permissions=True)
	except frappe.exceptions.TimestampMismatchError:
		frappe.clear_messages()
		pass
	frappe.clear_document_cache("EGS Student Participant", student_id)
	frappe.clear_cache(user="Guest")

	# Sync this stage advancement to the linked EGS Career Goal record
	career_goals = frappe.get_all(
		"EGS Career Goal",
		filters={"student_reference": doc.name},
	)
	if career_goals:
		for cg in career_goals:
			cg_doc = frappe.get_doc("EGS Career Goal", cg.name)
			cg_doc.reload()
			cg_doc.current_5ds_stage = "DELIVER"
			cg_doc.flags.ignore_student_sync = True
			cg_doc.flags.ignore_version = True
			try:
				cg_doc.save(ignore_permissions=True)
			except frappe.exceptions.TimestampMismatchError:
				frappe.clear_messages()
				pass
	else:
		cg_doc = frappe.get_doc({
			"doctype": "EGS Career Goal",
			"student_reference": doc.name,
			"finalized_career_goal": doc.final_chosen_career_goal,
			"current_5ds_stage": "DELIVER",
			"deadline": doc.date_of_decision or frappe.utils.today(),
			"personal_vision_statement": doc.personal_vision_statement or "",
			"a_promise_to_self": getattr(doc, "a_promise_to_self", None) or "",
		})
		cg_doc.flags.ignore_student_sync = True
		cg_doc.insert(ignore_permissions=True)

	frappe.db.commit()
	return {
		"status": "success",
		"message": _("Congratulations! You have advanced to Stage 5: DELIVER."),
		"current_5ds_stage": "DELIVER",
	}


def calculate_success_framework_score(student_doc):
	"""
	Calculates the Student Success Framework Index (0-100%) based on the 3-tier matrix:
	- Tier 1: Student Micro Check-in / Habits (Daily newspaper, Routine, Skills, PYQ, Peer forum) -> Up to 35 pts
	- Tier 2: System Activity (Checked-in, 5 goals saved, narrow goals selected, APSWB session registered, DECIDE reached) -> Up to 35 pts
	- Tier 3: DB Career Coordinator Evaluation (Clarity, Discipline, Mindset - 1-5 scale) -> Up to 30 pts
	"""
	score = 0

	# --- Tier 1: Habits & Self-Assessment (35 pts max) ---
	# 1. Daily newspaper reading: 7 pts
	if getattr(student_doc, "sf_daily_newspaper", 0):
		score += 7
	# 2. Time management & routine discipline: rating 1 to 5 -> 7 pts max
	routine_val = int(getattr(student_doc, "sf_routine_discipline", 3) or 3)
	score += round((routine_val / 5.0) * 7)
	# 3. Skill & AI acquisition: 7 pts
	if getattr(student_doc, "sf_skill_learning", None):
		score += 7
	# 4. PYQ / Syllabus / Strengths reviewed: 7 pts
	if getattr(student_doc, "sf_pyq_syllabus_reviewed", 0):
		score += 7
	# 5. Peer forum participation: 7 pts
	if getattr(student_doc, "sf_peer_forum_active", 0):
		score += 7

	# --- Tier 2: Objective Milestones (35 pts max) ---
	# Event Check-in verified: 7 pts
	if student_doc.event_status == "Checked-In":
		score += 7
	# 5 goals selected: 7 pts
	choices_count = frappe.db.count("EGS Student Career Choice", {"parent": student_doc.name})
	if choices_count >= 5:
		score += 7
	# Registered with Career Coordinator / Narrowed goals in DISCOVER: 7 pts
	if getattr(student_doc, "chosen_career_domain", None) or getattr(student_doc, "narrow_goal_1", None):
		score += 7
	# Attended / registered for APSWB online sessions: 7 pts
	has_session_reg = frappe.db.exists("EGS Session Registration", {"student": student_doc.name}) or getattr(student_doc, "ap_session_registered", 0)
	if has_session_reg:
		score += 7
	# Advanced to DECIDE or beyond: 7 pts
	if student_doc.current_5ds_stage in ("DECIDE", "DEVELOP", "DEVELOP/PREPARE", "DELIVER"):
		score += 7

	# --- Tier 3: Coordinator Qualitative Review (30 pts max) ---
	c_clarity = int(getattr(student_doc, "sf_coordinator_clarity", 3) or 3)
	c_discipline = int(getattr(student_doc, "sf_coordinator_discipline", 3) or 3)
	c_mindset = int(getattr(student_doc, "sf_coordinator_mindset", 3) or 3)
	score += round((c_clarity / 5.0) * 10)
	score += round((c_discipline / 5.0) * 10)
	score += round((c_mindset / 5.0) * 10)

	return min(max(int(score), 0), 100)


@frappe.whitelist(allow_guest=True)
def submit_success_framework_eval(student_id, access_key, daily_newspaper=0, routine_discipline=3, skill_learning="", pyq_syllabus_reviewed=0, peer_forum_active=0):
	"""
	Submits student monthly self-evaluation against the 5 Factors Success Framework.
	Updates EGS Student Participant and logs entry in EGS Check-in Log.
	"""
	student = frappe.db.get_value("EGS Student Participant", student_id, ["name", "access_token"], as_dict=True)
	if not student or student.access_token != access_key:
		frappe.throw(_("Invalid or expired credentials."), frappe.PermissionError)

	doc = frappe.get_doc("EGS Student Participant", student_id)
	doc.sf_daily_newspaper = 1 if int(daily_newspaper or 0) else 0
	doc.sf_routine_discipline = int(routine_discipline or 3)
	doc.sf_skill_learning = (skill_learning or "").strip()
	doc.sf_pyq_syllabus_reviewed = 1 if int(pyq_syllabus_reviewed or 0) else 0
	doc.sf_peer_forum_active = 1 if int(peer_forum_active or 0) else 0
	doc.sf_last_evaluated_date = frappe.utils.today()

	new_score = calculate_success_framework_score(doc)
	doc.success_framework_score = new_score

	# Update database directly via db.set_value to ensure custom schema columns persist without DocType meta mismatch
	frappe.db.set_value(
		"EGS Student Participant",
		student_id,
		{
			"sf_daily_newspaper": 1 if int(daily_newspaper or 0) else 0,
			"sf_routine_discipline": int(routine_discipline or 3),
			"sf_skill_learning": (skill_learning or "").strip(),
			"sf_pyq_syllabus_reviewed": 1 if int(pyq_syllabus_reviewed or 0) else 0,
			"sf_peer_forum_active": 1 if int(peer_forum_active or 0) else 0,
			"sf_last_evaluated_date": frappe.utils.today(),
			"success_framework_score": new_score,
		},
		update_modified=True,
	)

	# Log check-in record
	try:
		existing_logs = frappe.get_all("EGS Check-in Log", filters={"student_reference": student_id}, fields=["check_in_round"], order_by="check_in_round desc", limit=1)
		next_round = (existing_logs[0].check_in_round + 1) if existing_logs else 1
		
		# Insert log record and update SF metrics
		log_name = frappe.db.sql(
			"""
			INSERT INTO `tabEGS Check-in Log`
			(name, creation, modified, modified_by, owner, docstatus, idx, student_reference, check_in_round, timestamp, triage_route, student_response, daily_newspaper, routine_discipline, skill_learning, pyq_syllabus_reviewed, peer_forum_active, framework_self_score)
			VALUES (%s, NOW(6), NOW(6), 'Administrator', 'Administrator', 0, 0, %s, %s, NOW(6), %s, %s, %s, %s, %s, %s, %s, %s)
			""",
			(
				f"LOG-{frappe.utils.now()[:4][-2:]}-{random.randint(1000, 9999)}",
				student_id,
				next_round,
				"On track" if new_score >= 60 else "Stuck",
				"Still deciding" if doc.current_5ds_stage in ("DREAM", "DISCOVER") else "Yes decided",
				1 if int(daily_newspaper or 0) else 0,
				int(routine_discipline or 3),
				(skill_learning or "").strip(),
				1 if int(pyq_syllabus_reviewed or 0) else 0,
				1 if int(peer_forum_active or 0) else 0,
				new_score,
			)
		)
	except Exception:
		pass

	frappe.clear_document_cache("EGS Student Participant", student_id)
	frappe.clear_cache(user="Guest")
	frappe.db.commit()

	return {
		"status": "success",
		"message": _("Your Success Framework evaluation has been saved! Current Score: {0}%").format(new_score),
		"score": new_score,
	}




