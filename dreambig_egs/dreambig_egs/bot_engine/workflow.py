# Copyright (c) 2026, Dream Big and contributors
# For license information, please see license.txt

import re
import frappe
from frappe import _
from frappe.utils import get_url, now_datetime, getdate, today
from dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant import (
	submit_decide_stage,
	advance_to_develop,
	advance_to_deliver,
	add_egs_commitment,
	revert_5ds_stage,
	step_back_stage,
	process_student_checkin,
	get_cohort_whatsapp_link,
	get_all_career_pathways,
	submit_success_framework_eval,
	calculate_success_framework_score,
)
from dreambig_egs.bot_engine.provider import BaseMessagingProvider


def find_student_by_identifier(query: str):
	"""
	Locates an EGS Student Participant using Student ID, access token, email, or phone.
	"""
	if not query:
		return None
	query = query.strip()

	# 1. Exact Student ID
	if frappe.db.exists("EGS Student Participant", query):
		return frappe.get_doc("EGS Student Participant", query)

	# 2. Access Token
	students = frappe.get_all("EGS Student Participant", filters={"access_token": query}, limit=1)
	if students:
		return frappe.get_doc("EGS Student Participant", students[0].name)

	# 3. Email
	students = frappe.get_all("EGS Student Participant", filters={"student_email": query}, limit=1)
	if students:
		return frappe.get_doc("EGS Student Participant", students[0].name)

	# 4. Phone
	cleaned_phone = re.sub(r"\D", "", query)
	if len(cleaned_phone) >= 10:
		phone_10 = cleaned_phone[-10:]
		students = frappe.get_all(
			"EGS Student Participant",
			filters={"phone_number": ["like", f"%{phone_10}"]},
			limit=1,
		)
		if students:
			return frappe.get_doc("EGS Student Participant", students[0].name)

	return None


def assign_coordinator_for_student(student_doc):
	"""
	Finds the most relevant EGS Coordinator for the student based on
	institution, then city, then general coordinators.
	"""
	# Match by Institution
	if getattr(student_doc, "university_college", None):
		coords = frappe.get_all(
			"EGS Coordinator",
			filters={"institution": student_doc.university_college},
			limit=1,
		)
		if coords:
			return coords[0].name

	# Match by City
	if getattr(student_doc, "city", None):
		coords = frappe.get_all(
			"EGS Coordinator",
			filters={"city": student_doc.city},
			limit=1,
		)
		if coords:
			return coords[0].name

	# Fallback to any coordinator
	coords = frappe.get_all("EGS Coordinator", limit=1)
	return coords[0].name if coords else None


def create_escalation_ticket_for_student(student_doc, reason="Student requested assistance via 5Ds chatbot"):
	"""
	Automated Support & Escalate cycle:
	Creates an EGS Check-in Log ('Stuck' triage) and triggers an EGS Escalation Ticket.
	"""
	coordinator_name = assign_coordinator_for_student(student_doc)

	# Check-in round counter
	round_count = frappe.db.count("EGS Check-in Log", {"student_reference": student_doc.name}) + 1

	checkin_log = frappe.get_doc({
		"doctype": "EGS Check-in Log",
		"student_reference": student_doc.name,
		"check_in_round": round_count,
		"timestamp": now_datetime(),
		"triage_route": "Stuck",
		"student_response": "I need help",
		"next_dated_action": "Escalated to Career Coordinator",
	})
	checkin_log.insert(ignore_permissions=True)

	ticket = frappe.get_doc({
		"doctype": "EGS Escalation Ticket",
		"student_reference": student_doc.name,
		"triggering_check_in": checkin_log.name,
		"escalation_route": "Stuck",
		"assigned_coordinator": coordinator_name,
		"status": "Open",
		"resolution_notes": reason,
	})
	ticket.insert(ignore_permissions=True)
	frappe.db.commit()

	return ticket, coordinator_name


