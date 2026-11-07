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


def process_student_checkin(doc):
	event = None
	if doc.event:
		event = frappe.get_doc("EGS Event", doc.event)
	elif doc.city:
		from dreambig_egs.dreambig_egs.doctype.egs_event.egs_event import get_open_events_by_city
		open_events = get_open_events_by_city(doc.city)
		if open_events:
			doc.event = open_events[0].name
			event = frappe.get_doc("EGS Event", doc.event)

	# 1. Digital check-in validation
	if event and not event.allow_digital_checkins:
		frappe.throw(
			_("Digital check-ins are not enabled for this event."),
			frappe.ValidationError,
		)

	already_checked_in = (doc.event_status == "Checked-In")
	doc.event_status = "Checked-In"
	doc.physical_attendance = 1
	if getattr(doc, "current_5ds_stage", None) in (None, "", "DREAM"):
		doc.current_5ds_stage = "DISCOVER"

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

	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"status": "success",
		"message": "Your career goals have been updated successfully!",
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



