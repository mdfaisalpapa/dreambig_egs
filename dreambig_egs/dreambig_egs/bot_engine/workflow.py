# Copyright (c) 2026, Dream Big and contributors
# For license information, please see license.txt

import re
import frappe
from frappe import _
from frappe.utils import get_url, now_datetime, getdate, today
from dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant import (
	submit_decide_stage,
	advance_to_develop,
	add_egs_commitment,
)
from dreambig_egs.dreambig_egs.bot_engine.provider import BaseMessagingProvider


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
	Platform-agnostic state machine executing the 'Track -> Nudge -> Support -> Escalate' cycle.
	"""

	def __init__(self, session, provider: BaseMessagingProvider):
		self.session = session
		self.provider = provider
		self.chat_id = session.chat_id

	def process_message(self, message_data: dict):
		text = (message_data.get("text") or "").strip()
		payload = (message_data.get("payload") or "").strip()

		# Update last interaction
		self.session.last_interaction = now_datetime()

		# 1. Unlinked session identification
		if not self.session.student_participant:
			self.handle_unlinked_session(text, payload)
			return

		# Load student participant
		student = frappe.get_doc("EGS Student Participant", self.session.student_participant)

		# 2. Universal command handlers
		low_text = text.lower()
		if payload == "VIEW_DASHBOARD" or low_text in ("/dashboard", "dashboard", "portal"):
			portal_url = f"{get_url()}/my-dream-big?id={student.name}&key={student.access_token}"
			self.provider.send_text(
				self.chat_id,
				f"🔗 **Your DREAM BIG Dashboard:**\n[Click here to open your live portal]({portal_url})\n\nBookmark this link on your device for instant access!",
			)
			self.session.save(ignore_permissions=True)
			return

		if low_text in ("/reset", "reset", "/restart"):
			self.session.current_conversation_state = "IDLE"
			self.session.clear_context()
			self.session.save(ignore_permissions=True)
			self.trigger_stage_prompt(student, is_reset=True)
			return

		if low_text in ("/help", "help"):
			self.provider.send_text(
				self.chat_id,
				"🤖 **DREAM BIG 5Ds Framework Assistant**\n\n"
				"I help you track and advance through your career journey:\n"
				"• **Stage 2 (DISCOVER):** Shortlist career paths and request mentor support.\n"
				"• **Stage 3 (DECIDE):** Lock your finalized career goal and promise to self.\n"
				"• **Stage 4 (DEVELOP):** Commit to dated preparation milestones.\n\n"
				"Commands:\n"
				"• `/dashboard` - Get your secure dashboard link\n"
				"• `/status` - Check your current stage\n"
				"• `/reset` - Restart conversation prompt",
			)
			self.session.save(ignore_permissions=True)
			return

		if low_text in ("/status", "status"):
			stage = student.current_5ds_stage or "DISCOVER"
			goal = student.final_chosen_career_goal or "Not finalized yet"
			self.provider.send_text(
				self.chat_id,
				f"📊 **Your Journey Status**\n\n"
				f"• **Student:** {student.student_name} ({student.name})\n"
				f"• **Current 5Ds Stage:** {stage}\n"
				f"• **Finalized Career Goal:** {goal}\n",
			)
			self.session.save(ignore_permissions=True)
			return

		# 3. Route by conversation state first, then student's active 5Ds stage
		curr_state = (self.session.current_conversation_state or "IDLE").upper()
		active_stage = (student.current_5ds_stage or "DISCOVER").upper()

		if curr_state.startswith("DECIDE_"):
			self.handle_decide_flow(student, text, payload)
		elif curr_state.startswith("DEVELOP_"):
			self.handle_develop_flow(student, text, payload)
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

	def handle_unlinked_session(self, text: str, payload: str):
		# Attempt to extract student identifier from /start command or direct input
		identifier = text
		if text.startswith("/start"):
			parts = text.split(maxsplit=1)
			if len(parts) > 1:
				identifier = parts[1].strip()

		student = find_student_by_identifier(identifier)
		if student:
			self.session.student_participant = student.name
			self.session.current_conversation_state = "IDLE"
			self.session.save(ignore_permissions=True)

			self.provider.send_text(
				self.chat_id,
				f"🎉 Welcome **{student.student_name}**!\n\n"
				f"Your Telegram account is now connected to your **DREAM BIG Journey** (`{student.name}`).\n"
				f"Current Stage: **{student.current_5ds_stage or 'DISCOVER'}**.",
			)
			self.trigger_stage_prompt(student)
		else:
			self.provider.send_text(
				self.chat_id,
				"👋 Welcome to the **EARLY GOAL SETTING: DREAM BIG** Bot!\n\n"
				"To connect your journey, please reply with your **Student ID** (e.g. `STU-26-0092`), "
				"your **registered email address**, or paste your **Magic Link access key**.",
			)
			self.session.save(ignore_permissions=True)

	def trigger_stage_prompt(self, student, is_reset=False):
		stage = (student.current_5ds_stage or "DISCOVER").upper()

		if "DISCOVER" in stage:
			self.send_discover_nudge()
		elif "DECIDE" in stage:
			self.session.current_conversation_state = "DECIDE_AWAITING_GOAL"
			self.session.save(ignore_permissions=True)
			self.provider.send_text(
				self.chat_id,
				"🎯 **Stage 3: DECIDE — A Promise to Self**\n\n"
				"Please reply with your **Final Chosen Career Goal**\n"
				"(e.g., Software Engineering, Civil Services, Artificial Intelligence, Chartered Accountancy):",
			)
		elif "DEVELOP" in stage:
			self.session.current_conversation_state = "DEVELOP_AWAITING_ACTION"
			self.session.save(ignore_permissions=True)
			self.provider.send_text(
				self.chat_id,
				"🚀 **Stage 4: DEVELOP — Action Plan**\n\n"
				"What is your next action item towards your goal?\n"
				"(e.g., Complete 3 mock test papers / Enroll in AWS certification course):",
			)
		else:
			self.provider.send_text(
				self.chat_id,
				f"🎓 You are in **Stage: {stage}**. Type `/dashboard` to view your progress or `/help` for commands.",
			)

	def send_discover_nudge(self):
		self.session.current_conversation_state = "DISCOVER_AWAITING_CHOICE"
		self.session.save(ignore_permissions=True)

		buttons = [
			{"title": "① Yes, decided", "payload": "DISCOVER_YES"},
			{"title": "② Still deciding", "payload": "DISCOVER_STILL_DECIDING"},
			{"title": "③ I need help", "payload": "DISCOVER_NEED_HELP"},
		]
		self.provider.send_interactive_buttons(
			self.chat_id,
			"🧭 **Stage 2: DISCOVER — Career Shortlist**\n\n"
			"Have you narrowed your shortlist?\n\n"
			"① Yes, decided\n"
			"② Still deciding\n"
			"③ I need help",
			buttons,
		)

	# --- STAGE 2: DISCOVER FLOW ---
	def handle_discover_flow(self, student, text: str, payload: str):
		curr_state = self.session.current_conversation_state or "IDLE"
		norm_input = (payload or text).strip().upper()

		# Check for "I need help" escalation
		if norm_input in ("DISCOVER_NEED_HELP", "3", "③ I NEED HELP") or "help" in text.lower() or "stuck" in text.lower():
			ticket, coord = create_escalation_ticket_for_student(
				student,
				reason="Student selected 'I need help' during DISCOVER stage chatbot follow-up.",
			)
			self.session.current_conversation_state = "DISCOVER_ESCALATED"
			self.session.save(ignore_permissions=True)

			coord_msg = f" ({coord})" if coord else ""
			self.provider.send_text(
				self.chat_id,
				f"🤝 **Support is on the way!**\n\n"
				f"An escalation ticket (`{ticket.name}`) has been generated and assigned to your "
				f"**DB Career Coordinator**{coord_msg}.\n\n"
				f"They will reach out to you directly to guide you through your career pathway options. "
				f"In the meantime, feel free to review your choices on the dashboard.",
			)
			return

		# Check for "Yes, decided" progression
		if norm_input in ("DISCOVER_YES", "1", "① YES, DECIDED") or "decided" in text.lower() or text.lower() == "yes":
			self.session.current_conversation_state = "DECIDE_AWAITING_GOAL"
			self.session.clear_context()
			self.session.save(ignore_permissions=True)

			self.provider.send_text(
				self.chat_id,
				"🎯 **Stage 3: DECIDE — A Promise to Self**\n\n"
				"Fantastic! Stepping into DECIDE is a powerful commitment.\n\n"
				"Please reply with your **Final Chosen Career Goal**\n"
				"(e.g., Artificial Intelligence & Robotics, Civil Services, Chartered Accountancy, Biotech Engineering):",
			)
			return

		# Check for "Still deciding" nudge
		if norm_input in ("DISCOVER_STILL_DECIDING", "2", "② STILL DECIDING") or "still" in text.lower():
			buttons = [
				{"title": "① I'm ready to decide", "payload": "DISCOVER_YES"},
				{"title": "③ I need help", "payload": "DISCOVER_NEED_HELP"},
			]
			self.provider.send_interactive_buttons(
				self.chat_id,
				"💡 **Take your time exploring!**\n\n"
				"Careful consideration leads to confident decisions. Review your Top 5 Career choices on your portal "
				"or consult your brochure.\n\n"
				"Whenever you are ready, or if you feel stuck, select an option below:",
				buttons,
			)
			return

		# If in idle or awaiting choice and input wasn't recognized, prompt with buttons
		self.send_discover_nudge()

	# --- STAGE 3: DECIDE FLOW ---
	def handle_decide_flow(self, student, text: str, payload: str):
		curr_state = self.session.current_conversation_state or "DECIDE_AWAITING_GOAL"

		if curr_state == "DECIDE_AWAITING_GOAL":
			goal_candidate = text.strip()
			if not goal_candidate:
				self.provider.send_text(
					self.chat_id,
					"Please reply with the title of your **Final Chosen Career Goal**:",
				)
				return

			self.session.update_context({"pending_goal": goal_candidate})
			self.session.current_conversation_state = "DECIDE_AWAITING_VISION"
			self.session.save(ignore_permissions=True)

			self.provider.send_text(
				self.chat_id,
				f"🌟 Target Goal: **{goal_candidate}**\n\n"
				f"Now, please write and reply with your **Personal Vision Statement**:\n"
				f"*(Where do you see yourself, what impact do you want to create, and why is this your aspiration?)*",
			)
			return

		if curr_state == "DECIDE_AWAITING_VISION":
			vision_text = text.strip()
			if not vision_text:
				self.provider.send_text(
					self.chat_id,
					"Please reply with your **Personal Vision Statement** to complete your DECIDE commitment:",
				)
				return

			ctx = self.session.get_context_data()
			chosen_goal = ctx.get("pending_goal") or student.final_chosen_career_goal or "General Pathway"

			try:
				# 1. Commit to DECIDE Stage in backend
				submit_decide_stage(
					student_id=student.name,
					token=student.access_token,
					final_chosen_career_goal=chosen_goal,
					personal_vision_statement=vision_text,
					a_promise_to_self=vision_text,
					date_of_decision=today(),
				)

				# 2. Advance student to Stage 4: DEVELOP
				advance_to_develop(
					student_id=student.name,
					token=student.access_token,
				)

				# Update session state to DEVELOP action planning
				self.session.clear_context()
				self.session.current_conversation_state = "DEVELOP_AWAITING_ACTION"
				self.session.save(ignore_permissions=True)

				self.provider.send_text(
					self.chat_id,
					f"🚀 **Stage 3 Complete! You have advanced to Stage 4: DEVELOP.**\n\n"
					f"• **Chosen Career Goal:** {chosen_goal}\n"
					f"• **Vision:** \"{vision_text}\"\n\n"
					f"To kick off your action plan: **What is your next action item?**\n"
					f"*(e.g., Complete 3 mock test papers / Enroll in AWS certification course)*",
				)
			except Exception as e:
				frappe.log_error(f"DECIDE transition failed in bot workflow: {e}", "Bot Workflow DECIDE")
				self.provider.send_text(
					self.chat_id,
					f"⚠️ We encountered an issue saving your DECIDE commitment: {e}\n"
					f"Please type `/reset` to try again or open your dashboard.",
				)
			return

		# Fallback to prompt for goal
		self.session.current_conversation_state = "DECIDE_AWAITING_GOAL"
		self.session.save(ignore_permissions=True)
		self.provider.send_text(
			self.chat_id,
			"🎯 **Stage 3: DECIDE**\nPlease reply with your **Final Chosen Career Goal**:",
		)

	# --- STAGE 4: DEVELOP FLOW ---
	def handle_develop_flow(self, student, text: str, payload: str):
		curr_state = self.session.current_conversation_state or "DEVELOP_AWAITING_ACTION"
		norm_input = (payload or text).strip().upper()

		if norm_input == "DEVELOP_ADD_ACTION" or "add action" in text.lower():
			self.session.current_conversation_state = "DEVELOP_AWAITING_ACTION"
			self.session.save(ignore_permissions=True)
			self.provider.send_text(
				self.chat_id,
				"📋 **New Action Commitment**\n\nWhat is your next action item towards your goal?",
			)
			return

		if curr_state == "DEVELOP_AWAITING_ACTION":
			action_text = text.strip()
			if not action_text:
				self.provider.send_text(
					self.chat_id,
					"Please reply with the action item you want to commit to:",
				)
				return

			self.session.update_context({"pending_action": action_text})
			self.session.current_conversation_state = "DEVELOP_AWAITING_DUE_DATE"
			self.session.save(ignore_permissions=True)

			self.provider.send_text(
				self.chat_id,
				f"🎯 Action: **{action_text}**\n\n"
				f"**When is the due date for this commitment?**\n"
				f"Please reply in **YYYY-MM-DD** format (e.g. `2026-12-15`):",
			)
			return

		if curr_state == "DEVELOP_AWAITING_DUE_DATE":
			date_candidate = text.strip()

			# Validate YYYY-MM-DD date format
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
						"status": "Pending",
					},
				)

				self.session.clear_context()
				self.session.current_conversation_state = "IDLE"
				self.session.save(ignore_permissions=True)

				buttons = [
					{"title": "➕ Add another action item", "payload": "DEVELOP_ADD_ACTION"},
					{"title": "📊 View My Dashboard", "payload": "VIEW_DASHBOARD"},
				]
				self.provider.send_interactive_buttons(
					self.chat_id,
					f"✅ **Dated Commitment Locked!**\n\n"
					f"• **Action Required:** {pending_action}\n"
					f"• **Due Date:** {formatted_date}\n"
					f"• **Status:** Pending\n\n"
					f"*Every contact ends with a dated next action.* Your commitment has been saved to your Stage 4 DEVELOP action plan.\n\n"
					f"What would you like to do next?",
					buttons,
				)
			except Exception as e:
				frappe.log_error(f"Commitment creation failed in bot workflow: {e}", "Bot Workflow DEVELOP")
				self.provider.send_text(
					self.chat_id,
					f"⚠️ Failed to save commitment: {e}\nPlease type `/reset` to try again.",
				)
			return

		# If idle in DEVELOP
		buttons = [
			{"title": "➕ Add Next Action Item", "payload": "DEVELOP_ADD_ACTION"},
			{"title": "📊 Open Dashboard", "payload": "VIEW_DASHBOARD"},
		]
		self.provider.send_interactive_buttons(
			self.chat_id,
			f"🚀 **Stage 4: DEVELOP — Action Tracking**\n\n"
			f"You are actively working on your preparation milestones for **{student.final_chosen_career_goal or 'your chosen goal'}**.\n\n"
			f"Remember: *No student is left unguided and every contact ends with a dated next action.*",
			buttons,
		)

	# --- STAGE 5: DELIVER FLOW ---
	def handle_deliver_flow(self, student, text: str, payload: str):
		buttons = [
			{"title": "📊 Open Dashboard", "payload": "VIEW_DASHBOARD"},
		]
		self.provider.send_interactive_buttons(
			self.chat_id,
			f"🎓 **Stage 5: DELIVER — Achievement Milestone**\n\n"
			f"Congratulations, **{student.student_name}**! You have reached the execution and delivery stage for **{student.final_chosen_career_goal or 'your goal'}**.\n\n"
			f"Track your exam qualifications, college admissions, and placement milestones directly on your portal.",
			buttons,
		)


def process_bot_message(session, message_data: dict, provider: BaseMessagingProvider):
	"""
	Main entry point invoked by the webhook router.
	"""
	engine = EGS5DsWorkflowEngine(session, provider)
	engine.process_message(message_data)