class EGS5DsWorkflowEngine:
	"""
	Platform-agnostic state machine executing the 'Track -> Nudge -> Support -> Escalate' cycle
	across all 5Ds stages using a standardized, button-driven interface with native contact sharing,
	seamless registration routing, complete Advance/Revert stage mechanics, in-bot profile view,
	universal Back navigation, and secure Logout.
	"""

	def __init__(self, session, provider: BaseMessagingProvider):
		self.session = session
		self.session.flags.ignore_version = True
		self.provider = provider
		self.chat_id = session.chat_id

	def set_conversation_state(self, new_state: str):
		"""
		Securely updates the conversation state in memory and database using update_modified=False.
		"""
		self.session.current_conversation_state = new_state
		self.session.flags.ignore_version = True
		if self.session.name:
			frappe.db.set_value(
				"EGS Bot Session",
				self.session.name,
				"current_conversation_state",
				new_state,
				update_modified=False,
			)

	def process_message(self, message_data: dict):
		text = (message_data.get("text") or "").strip()
		payload = (message_data.get("payload") or "").strip()
		low_text = text.lower()
		norm_input = (payload or text).strip().upper()

		# Update last interaction
		self.session.last_interaction = now_datetime()

		# Load student participant if linked
		student = None
		if self.session.student_participant:
			student = frappe.get_doc("EGS Student Participant", self.session.student_participant)

		# 1. Logout Handler
		if norm_input in ("LOGOUT", "LOG_OUT", "🚪 LOGOUT") or low_text in ("/logout", "logout", "log out"):
			self.handle_logout(student)
			return

		# 2. Universal Back Handler
		if norm_input in ("BACK_TO_MENU", "BACK", "STAGE_MENU", "DEVELOP_MENU", "⏪ BACK TO MENU", "⏪ BACK") or low_text in ("/menu", "menu", "back", "/back"):
			self.session.clear_context()
			self.set_conversation_state("IDLE")
			self.session.save(ignore_permissions=True)
			if student:
				student.reload()
				self.trigger_stage_prompt(student)
			else:
				self.handle_unlinked_session(text, payload)
			return

		# 3. In-Bot "My Profile" Handler (replaces external web dashboard links)
		if norm_input in ("VIEW_PROFILE", "SHOW_PROFILE", "MY_PROFILE", "VIEW_DASHBOARD", "👤 MY PROFILE") or low_text in ("/profile", "profile", "/myprofile", "my profile", "/dashboard", "dashboard", "portal"):
			if student:
				self.show_my_profile(student)
			else:
				self.handle_unlinked_session(text, payload)
			return

		# 3.1 Event Check-in Handler
		if norm_input in ("EVENT_CHECKIN", "CHECK_IN", "CHECKIN", "📍 CHECK IN TO EVENT") or low_text in ("/checkin", "check in", "checkin"):
			if student:
				self.handle_event_checkin(student)
			else:
				self.handle_unlinked_session(text, payload)
			return

		# 3.2 Cohort Community Link Handler
		if norm_input in ("JOIN_COHORT", "COHORT_GROUP", "COHORT", "WHATSAPP_GROUP") or low_text in ("/cohort", "cohort", "group"):
			if student:
				cohort_res = get_cohort_whatsapp_link(student.name)
				if cohort_res and cohort_res.get("status") == "success" and cohort_res.get("link"):
					link = cohort_res["link"]
					buttons = [
						{"id": "OPEN_COHORT", "title": "👥 Open WhatsApp Group", "url": link},
						{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"},
					]
					self.provider.send_interactive_message(
						self.chat_id,
						f"👥 **Your Cohort Community WhatsApp Group**\n\n"
						f"Connect with your fellow First-Year peers in **{student.course}** (Cohort {student.cohort_year}) at **{student.university_college}**:\n\n"
						f"{link}",
						buttons,
					)
				else:
					buttons = [{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"}]
					self.provider.send_interactive_message(
						self.chat_id,
						"ℹ️ **Cohort WhatsApp Group Not Yet Assigned**\n\n"
						"Your institution or course coordinator will publish the WhatsApp group link soon. Check back or visit your profile!",
						buttons,
					)
			else:
				self.handle_unlinked_session(text, payload)
			return

		# 4. Unlinked session identification
		if not self.session.student_participant:
			self.handle_unlinked_session(text, payload)
			return

		# 5. Universal Command Handlers
		if low_text in ("/reset", "reset", "/restart"):
			self.set_conversation_state("IDLE")
			self.session.clear_context()
			self.session.save(ignore_permissions=True)
			self.trigger_stage_prompt(student, is_reset=True)
			return

		if low_text in ("/help", "help"):
			buttons = [
				{"id": "VIEW_PROFILE", "title": "👤 My Profile"},
				{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"},
			]
			self.provider.send_interactive_message(
				self.chat_id,
				"🤖 **DREAM BIG 5Ds Framework Assistant**\n\n"
				"I help you track, advance, and manage your complete career journey:\n"
				"• **Stage 1 (DREAM):** Registration & onboarding\n"
				"• **Stage 2 (DISCOVER):** Shortlist career paths and explore options\n"
				"• **Stage 3 (DECIDE):** Commit to goal, vision, and promise to self\n"
				"• **Stage 4 (DEVELOP):** Track dated preparation commitments\n"
				"• **Stage 5 (DELIVER):** Log verified accomplishments\n\n"
				"Commands:\n"
				"• `/profile` - View your student profile\n"
				"• `/menu` - Back to main stage menu\n"
				"• `/logout` - Securely log out from this session\n"
				"• `/reset` - Restart conversation menu",
				buttons,
			)
			self.session.save(ignore_permissions=True)
			return

		if low_text in ("/status", "status") or norm_input == "VIEW_STATUS":
			self.show_my_profile(student)
			return

		# 6. Route by conversation state first, then student's active 5Ds stage
		curr_state = (self.session.current_conversation_state or "IDLE").upper()
		active_stage = (student.current_5ds_stage or "DISCOVER").upper()

		if norm_input in ("SF_EVAL", "TAKE_SF_EVAL", "🌟 MONTHLY EVALUATION", "MONTHLY EVALUATION") or low_text in ("/eval", "/checkin", "eval", "evaluation") or "evaluation" in low_text:
			self.start_sf_evaluation(student)
			return

		if curr_state.startswith("SF_"):
			self.handle_sf_eval_flow(student, text, payload)
		elif curr_state.startswith("DECIDE_"):
			self.handle_decide_flow(student, text, payload)
		elif curr_state.startswith("DEVELOP_"):
			self.handle_develop_flow(student, text, payload)
		elif curr_state.startswith("DELIVER_"):
			self.handle_deliver_flow(student, text, payload)
		elif curr_state.startswith("DISCOVER_"):
			self.handle_discover_flow(student, text, payload)
		elif "DISCOVER" in active_stage:
			self.handle_discover_flow(student, text, payload)
		elif "DECIDE" in active_stage:
			self.handle_decide_flow(student, text, payload)
		elif "DEVELOP" in active_stage:
			self.handle_develop_flow(student, text, payload)
		elif "DELIVER" in active_stage:
			self.handle_deliver_flow(student, text, payload)
		else:
			self.handle_discover_flow(student, text, payload)

		self.session.save(ignore_permissions=True)

	# --- IN-BOT PROFILE VIEW ---
	def show_my_profile(self, student):
		"""
		Formats an in-bot rich text card replicating the portal's top dashboard card:
		- Name: student.student_name
		- Academic: student.course (Cohort student.cohort_year) • student.university_college
		- ID: student.name
		- Active Stage: student.current_5ds_stage
		- Event Status & Food Coupon (if checked in)
		- Cohort WhatsApp group link (if available)
		- Goal (if DECIDE or later): student.final_chosen_career_goal
		Sends this profile message with [⏪ Back to Menu] and [🚪 Logout].
		"""
		student.reload()
		stage = student.current_5ds_stage or "DISCOVER"
		stage_upper = stage.upper()

		academic_info = f"{student.course or 'Course'} (Cohort {student.cohort_year or '2026'}) • {student.university_college or 'Institution'}"

		event_line = f"\n• **Event Status:** {student.event_status or 'Registered'}"
		if student.food_coupon_code:
			event_line += f" (🍽️ Meal Coupon: `{student.food_coupon_code}`)"

		# Cohort WhatsApp group link
		cohort_res = get_cohort_whatsapp_link(student.name)
		cohort_link = cohort_res.get("link") if cohort_res and cohort_res.get("status") == "success" else None
		cohort_line = f"\n• **Cohort Community:** [Join WhatsApp Group]({cohort_link})" if cohort_link else ""

		goal_line = ""
		if any(st in stage_upper for st in ("DECIDE", "DEVELOP", "DELIVER")) or student.final_chosen_career_goal:
			goal_val = student.final_chosen_career_goal or "Pending Commitment"
			goal_line = f"\n• **Goal:** {goal_val}"

		profile_msg = (
			f"👤 **My Profile & Dashboard**\n\n"
			f"• **Name:** {student.student_name}\n"
			f"• **Academic:** {academic_info}\n"
			f"• **ID:** `{student.name}`\n"
			f"• **Active Stage:** {stage}"
			f"{event_line}"
			f"{cohort_line}"
			f"{goal_line}"
		)

		buttons = []
		portal_app_url = f"{get_url()}/my-dream-big?id={student.name}&key={student.access_token}"
		buttons.append({"id": "OPEN_DASHBOARD_APP", "title": "📱 Open Dashboard App", "web_app": portal_app_url})
		if cohort_link:
			buttons.append({"id": "JOIN_COHORT", "title": "👥 Join Cohort Group", "url": cohort_link})
		if student.event_status != "Checked-In":
			buttons.append({"id": "EVENT_CHECKIN", "title": "📍 Check In to Event"})
		buttons.append({"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"})
		buttons.append({"id": "LOGOUT", "title": "🚪 Logout"})

		self.set_conversation_state("VIEWING_PROFILE")
		self.session.save(ignore_permissions=True)
		self.provider.send_interactive_message(self.chat_id, profile_msg, buttons)

	# --- SECURE LOGOUT ---
	def handle_logout(self, student=None):
		"""
		Securely logs out the user:
		- For Telegram: Clears telegram_chat_id on EGS Student Participant with update_modified=False
		- For Both Platforms: Clears session_data and sets current_conversation_state to LOGGED_OUT
		- Clears student_participant link on session
		- Sends confirmation message
		"""
		if student and self.session.platform == "Telegram":
			frappe.db.set_value(
				"EGS Student Participant",
				student.name,
				"telegram_chat_id",
				None,
				update_modified=False,
			)

		self.session.student_participant = None
		self.session.session_data = "{}"
		self.session.current_conversation_state = "LOGGED_OUT"
		self.session.flags.ignore_version = True

		if self.session.name:
			frappe.db.set_value(
				"EGS Bot Session",
				self.session.name,
				{
					"student_participant": None,
					"session_data": "{}",
					"current_conversation_state": "LOGGED_OUT",
				},
				update_modified=False,
			)
		frappe.db.commit()

		self.provider.send_text(
			self.chat_id,
			"You have been successfully logged out. Send 'Hi' or /start to log back in.",
		)

	# --- STAGE 1: DREAM / NEW USER REGISTRATION ROUTING ---
	def send_registration_prompt(self, phone: str = "", retry: bool = False):
		"""
		Sends welcoming message stating their number is not registered, accompanied by
		an inline URL button: '[📝 Register via Web]' and '[🔄 I have registered]'.
		Points directly to /egs-student-participant/new to avoid 301 redirects inside Telegram WebApp.
		"""
		reg_url = f"{get_url()}/egs-student-participant/new"
		phone_str = f" (`{phone}`)" if phone else ""

		if retry:
			msg = (
				f"⚠️ We couldn't find a completed registration for your number{phone_str} yet.\n\n"
				f"Please submit your registration on the web portal at:\n{reg_url}\n\n"
				"Then tap **🔄 I have registered** below:"
			)
		else:
			msg = (
				f"👋 Welcome to **EARLY GOAL SETTING: DREAM BIG**!\n\n"
				f"Your mobile number{phone_str} is not registered in our student records yet.\n\n"
				"Full registration includes choosing your City, Institution, and Faculty Department, "
				"which is easiest to complete on our web portal.\n\n"
				f"1️⃣ Register via Web:\n{reg_url}\n\n"
				"2️⃣ Once registered, return here and tap **🔄 I have registered** to start your 5Ds journey!"
			)

		buttons = [
			{"id": "REGISTER_WEB", "title": "📝 Register via Web", "url": reg_url},
			{"id": "I_HAVE_REGISTERED", "title": "🔄 I have registered"},
		]
		self.set_conversation_state("AWAITING_REGISTRATION")
		self.session.save(ignore_permissions=True)
		self.provider.send_interactive_message(self.chat_id, msg, buttons)

	def send_dream_menu(self, student):
		"""
		Menu for registered students who have not yet checked in to their event.
		Offers Digital Event Check-in, Cohort WhatsApp Community, Profile, and WebApp Links.
		"""
		student.reload()
		cohort_res = get_cohort_whatsapp_link(student.name)
		cohort_link = cohort_res.get("link") if cohort_res and cohort_res.get("status") == "success" else None

		event_name = "your registered DREAM BIG conference"
		if student.event:
			event_name = frappe.db.get_value("EGS Event", student.event, "event_name") or event_name

		msg = (
			f"🌟 **Stage 1: DREAM — Foundation & Aspiration**\n\n"
			f"Welcome, **{student.student_name}**!\n"
			f"• **Event:** {event_name}\n"
			f"• **Status:** {student.event_status or 'Registered'}\n\n"
			f"Your 5 DREAM BIG Career Goals (Exercise 2) will unlock upon event check-in."
		)

		buttons = []
		if student.event_status != "Checked-In":
			checkin_webapp_url = f"{get_url()}/event-checkin?id={student.name}&key={student.access_token}"
			buttons.append({"id": "EVENT_CHECKIN", "title": "📍 Check In to Event"})
			buttons.append({"id": "CHECKIN_WEBAPP", "title": "📱 Event Check-in WebApp", "web_app": checkin_webapp_url})
		if cohort_link:
			buttons.append({"id": "JOIN_COHORT", "title": "👥 Join Cohort Group", "url": cohort_link})
		buttons.append({"id": "VIEW_PROFILE", "title": "👤 My Profile"})

		self.set_conversation_state("IDLE")
		self.session.save(ignore_permissions=True)
		self.provider.send_interactive_message(self.chat_id, msg, buttons)

	def handle_event_checkin(self, student):
		"""
		Executes in-chat digital check-in for the student.
		Issues the digital food coupon (if event allows) and unlocks Stage 2: DISCOVER.
		"""
		try:
			student, already_checked_in, coupon_issued = process_student_checkin(student)
			student.reload()

			coupon_msg = ""
			if student.food_coupon_code:
				coupon_msg = (
					f"\n\n🍽️ **Digital Food Coupon Issued:**\n"
					f"`{student.food_coupon_code}`\n"
					f"*(Show this coupon code at the event lunch counter)*"
				)

			if already_checked_in:
				res_msg = (
					f"✅ **Already Checked In!**\n\n"
					f"You are checked in for your event.{coupon_msg}\n\n"
					f"Your 5 DREAM BIG Career Goals (Stage 2: DISCOVER) are active."
				)
			else:
				res_msg = (
					f"🎉 **Check-In Confirmed!**\n\n"
					f"Welcome to the event venue, **{student.student_name}**!{coupon_msg}\n\n"
					f"Stage 2: DISCOVER (Exercise 2) is now unlocked."
				)

			buttons = [
				{"id": "DISCOVER_VIEW_GOALS", "title": "📋 View Shortlist"},
				{"id": "DISCOVER_YES", "title": "① Yes, decided"},
				{"id": "VIEW_PROFILE", "title": "👤 My Profile"},
				{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"},
			]
			self.set_conversation_state("IDLE")
			self.session.save(ignore_permissions=True)
			self.provider.send_interactive_message(self.chat_id, res_msg, buttons)
		except Exception as e:
			frappe.log_error(f"In-bot event check-in failed: {e}", "Bot Event Check-in")
			self.provider.send_text(
				self.chat_id,
				f"⚠️ Check-in could not be completed: {e}\nPlease check with the registration desk.",
			)

	def handle_unlinked_session(self, text: str, payload: str):
		"""
		Handles unregistered users or users tapping '[🔄 I have registered]' to refresh their session.
		"""
		norm_input = (payload or text).strip().upper()
		ctx = self.session.get_context_data()
		phone_candidate = ctx.get("unregistered_phone")

		if not phone_candidate:
			cleaned = re.sub(r"\D", "", self.chat_id)
			if len(cleaned) >= 10:
				phone_candidate = cleaned[-10:]

		# Check if user taps "I have registered" or says "registered"
		if norm_input in ("I_HAVE_REGISTERED", "REFRESH_REGISTRATION", "🔄 I HAVE REGISTERED") or "registered" in text.lower():
			matched_student = None
			if phone_candidate:
				students = frappe.get_all(
					"EGS Student Participant",
					filters={"phone_number": ["like", f"%{phone_candidate}"]},
					limit=1,
				)
				if students:
					matched_student = frappe.get_doc("EGS Student Participant", students[0].name)

			# Also check by text if user typed email or ID
			if not matched_student and text:
				matched_student = find_student_by_identifier(text)

			if matched_student:
				if self.session.platform == "Telegram":
					frappe.db.set_value("EGS Student Participant", matched_student.name, "telegram_chat_id", self.chat_id, update_modified=False)
					frappe.db.commit()

				self.session.student_participant = matched_student.name
				self.session.clear_context()
				self.set_conversation_state("IDLE")
				self.session.save(ignore_permissions=True)

				self.provider.send_text(
					self.chat_id,
					f"🎉 Registration verified! Welcome **{matched_student.student_name}** to your **DREAM BIG Journey** (`{matched_student.name}`).",
				)
				self.trigger_stage_prompt(matched_student)
				return
			else:
				self.send_registration_prompt(phone=phone_candidate or "", retry=True)
				return

		# Default registration fallback
		self.send_registration_prompt(phone=phone_candidate or "")

	def trigger_stage_prompt(self, student, is_reset=False):
		"""
		Dispatches the appropriate interactive menu based on active 5Ds stage.
		"""
		student.reload()
		stage = (student.current_5ds_stage or "DREAM").upper()

		if student.event_status != "Checked-In" and stage in ("DREAM", ""):
			self.send_dream_menu(student)
		elif "DISCOVER" in stage or student.event_status == "Checked-In" and stage == "DREAM":
			self.send_discover_nudge(student)
		elif "DECIDE" in stage:
			self.send_decide_prompt(student)
		elif "DEVELOP" in stage:
			self.send_develop_menu(student)
		elif "DELIVER" in stage:
			self.send_deliver_menu(student)
		else:
			self.send_discover_nudge(student)

	# --- STAGE 2: DISCOVER FLOW ---
	def send_discover_nudge(self, student=None):
		self.set_conversation_state("DISCOVER_AWAITING_CHOICE")
		self.session.save(ignore_permissions=True)

		dashboard_webapp_url = (
			f"{get_url()}/my-dream-big?id={student.name}&key={student.access_token}"
			if student
			else f"{get_url()}/my-dream-big"
		)

		buttons = [
			{"id": "DISCOVER_YES", "title": "① Yes, decided"},
			{"id": "DISCOVER_VIEW_GOALS", "title": "📋 View Shortlist"},
			{"id": "DISCOVER_WEBAPP", "title": "📱 DISCOVER WebApp", "web_app": dashboard_webapp_url},
			{"id": "DISCOVER_STILL_EXPLORING", "title": "② Still exploring"},
			{"id": "DISCOVER_NEED_HELP", "title": "③ I need help"},
			{"id": "VIEW_PROFILE", "title": "👤 My Profile"},
		]
		self.provider.send_interactive_message(
			self.chat_id,
			"🧭 **Stage 2: DISCOVER — Career Shortlist**\n\n"
			"Are you ready to finalize your goal?\n\n"
			"① Yes, decided\n"
			"② Still exploring\n"
			"③ I need help",
			buttons,
		)

	def handle_discover_flow(self, student, text: str, payload: str):
		curr_state = self.session.current_conversation_state or "IDLE"
		norm_input = (payload or text).strip().upper()

		# Check for "View Shortlist"
		if norm_input in ("DISCOVER_VIEW_GOALS", "VIEW_SHORTLIST", "SHORTLIST", "📋 VIEW SHORTLIST") or "shortlist" in text.lower():
			student.reload()
			top_goals = [
				c.career_pathway for c in student.get("top_5_career_goals", []) if c.career_pathway
			]
			if top_goals:
				goals_text = "\n".join([f"• **{i+1}.** {g}" for i, g in enumerate(top_goals)])
				msg = (
					f"📋 **Your Selected Top {len(top_goals)} Career Goals (Exercise 2):**\n\n"
					f"{goals_text}\n\n"
					"You can finalize one of these goals for Stage 3: DECIDE."
				)
			else:
				msg = (
					"📋 **Your Career Shortlist:**\n\n"
					"You haven't selected your 5 career goals yet.\n"
					"Log in to the web portal or explore the 42 official pathways in your brochure!"
				)

			buttons = [
				{"id": "DISCOVER_YES", "title": "① Yes, decided"},
				{"id": "DISCOVER_NEED_HELP", "title": "③ I need help"},
				{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"},
			]
			self.provider.send_interactive_message(self.chat_id, msg, buttons)
			return

		# Check for "I need help" escalation
		if norm_input in ("DISCOVER_NEED_HELP", "3", "③ I NEED HELP") or "help" in text.lower() or "stuck" in text.lower():
			ticket, coord = create_escalation_ticket_for_student(
				student,
				reason="Student selected 'I need help' during DISCOVER stage chatbot follow-up.",
			)
			self.set_conversation_state("DISCOVER_ESCALATED")
			self.session.save(ignore_permissions=True)

			coord_msg = f" ({coord})" if coord else ""
			buttons = [
				{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"},
				{"id": "VIEW_PROFILE", "title": "👤 My Profile"},
			]
			self.provider.send_interactive_message(
				self.chat_id,
				f"🤝 **Support is on the way!**\n\n"
				f"An escalation ticket (`{ticket.name}`) has been generated and assigned to your "
				f"**DB Career Coordinator**{coord_msg}.\n\n"
				f"They will reach out to you directly to guide you through your career pathway options.",
				buttons,
			)
			return

		# Check for Success Framework Self-Evaluation trigger
		if norm_input in ("SF_EVAL", "TAKE_SF_EVAL", "🌟 MONTHLY EVALUATION", "MONTHLY EVALUATION") or "evaluation" in text.lower():
			self.start_sf_evaluation(student)
			return

		# Check for "Yes, decided" progression
		if norm_input in ("DISCOVER_YES", "1", "① YES, DECIDED") or "decided" in text.lower() or text.lower() == "yes":
			self.send_decide_prompt(student)
			return

		# Check for "Still exploring / Still deciding" nudge
		if norm_input in ("DISCOVER_STILL_EXPLORING", "DISCOVER_STILL_DECIDING", "2", "② STILL EXPLORING", "② STILL DECIDING") or "still" in text.lower():
			buttons = [
				{"id": "DISCOVER_YES", "title": "① Ready to decide"},
				{"id": "DISCOVER_VIEW_GOALS", "title": "📋 View Shortlist"},
				{"id": "DISCOVER_NEED_HELP", "title": "③ I need help"},
				{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"},
			]
			self.provider.send_interactive_message(
				self.chat_id,
				"💡 **Take your time exploring!**\n\n"
				"Careful consideration leads to confident decisions. Review your Top 5 Career choices or consult your brochure.\n\n"
				"Whenever you are ready, select an option below:",
				buttons,
			)
			return

		# Default: prompt with buttons
		self.send_discover_nudge(student)

	# --- STAGE 3: DECIDE FLOW ---
	def send_decide_prompt(self, student):
		student.reload()
		# If student has already committed in Stage 3 (DECIDE), show management menu with Advance/Revert
		decide_webapp_url = f"{get_url()}/egs-decide-stage?id={student.name}&key={student.access_token}"
		if student.current_5ds_stage == "DECIDE" and student.final_chosen_career_goal:
			buttons = [
				{"id": "PROCEED_TO_DEVELOP", "title": "🚀 Proceed to Stage 4: DEVELOP"},
				{"id": "DECIDE_WEBAPP", "title": "📱 DECIDE WebApp", "web_app": decide_webapp_url},
				{"id": "SF_EVAL", "title": "📝 Monthly Evaluation"},
				{"id": "REVERT_TO_DISCOVER", "title": "🔄 Re-evaluate Goal"},
				{"id": "VIEW_PROFILE", "title": "👤 My Profile"},
			]
			self.set_conversation_state("IDLE")
			self.session.save(ignore_permissions=True)
			self.provider.send_interactive_message(
				self.chat_id,
				f"🎯 **Stage 3: DECIDE — A Promise to Self**\n"
				f"*(Timeline: End of Year 1 / 1st Week of Year 2 - 2-Day Flagship Event)*\n\n"
				f"• **Single Finalized Goal:** {student.final_chosen_career_goal}\n"
				f"• **Vision Statement (The 'Why', Inspiration & Impact):**\n"
				f"  \"{student.personal_vision_statement or 'Not recorded'}\"\n"
				f"• **Promise to Self:**\n"
				f"  \"{student.a_promise_to_self or 'Not recorded'}\"\n\n"
				f"Select an action to proceed with your journey, open your DECIDE WebApp, or re-evaluate:",
				buttons,
			)
			return

		# Fetch student's top_5_career_goals from their profile
		top_goals = [
			c.career_pathway for c in student.get("top_5_career_goals", []) if c.career_pathway
		]

		self.set_conversation_state("DECIDE_AWAITING_GOAL")
		self.session.clear_context()

		if top_goals:
			self.session.update_context({"shortlisted_goals": top_goals})
			self.session.save(ignore_permissions=True)

			buttons = []
			for idx, goal in enumerate(top_goals[:5]):
				buttons.append({
					"id": f"GOAL_{idx}",
					"title": goal[:20],
					"payload": goal,
				})
			buttons.append({"id": "DECIDE_WEBAPP", "title": "📱 DECIDE WebApp", "web_app": decide_webapp_url})
			buttons.append({"id": "REVERT_TO_DISCOVER", "title": "⏪ Revert to DISCOVER"})
			buttons.append({"id": "VIEW_PROFILE", "title": "👤 My Profile"})

			self.provider.send_interactive_message(
				self.chat_id,
				"🎯 **Stage 3: DECIDE — A Promise to Self**\n\n"
				"Please select your **Final Chosen Career Goal** from your shortlisted choices below:",
				buttons,
			)
		else:
			self.session.save(ignore_permissions=True)
			self.provider.send_text(
				self.chat_id,
				"🎯 **Stage 3: DECIDE — A Promise to Self**\n\n"
				"Please reply with your **Final Chosen Career Goal**\n"
				"(e.g., Artificial Intelligence & Robotics, Civil Services, Chartered Accountancy, Biotech Engineering):",
			)

	def handle_decide_flow(self, student, text: str, payload: str):
		curr_state = self.session.current_conversation_state or "IDLE"
		norm_input = (payload or text).strip().upper()

		# 1. Revert to DISCOVER trigger
		if norm_input in ("REVERT_TO_DISCOVER", "⏪ REVERT TO DISCOVER") or "revert to discover" in text.lower():
			self.set_conversation_state("DECIDE_AWAITING_REVERT_REASON")
			self.session.save(ignore_permissions=True)
			buttons = [{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"}]
			self.provider.send_interactive_message(
				self.chat_id,
				"⏪ **Reverting to Stage 2: DISCOVER**\n\n"
				"Please type and reply with your **reason for changing your career path**\n"
				"*(e.g., Realized stronger interest in Data Science rather than Civil Services)*:",
				buttons,
			)
			return

		# 2. Awaiting reason for Revert to DISCOVER
		if curr_state == "DECIDE_AWAITING_REVERT_REASON":
			reason_text = text.strip()
			if not reason_text:
				self.provider.send_text(
					self.chat_id,
					"Please provide a reason for changing your career path to complete the reversion:",
				)
				return

			try:
				revert_5ds_stage(
					student_id=student.name,
					reason=reason_text,
					token=student.access_token,
				)
				student.reload()
				self.session.clear_context()
				self.set_conversation_state("IDLE")
				self.session.save(ignore_permissions=True)

				self.provider.send_text(
					self.chat_id,
					f"✅ **Successfully returned to Stage 2: DISCOVER.**\n\n"
					f"Your reason has been recorded:\n\"{reason_text}\"\n\n"
					f"Stage 3 fields and career goal records have been cleanly reset. You may now re-evaluate your career shortlist.",
				)
				self.send_discover_nudge(student)
			except Exception as e:
				frappe.log_error(f"Revert to DISCOVER failed: {e}", "Bot Workflow DECIDE")
				self.provider.send_text(self.chat_id, f"⚠️ Unable to revert: {e}\nType `/reset` to retry.")
			return

		# 3. Advance to Stage 4 (DEVELOP) trigger
		if norm_input in ("PROCEED_TO_DEVELOP", "PROCEED TO STAGE 4: DEVELOP", "🚀 PROCEED TO STAGE 4: DEVELOP", "PROCEED TO DEVELOP"):
			try:
				advance_to_develop(student_id=student.name, token=student.access_token)
				student.reload()
				self.session.clear_context()
				self.set_conversation_state("IDLE")
				self.session.save(ignore_permissions=True)

				self.provider.send_text(
					self.chat_id,
					"🚀 **Congratulations! You have advanced to Stage 4: DEVELOP.**\n\n"
					"Now let's build your action plan and commit to dated milestones!",
				)
				self.send_develop_menu(student)
			except Exception as e:
				frappe.log_error(f"Advance to DEVELOP failed: {e}", "Bot Workflow DECIDE")
				self.provider.send_text(self.chat_id, f"⚠️ Unable to advance: {e}\nType `/reset` to retry.")
			return

		# 4. Awaiting Goal Selection
		if curr_state == "DECIDE_AWAITING_GOAL":
			ctx = self.session.get_context_data()
			chosen_goal = None

			if payload.startswith("GOAL_"):
				try:
					idx = int(payload.split("_")[1])
					goals = ctx.get("shortlisted_goals", [])
					if idx < len(goals):
						chosen_goal = goals[idx]
				except Exception:
					pass

			if not chosen_goal:
				chosen_goal = (payload or text).strip()

			if not chosen_goal:
				self.send_decide_prompt(student)
				return

			self.session.update_context({"pending_goal": chosen_goal})
			self.set_conversation_state("DECIDE_AWAITING_VISION")
			self.session.save(ignore_permissions=True)

			buttons = [{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"}]
			self.provider.send_interactive_message(
				self.chat_id,
				f"🌟 Target Goal: **{chosen_goal}**\n\n"
				f"Now, please write and reply with your **Personal Vision Statement**:\n"
				f"*(Where do you see yourself, what impact do you want to create, and why is this your aspiration?)*",
				buttons,
			)
			return

		# 5. Awaiting Vision Statement
		if curr_state == "DECIDE_AWAITING_VISION":
			vision_text = text.strip()
			if not vision_text:
				self.provider.send_text(
					self.chat_id,
					"Please reply with your **Personal Vision Statement** to continue your DECIDE commitment:",
				)
				return

			self.session.update_context({"pending_vision": vision_text})
			self.set_conversation_state("DECIDE_AWAITING_PROMISE")
			self.session.save(ignore_permissions=True)

			buttons = [{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"}]
			self.provider.send_interactive_message(
				self.chat_id,
				"✍️ Inspiring vision!\n\n"
				"Now, please write and reply with **A Promise to Self**:\n"
				"*(What personal commitment do you make to yourself to persevere and achieve this goal?)*",
				buttons,
			)
			return

		# 6. Awaiting Promise to Self
		if curr_state == "DECIDE_AWAITING_PROMISE":
			promise_text = text.strip()
			ctx = self.session.get_context_data()
			vision_text = ctx.get("pending_vision") or promise_text
			if not promise_text:
				promise_text = vision_text

			chosen_goal = ctx.get("pending_goal") or student.final_chosen_career_goal or "General Pathway"

			try:
				submit_decide_stage(
					student_id=student.name,
					token=student.access_token,
					final_chosen_career_goal=chosen_goal,
					personal_vision_statement=vision_text,
					a_promise_to_self=promise_text,
					date_of_decision=today(),
				)

				advance_to_develop(
					student_id=student.name,
					token=student.access_token,
				)

				student.reload()
				self.session.clear_context()
				self.set_conversation_state("IDLE")
				self.session.save(ignore_permissions=True)

				self.provider.send_text(
					self.chat_id,
					f"🚀 **Stage 3 Complete! You have advanced to Stage 4: DEVELOP.**\n\n"
					f"• **Career Goal:** {chosen_goal}\n"
					f"• **Vision:** \"{vision_text}\"\n"
					f"• **Promise to Self:** \"{promise_text}\"\n\n"
					f"Now let's build your action plan!",
				)
				self.send_develop_menu(student)
			except Exception as e:
				frappe.log_error(f"DECIDE transition failed in bot workflow: {e}", "Bot Workflow DECIDE")
				self.provider.send_text(
					self.chat_id,
					f"⚠️ We encountered an issue saving your DECIDE commitment: {e}\n"
					f"Please type `/reset` to try again.",
				)
			return

		# Default Stage 3 Prompt
		self.send_decide_prompt(student)

	# --- STAGE 4: DEVELOP FLOW ---
	def send_develop_menu(self, student):
		"""
		Stage 4 Menu: [Add Milestone], [Daily Routine Check], [Structured Mentoring], [Update Progress], [Proceed to DELIVER], [Refine Goal], [👤 My Profile], [Need Help].
		"""
		develop_webapp_url = f"{get_url()}/my-dream-big?id={student.name}&key={student.access_token}#develop"
		checkin_log_url = f"{get_url()}/egs-check-in-log?id={student.name}&key={student.access_token}"
		buttons = [
			{"id": "DEVELOP_ADD_ACTION", "title": "➕ Add Milestone"},
			{"id": "SF_EVAL", "title": "⏰ Daily Routine & SF"},
			{"id": "DEVELOP_VIEW_MENTORING", "title": "🧭 Mentoring & Academies"},
			{"id": "DEVELOP_UPDATE_PROGRESS", "title": "Update Progress"},
			{"id": "DEVELOP_WEBAPP", "title": "📱 DEVELOP WebApp", "web_app": develop_webapp_url},
			{"id": "PROCEED_TO_DELIVER", "title": "🚀 Proceed to Stage 5: DELIVER"},
			{"id": "REVERT_TO_DECIDE", "title": "🔄 Refine Goal (Core e)"},
			{"id": "VIEW_PROFILE", "title": "👤 My Profile"},
			{"id": "DEVELOP_NEED_HELP", "title": "Need Help"},
		]
		goal_label = student.final_chosen_career_goal or "your chosen goal"
		coord_name = student.assigned_career_coordinator or "Assigned DB Coordinator"
		routine_status = "Disciplined" if getattr(student, "sf_routine_discipline", 0) >= 3 else "Needs Attention"

		self.provider.send_interactive_message(
			self.chat_id,
			f"🚀 **Stage 4: DEVELOP/Prepare — Mentoring & Preparation**\n"
			f"*(Begins once career goal is finalised — Alongside Academics)*\n\n"
			f"• **Single Career Goal:** {goal_label}\n"
			f"• **DB Coordinator:** {coord_name}\n"
			f"• **Daily Fixed Routine:** {routine_status}\n"
			f"• **5 Factors Success Index:** {getattr(student, 'success_framework_score', 0)}/100%\n\n"
			f"Manage your joint action plan and milestones below:",
			buttons,
		)

	def send_commitments_for_update(self, student):
		"""
		Fetches student's pending EGS Commitment records and presents them as a list menu.
		"""
		career_goals = frappe.get_all(
			"EGS Career Goal",
			filters={"student_reference": student.name},
			order_by="creation desc",
			limit=1,
		)
		if not career_goals:
			buttons = [{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"}]
			self.provider.send_interactive_message(
				self.chat_id,
				"⚠️ No career goal found. Please finalize Stage 3 (DECIDE) first.",
				buttons,
			)
			return

		commitments = frappe.get_all(
			"EGS Commitment",
			filters={"career_goal_reference": career_goals[0].name},
			fields=["name", "action_required", "progress_status", "due_date"],
			order_by="creation desc",
			limit=10,
		)

		if not commitments:
			buttons = [
				{"id": "DEVELOP_ADD_ACTION", "title": "Add Commitment"},
				{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"},
			]
			self.provider.send_interactive_message(
				self.chat_id,
				"You don't have any commitments recorded yet.\n\nClick below to add your first dated action item:",
				buttons,
			)
			return

		buttons = []
		for c in commitments:
			btn_id = f"TASK_{c.name}"
			title = (c.action_required or c.name)[:20]
			desc = f"{c.progress_status or 'Pending'} | Due: {c.due_date}"
			buttons.append({
				"id": btn_id,
				"title": title,
				"description": desc,
				"payload": btn_id,
			})
		buttons.append({"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"})

		self.set_conversation_state("DEVELOP_SELECTING_COMMITMENT")
		self.session.save(ignore_permissions=True)

		self.provider.send_interactive_message(
			self.chat_id,
			"📋 **Select Commitment to Update Progress:**",
			buttons,
		)

	def handle_develop_flow(self, student, text: str, payload: str):
		curr_state = self.session.current_conversation_state or "IDLE"
		norm_input = (payload or text).strip().upper()

		# 1. Need Help / Escalation
		if norm_input in ("DEVELOP_NEED_HELP", "NEED HELP"):
			ticket, coord = create_escalation_ticket_for_student(
				student,
				reason="Student requested assistance during Stage 4: DEVELOP action planning.",
			)
			self.set_conversation_state("DEVELOP_ESCALATED")
			self.session.save(ignore_permissions=True)

			coord_msg = f" ({coord})" if coord else ""
			buttons = [
				{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"},
				{"id": "VIEW_PROFILE", "title": "👤 My Profile"},
			]
			self.provider.send_interactive_message(
				self.chat_id,
				f"🤝 **Support is on the way!**\n\n"
				f"An escalation ticket (`{ticket.name}`) has been created and assigned to your "
				f"**DB Career Coordinator**{coord_msg}.\n\n"
				f"They will assist you in resolving preparation barriers.",
				buttons,
			)
			return

		# 1.1 View Mentoring & Coaching Academies (Core Activity b)
		if norm_input in ("DEVELOP_VIEW_MENTORING", "MENTORING", "ACADEMIES") or "mentor" in text.lower() or "academy" in text.lower():
			coord_name = student.assigned_career_coordinator or "Assigned DB Coordinator"
			coord_doc = frappe.db.get_value("EGS Coordinator", coord_name, ["coordinator_name", "career_domain", "institution", "contact_number", "designation", "role"], as_dict=True) if coord_name else None

			coord_info = f"**Coordinator:** {coord_name}\n"
			if coord_doc:
				coord_info += f"• **Institution:** {coord_doc.institution or 'EGS Panel'}\n"
				if coord_doc.designation:
					coord_info += f"• **Designation:** {coord_doc.designation}\n"
				if coord_doc.contact_number:
					coord_info += f"• **Contact:** {coord_doc.contact_number}\n"

			msg = (
				f"🧭 **Stage 4: Structured Mentoring & Academies Network**\n\n"
				f"{coord_info}\n"
				f"🏛️ **Coaching Academies Collaboration:**\n"
				f"Need-based partnerships with top coaching institutes including **equity safeguards** (subsidized seats, curated test-series sponsorships).\n\n"
				f"👥 **Alumni & Peer Forums:**\n"
				f"Active interaction with successful alumni and career-specific study circles."
			)
			buttons = [
				{"id": "DEVELOP_ADD_ACTION", "title": "➕ Add Milestone"},
				{"id": "SF_EVAL", "title": "📝 Monthly Evaluation"},
				{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"},
			]
			self.provider.send_interactive_message(self.chat_id, msg, buttons)
			return

		# 2. Revert to DECIDE trigger (Core Activity e: Freedom to Revise or Refine Career Goal)
		if norm_input in ("REVERT_TO_DECIDE", "⏪ REVERT TO DECIDE", "REFINE GOAL", "REVISE GOAL", "🔄 REFINE GOAL (CORE E)") or "refine" in text.lower() or "revert to decide" in text.lower():
			try:
				step_back_stage(student_id=student.name, token=student.access_token, target_stage="DECIDE")
				student.reload()
				self.session.clear_context()
				self.set_conversation_state("IDLE")
				self.session.save(ignore_permissions=True)

				self.provider.send_text(
					self.chat_id,
					"⏪ **Reverted to Stage 3: DECIDE**\n\n"
					"All Stage 4 commitments have been wiped cleanly to ensure a clean slate.",
				)
				self.send_decide_prompt(student)
			except Exception as e:
				frappe.log_error(f"Step back to DECIDE failed: {e}", "Bot Workflow DEVELOP")
				self.provider.send_text(self.chat_id, f"⚠️ Unable to step back: {e}")
			return

		# 3. Proceed to Stage 5: DELIVER trigger
		if norm_input in ("PROCEED_TO_DELIVER", "PROCEED TO STAGE 5: DELIVER", "🚀 PROCEED TO STAGE 5: DELIVER", "PROCEED TO DELIVER"):
			try:
				advance_to_deliver(student_id=student.name, token=student.access_token)
				student.reload()
				self.session.clear_context()
				self.set_conversation_state("IDLE")
				self.session.save(ignore_permissions=True)

				self.provider.send_text(
					self.chat_id,
					"🚀 **Congratulations! You have advanced to Stage 5: DELIVER.**\n\n"
					"Record your achievements, exam qualifications, and placement milestones!",
				)
				self.send_deliver_menu(student)
			except Exception as e:
				frappe.log_error(f"Advance to DELIVER failed: {e}", "Bot Workflow DEVELOP")
				self.provider.send_text(self.chat_id, f"⚠️ Unable to advance to DELIVER: {e}")
			return

		# 4. Add Commitment trigger
		if norm_input in ("DEVELOP_ADD_ACTION", "ADD COMMITMENT") or "add commitment" in text.lower():
			self.set_conversation_state("DEVELOP_AWAITING_ACTION")
			self.session.save(ignore_permissions=True)
			buttons = [{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"}]
			self.provider.send_interactive_message(
				self.chat_id,
				"📋 **New Action Commitment**\n\n"
				"What is your next action item towards your goal?\n"
				"*(e.g., Complete 3 mock test papers / Enroll in AWS certification course)*",
				buttons,
			)
			return

		# 5. Update Progress trigger
		if norm_input in ("DEVELOP_UPDATE_PROGRESS", "UPDATE PROGRESS") or "update progress" in text.lower():
			self.send_commitments_for_update(student)
			return

		# 6. Add Commitment: Awaiting Action Item Text
		if curr_state == "DEVELOP_AWAITING_ACTION":
			action_text = text.strip()
			if not action_text:
				self.provider.send_text(
					self.chat_id,
					"Please reply with the action item you want to commit to:",
				)
				return

			self.session.update_context({"pending_action": action_text})
			self.set_conversation_state("DEVELOP_AWAITING_DUE_DATE")
			self.session.save(ignore_permissions=True)

			buttons = [{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"}]
			self.provider.send_interactive_message(
				self.chat_id,
				f"🎯 Action: **{action_text}**\n\n"
				f"**When is the due date for this commitment?**\n"
				f"Please reply in **YYYY-MM-DD** format (e.g. `2026-12-15`):",
				buttons,
			)
			return

		# 7. Add Commitment: Awaiting Due Date
		if curr_state == "DEVELOP_AWAITING_DUE_DATE":
			date_candidate = text.strip()
			try:
				parsed_date = getdate(date_candidate)
				formatted_date = str(parsed_date)
			except Exception:
				self.provider.send_text(
					self.chat_id,
					"⚠️ Invalid date format. Please reply with a valid date in **YYYY-MM-DD** format (e.g., `2026-12-15`):",
				)
				return

			ctx = self.session.get_context_data()
			pending_action = ctx.get("pending_action") or "Career Preparation Milestone"

			try:
				add_egs_commitment(
					student_id=student.name,
					token=student.access_token,
					data={
						"action_required": pending_action,
						"due_date": formatted_date,
						"progress_status": "Pending",
					},
				)

				self.session.clear_context()
				self.set_conversation_state("IDLE")
				self.session.save(ignore_permissions=True)

				buttons = [
					{"id": "DEVELOP_ADD_ACTION", "title": "Add Commitment"},
					{"id": "DEVELOP_UPDATE_PROGRESS", "title": "Update Progress"},
					{"id": "PROCEED_TO_DELIVER", "title": "🚀 Proceed to Stage 5: DELIVER"},
					{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"},
				]
				self.provider.send_interactive_message(
					self.chat_id,
					f"✅ **Dated Commitment Locked!**\n\n"
					f"• **Action Required:** {pending_action}\n"
					f"• **Due Date:** {formatted_date}\n"
					f"• **Status:** Pending\n\n"
					f"*Every contact ends with a dated next action.* Your commitment has been saved to your Stage 4 DEVELOP action plan.",
					buttons,
				)
			except Exception as e:
				frappe.log_error(f"Commitment creation failed in bot workflow: {e}", "Bot Workflow DEVELOP")
				self.provider.send_text(
					self.chat_id,
					f"⚠️ Failed to save commitment: {e}\nPlease type `/reset` to try again.",
				)
			return

		# 8. Update Progress: Selecting Commitment from List
		if curr_state == "DEVELOP_SELECTING_COMMITMENT":
			task_id = payload if payload.startswith("TASK-") else None
			if not task_id and payload.startswith("TASK_"):
				task_id = payload[5:]
			if not task_id and frappe.db.exists("EGS Commitment", text.strip()):
				task_id = text.strip()

			if not task_id or not frappe.db.exists("EGS Commitment", task_id):
				self.provider.send_text(self.chat_id, "⚠️ Commitment not recognized. Please choose from your active commitments:")
				self.send_commitments_for_update(student)
				return

			task_doc = frappe.get_doc("EGS Commitment", task_id)
			self.session.update_context({"selected_task_id": task_doc.name, "selected_task_title": task_doc.action_required})
			self.set_conversation_state("DEVELOP_UPDATING_STATUS")
			self.session.save(ignore_permissions=True)

			status_buttons = [
				{"id": "STATUS_In Progress", "title": "In Progress"},
				{"id": "STATUS_Progress Made", "title": "Progress Made"},
				{"id": "STATUS_Completed", "title": "Completed"},
				{"id": "STATUS_Stalled", "title": "Stalled"},
				{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"},
			]
			self.provider.send_interactive_message(
				self.chat_id,
				f"📝 **Update Progress:**\n\n"
				f"Commitment: **{task_doc.action_required}**\n"
				f"Current Status: `{task_doc.progress_status or 'Pending'}`\n\n"
				f"Select new progress status:",
				status_buttons,
			)
			return

		# 9. Update Progress: Updating Status
		if curr_state == "DEVELOP_UPDATING_STATUS":
			new_status = payload.replace("STATUS_", "").strip() if payload.startswith("STATUS_") else text.strip()
			allowed_statuses = ("In Progress", "Progress Made", "Completed", "Stalled")
			matched_status = None
			for s in allowed_statuses:
				if s.lower() == new_status.lower():
					matched_status = s
					break

			if not matched_status:
				status_buttons = [
					{"id": "STATUS_In Progress", "title": "In Progress"},
					{"id": "STATUS_Progress Made", "title": "Progress Made"},
					{"id": "STATUS_Completed", "title": "Completed"},
					{"id": "STATUS_Stalled", "title": "Stalled"},
					{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"},
				]
				self.provider.send_interactive_message(
					self.chat_id,
					"Please select a valid progress status:",
					status_buttons,
				)
				return

			ctx = self.session.get_context_data()
			task_id = ctx.get("selected_task_id")
			if task_id and frappe.db.exists("EGS Commitment", task_id):
				frappe.db.set_value("EGS Commitment", task_id, "progress_status", matched_status, update_modified=False)
				frappe.db.commit()

			task_title = ctx.get("selected_task_title") or task_id or "Commitment"
			self.session.clear_context()
			self.set_conversation_state("IDLE")
			self.session.save(ignore_permissions=True)

			if matched_status == "Stalled":
				buttons = [
					{"id": "DEVELOP_NEED_HELP", "title": "Need Help"},
					{"id": "DEVELOP_UPDATE_PROGRESS", "title": "Update Another"},
					{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"},
				]
				self.provider.send_interactive_message(
					self.chat_id,
					f"⚠️ Commitment **{task_title}** marked as **Stalled**.\n\n"
					f"Would you like assistance from your EGS Career Coordinator to help unblock this milestone?",
					buttons,
				)
			else:
				buttons = [
					{"id": "DEVELOP_UPDATE_PROGRESS", "title": "Update Another"},
					{"id": "DEVELOP_ADD_ACTION", "title": "Add Commitment"},
					{"id": "PROCEED_TO_DELIVER", "title": "🚀 Proceed to Stage 5: DELIVER"},
					{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"},
				]
				self.provider.send_interactive_message(
					self.chat_id,
					f"✅ **Progress Recorded!**\n\n"
					f"• **Commitment:** {task_title}\n"
					f"• **New Status:** {matched_status}\n\n"
					f"Keep up the great momentum!",
					buttons,
				)
			return

		# Default Stage 4 Menu
		self.send_develop_menu(student)

	# --- STAGE 5: DELIVER FLOW ---
	def send_deliver_menu(self, student):
		"""
		Stage 5 Menu: [Log Accomplishment], [Post-Grad & Factors], [🔄 Flywheel Mentorship], [DELIVER WebApp], [⏪ Revert to DEVELOP], [👤 My Profile].
		"""
		deliver_webapp_url = f"{get_url()}/my-dream-big?id={student.name}&key={student.access_token}#deliver"
		buttons = [
			{"id": "DELIVER_LOG_ACC", "title": "🏆 Log Accomplishment"},
			{"id": "DELIVER_VIEW_FLYWHEEL", "title": "🔄 Flywheel Mentorship"},
			{"id": "SF_EVAL", "title": "📝 Factors 3,4,5 Check"},
			{"id": "DELIVER_WEBAPP", "title": "📱 DELIVER WebApp", "web_app": deliver_webapp_url},
			{"id": "REVERT_TO_DEVELOP", "title": "⏪ Revert to DEVELOP"},
			{"id": "VIEW_PROFILE", "title": "👤 My Profile"},
		]
		goal_label = student.final_chosen_career_goal or "your career goal"
		degree_info = f"{student.course or 'Degree'} ({student.university_college or 'University'})"
		self.provider.send_interactive_message(
			self.chat_id,
			f"🎓 **Stage 5: DELIVER & GIVE BACK — Intense Preparation & Leadership**\n"
			f"*(Timeline: Throughout remaining undergraduate years and beyond)*\n\n"
			f"• **Objective:** Turn aspirants into achievers / leaders and absorb them as mentors\n"
			f"• **Goal Benchmark:** {goal_label}\n"
			f"• **Academic Focus:** Dual Excellence ({degree_info})\n"
			f"• **Flywheel Status:** Active Leadership Candidate\n\n"
			f"Record your milestones or manage your leadership journey below:",
			buttons,
		)

	def handle_deliver_flow(self, student, text: str, payload: str):
		curr_state = self.session.current_conversation_state or "IDLE"
		norm_input = (payload or text).strip().upper()

		# 1. Revert to DEVELOP trigger
		if norm_input in ("REVERT_TO_DEVELOP", "⏪ REVERT TO DEVELOP") or "revert to develop" in text.lower():
			try:
				step_back_stage(student_id=student.name, token=student.access_token, target_stage="DEVELOP")
				student.reload()
				self.session.clear_context()
				self.set_conversation_state("IDLE")
				self.session.save(ignore_permissions=True)

				self.provider.send_text(
					self.chat_id,
					"⏪ **Reverted to Stage 4: DEVELOP**\n\n"
					"All Stage 5 accomplishment records have been wiped cleanly to ensure a clean slate.",
				)
				self.send_develop_menu(student)
			except Exception as e:
				frappe.log_error(f"Step back to DEVELOP failed: {e}", "Bot Workflow DELIVER")
				self.provider.send_text(self.chat_id, f"⚠️ Unable to step back: {e}")
			return

		# 1.1 View Flywheel Mentorship & Give Back (Core Activity d)
		if norm_input in ("DELIVER_VIEW_FLYWHEEL", "FLYWHEEL", "GIVE BACK", "MENTOR JUNIORS") or "flywheel" in text.lower():
			msg = (
				"🔄 **The DREAM BIG Flywheel Effect (Core Activity d)**\n\n"
				"• **Objective:** Turn successful candidates & alumni into mentors for junior batches entering Stages 1, 2, and 3.\n\n"
				"🤝 **Your Flywheel Roles:**\n"
				"1. **Peer Forum Guidance:** Host AMA strategy discussions for junior aspirants.\n"
				"2. **Resource Sharing:** Share verified notes, mock tests, and interview insights.\n"
				"3. **Campus Ambassadorship:** Represent EGS:DB as an inspiring alumni leader."
			)
			buttons = [
				{"id": "DELIVER_LOG_ACC", "title": "🏆 Log Accomplishment"},
				{"id": "SF_EVAL", "title": "📝 Factors 3,4,5 Check"},
				{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"},
			]
			self.provider.send_interactive_message(self.chat_id, msg, buttons)
			return

		# 2. Log Accomplishment trigger
		if norm_input in ("DELIVER_LOG_ACC", "LOG ACCOMPLISHMENT") or "accomplishment" in text.lower():
			self.set_conversation_state("DELIVER_AWAITING_TITLE")
			self.session.clear_context()
			self.session.save(ignore_permissions=True)

			buttons = [{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"}]
			self.provider.send_interactive_message(
				self.chat_id,
				"🏆 **Log New Accomplishment**\n\n"
				"What milestone did you achieve?\n"
				"*(e.g., Cleared UPSC Prelims / Completed AWS Internship / Built Full-Stack React Project)*",
				buttons,
			)
			return

		# 3. Awaiting Accomplishment Title
		if curr_state == "DELIVER_AWAITING_TITLE":
			title_text = text.strip()
			if not title_text:
				self.provider.send_text(
					self.chat_id,
					"Please reply with the title of your accomplishment:",
				)
				return

			self.session.update_context({"pending_acc_title": title_text})
			self.set_conversation_state("DELIVER_AWAITING_CATEGORY")
			self.session.save(ignore_permissions=True)

			cat_meta = frappe.get_meta("EGS Accomplishment").get_field("category")
			options = [
				opt.strip()
				for opt in (cat_meta.options or "Exam\nInternship\nProject\nQualification\nOther").split("\n")
				if opt.strip()
			]
			buttons = [{"id": f"CAT_{opt}", "title": opt[:20], "payload": opt} for opt in options]
			buttons.append({"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"})

			self.provider.send_interactive_message(
				self.chat_id,
				f"🏆 Accomplishment: **{title_text}**\n\n"
				f"Select category for this achievement:",
				buttons,
			)
			return

		# 4. Awaiting Category
		if curr_state == "DELIVER_AWAITING_CATEGORY":
			chosen_cat = payload.replace("CAT_", "").strip() if payload.startswith("CAT_") else text.strip()
			cat_meta = frappe.get_meta("EGS Accomplishment").get_field("category")
			options = [
				opt.strip()
				for opt in (cat_meta.options or "Exam\nInternship\nProject\nQualification\nOther").split("\n")
				if opt.strip()
			]
			matched_cat = "Other"
			for opt in options:
				if opt.lower() == chosen_cat.lower():
					matched_cat = opt
					break

			self.session.update_context({"pending_acc_category": matched_cat})
			self.set_conversation_state("DELIVER_AWAITING_DATE")
			self.session.save(ignore_permissions=True)

			buttons = [{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"}]
			self.provider.send_interactive_message(
				self.chat_id,
				f"📅 Category: **{matched_cat}**\n\n"
				f"When did you achieve this? Please reply in **YYYY-MM-DD** format (e.g. `2026-11-01`) or reply `today`:",
				buttons,
			)
			return

		# 5. Awaiting Date
		if curr_state == "DELIVER_AWAITING_DATE":
			date_candidate = text.strip()
			if date_candidate.lower() == "today":
				achieved_date = today()
			else:
				try:
					achieved_date = str(getdate(date_candidate))
				except Exception:
					self.provider.send_text(
						self.chat_id,
						"⚠️ Invalid date format. Please reply in **YYYY-MM-DD** format (e.g. `2026-11-01`) or `today`:",
					)
					return

			ctx = self.session.get_context_data()
			acc_title = ctx.get("pending_acc_title") or "Milestone Achievement"
			acc_cat = ctx.get("pending_acc_category") or "Other"

			try:
				acc_doc = frappe.get_doc({
					"doctype": "EGS Accomplishment",
					"student_reference": student.name,
					"accomplishment_title": acc_title,
					"category": acc_cat,
					"date_achieved": achieved_date,
				})
				acc_doc.insert(ignore_permissions=True)
				frappe.db.commit()

				self.session.clear_context()
				self.set_conversation_state("IDLE")
				self.session.save(ignore_permissions=True)

				buttons = [
					{"id": "DELIVER_LOG_ACC", "title": "Log Another"},
					{"id": "REVERT_TO_DEVELOP", "title": "⏪ Revert to DEVELOP"},
					{"id": "VIEW_PROFILE", "title": "👤 My Profile"},
					{"id": "BACK_TO_MENU", "title": "⏪ Back to Menu"},
				]
				self.provider.send_interactive_message(
					self.chat_id,
					f"🎉 **Accomplishment Recorded!**\n\n"
					f"• **Title:** {acc_title}\n"
					f"• **Category:** {acc_cat}\n"
					f"• **Date Achieved:** {achieved_date}\n\n"
					f"Your milestone has been saved to your Stage 5: DELIVER portfolio.",
					buttons,
				)
			except Exception as e:
				frappe.log_error(f"Accomplishment creation failed in bot workflow: {e}", "Bot Workflow DELIVER")
				self.provider.send_text(
					self.chat_id,
					f"⚠️ Failed to record accomplishment: {e}\nPlease type `/reset` to try again.",
				)
			return

		# Default Stage 5 Menu
		self.send_deliver_menu(student)

	# --- 5 FACTORS SUCCESS FRAMEWORK EVALUATION FLOW (FACTORS 1 TO 5) ---
	def start_sf_evaluation(self, student):
		"""
		Starts the interactive step-by-step 5 Factors Success Framework evaluation.
		Factor 1: Daily Newspaper
		Factor 2: Routine Discipline (1-5)
		Factor 3: Skill / AI Learning
		Factor 4: PYQs & Exam Syllabus Analysis
		Factor 5: Active Peer Forum Engagement
		"""
		self.set_conversation_state("SF_AWAITING_NEWSPAPER")
		self.session.clear_context()
		self.session.save(ignore_permissions=True)

		buttons = [
			{"id": "SF_NEWS_YES", "title": "Yes, Daily"},
			{"id": "SF_NEWS_NO", "title": "No / Rarely"},
			{"id": "BACK_TO_MENU", "title": "⏪ Cancel"},
		]
		self.provider.send_interactive_message(
			self.chat_id,
			"🌟 **Students Success Framework — Monthly Check-in (1/5)**\n\n"
			"**Factor 1: General Awareness & Knowledge**\n"
			"Do you read a standard daily national newspaper or editorial analysis regularly?",
			buttons,
		)

	def handle_sf_eval_flow(self, student, text: str, payload: str):
		curr_state = self.session.current_conversation_state or "IDLE"
		norm_input = (payload or text).strip().upper()
		ctx = self.session.get_context_data()

		# Step 1: Newspaper
		if curr_state == "SF_AWAITING_NEWSPAPER":
			is_yes = 1 if norm_input in ("SF_NEWS_YES", "YES", "YES, DAILY", "Y", "1") else 0
			self.session.update_context({"sf_daily_newspaper": is_yes})
			self.set_conversation_state("SF_AWAITING_ROUTINE")
			self.session.save(ignore_permissions=True)

			buttons = [
				{"id": "SF_ROUTINE_5", "title": "⭐⭐⭐⭐⭐ High (5/5)"},
				{"id": "SF_ROUTINE_4", "title": "⭐⭐⭐⭐ Good (4/5)"},
				{"id": "SF_ROUTINE_3", "title": "⭐⭐⭐ Moderate (3/5)"},
				{"id": "SF_ROUTINE_2", "title": "⭐⭐ Low (2/5)"},
				{"id": "BACK_TO_MENU", "title": "⏪ Cancel"},
			]
			self.provider.send_interactive_message(
				self.chat_id,
				"🌟 **Success Framework Check-in (2/5)**\n\n"
				"**Factor 2: Time Management & Fixed Routine**\n"
				"How strictly do you maintain a fixed daily schedule balancing regular college degree studies alongside competitive preparation?",
				buttons,
			)
			return

		# Step 2: Routine
		if curr_state == "SF_AWAITING_ROUTINE":
			routine_val = 3
			for r in (5, 4, 3, 2, 1):
				if str(r) in norm_input:
					routine_val = r
					break
			self.session.update_context({"sf_routine_discipline": routine_val})
			self.set_conversation_state("SF_AWAITING_SKILL")
			self.session.save(ignore_permissions=True)

			buttons = [{"id": "BACK_TO_MENU", "title": "⏪ Cancel"}]
			self.provider.send_interactive_message(
				self.chat_id,
				"🌟 **Success Framework Check-in (3/5)**\n\n"
				"**Factor 3: Skill Building & Internships**\n"
				"What specialized technical skill, certification, AI tool, or internship are you currently learning or pursuing?\n"
				"*(Reply with skill name or 'None' if not started yet)*:",
				buttons,
			)
			return

		# Step 3: Skill
		if curr_state == "SF_AWAITING_SKILL":
			skill_val = text.strip()
			if not skill_val:
				skill_val = "Specialized Preparation"
			self.session.update_context({"sf_skill_learning": skill_val})
			self.set_conversation_state("SF_AWAITING_PYQ")
			self.session.save(ignore_permissions=True)

			buttons = [
				{"id": "SF_PYQ_YES", "title": "Yes, Thoroughly"},
				{"id": "SF_PYQ_NO", "title": "Not Yet / In Progress"},
				{"id": "BACK_TO_MENU", "title": "⏪ Cancel"},
			]
			self.provider.send_interactive_message(
				self.chat_id,
				"🌟 **Success Framework Check-in (4/5)**\n\n"
				"**Factor 4: Exam Rigor & Analysis**\n"
				"Have you reviewed the complete competitive syllabus and solved/analyzed past 5–10 years question papers (PYQs)?",
				buttons,
			)
			return

		# Step 4: PYQs
		if curr_state == "SF_AWAITING_PYQ":
			is_pyq = 1 if norm_input in ("SF_PYQ_YES", "YES", "YES, THOROUGHLY", "Y", "1") else 0
			self.session.update_context({"sf_pyq_syllabus_reviewed": is_pyq})
			self.set_conversation_state("SF_AWAITING_PEER")
			self.session.save(ignore_permissions=True)

			buttons = [
				{"id": "SF_PEER_YES", "title": "Yes, Actively"},
				{"id": "SF_PEER_NO", "title": "No / Inactive"},
				{"id": "BACK_TO_MENU", "title": "⏪ Cancel"},
			]
			self.provider.send_interactive_message(
				self.chat_id,
				"🌟 **Success Framework Check-in (5/5)**\n\n"
				"**Factor 5: Peer Forum & Collaborative Learning**\n"
				"Are you actively participating in your career peer forum, exchanging study notes, and resolving doubts?",
				buttons,
			)
			return

		# Step 5: Peer Forum & Submission
		if curr_state == "SF_AWAITING_PEER":
			is_peer = 1 if norm_input in ("SF_PEER_YES", "YES", "YES, ACTIVELY", "Y", "1") else 0
			ctx = self.session.get_context_data()

			daily_news = ctx.get("sf_daily_newspaper", 0)
			routine_disc = ctx.get("sf_routine_discipline", 3)
			skill_val = ctx.get("sf_skill_learning", "")
			is_pyq = ctx.get("sf_pyq_syllabus_reviewed", 0)

			try:
				submit_success_framework_eval(
					student_id=student.name,
					access_key=student.access_token,
					daily_newspaper=daily_news,
					routine_discipline=routine_disc,
					skill_learning=skill_val,
					pyq_syllabus_reviewed=is_pyq,
					peer_forum_active=is_peer,
				)
				student.reload()
				score = calculate_success_framework_score(student)

				self.session.clear_context()
				self.set_conversation_state("IDLE")
				self.session.save(ignore_permissions=True)

				buttons = [
					{"id": "VIEW_PROFILE", "title": "👤 My Profile"},
					{"id": "BACK_TO_MENU", "title": "⏪ Main Menu"},
				]
				self.provider.send_interactive_message(
					self.chat_id,
					f"🎉 **Monthly Evaluation Saved!**\n\n"
					f"• **New Success Framework Score:** **{score}/100%**\n"
					f"• **Daily Newspaper:** {'✓ Yes' if daily_news else 'Needs Attention'}\n"
					f"• **Routine Discipline:** {routine_disc}/5\n"
					f"• **Skill Focus:** {skill_val}\n"
					f"• **PYQs & Syllabus:** {'✓ Thorough' if is_pyq else 'In Progress'}\n"
					f"• **Peer Forum Engagement:** {'✓ Active' if is_peer else 'Inactive'}\n\n"
					f"Your progress has been logged in your official check-in record.",
					buttons,
				)
			except Exception as e:
				frappe.log_error(f"Failed to submit SF evaluation via bot: {e}", "Bot SF Eval")
				self.provider.send_text(
					self.chat_id,
					f"⚠️ Unable to record self-evaluation: {e}\nPlease type `/reset` to retry.",
				)
			return


def process_bot_message(session, message_data: dict, provider: BaseMessagingProvider):
	"""
	Main entry point invoked by the webhook router.
	"""
	engine = EGS5DsWorkflowEngine(session, provider)
	engine.process_message(message_data)
