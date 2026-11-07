# Copyright (c) 2026, Dream Big and contributors
# For license information, please see license.txt

import re
import frappe
from frappe.utils import get_url
from dreambig_egs.bot_engine.provider import get_messaging_provider
from dreambig_egs.bot_engine.workflow import (
	process_bot_message,
	find_student_by_identifier,
	EGS5DsWorkflowEngine,
)


@frappe.whitelist(allow_guest=True)
def get_registration_url() -> str:
	"""
	Returns the full Web Form registration URL using Frappe site configuration host_name / get_url().
	"""
	return f"{get_url()}/egs-student-participant"


@frappe.whitelist(allow_guest=True)
def bot_webhook(platform="telegram", **kwargs):
	"""
	Universal webhook router for platform-agnostic bot messaging (Telegram, WhatsApp, etc.).
	Parses incoming payload, executes native contact & identity binding, retrieves active EGS Bot Session,
	and dispatches to the 5Ds Workflow Engine.
	"""
	platform_norm = (platform or "telegram").strip().lower()
	platform_label = "WhatsApp" if platform_norm in ("whatsapp", "wa") else "Telegram"
	provider = get_messaging_provider(platform_norm)

	# Extract incoming request payload (JSON or form-data)
	raw_data = None
	if hasattr(frappe.local, "request") and frappe.local.request:
		try:
			raw_data = frappe.local.request.get_json()
		except Exception:
			raw_data = None

	if not raw_data:
		raw_data = dict(frappe.local.form_dict or kwargs or {})

	# Remove internal frappe parameters like cmd
	raw_data.pop("cmd", None)

	# Normalize payload through provider adapter
	message_data = provider.parse_incoming_webhook(raw_data)
	chat_id = str(message_data.get("chat_id") or "").strip()

	if not chat_id:
		return {"status": "ignored", "reason": "No chat_id in incoming webhook"}

	text = str(message_data.get("text") or "").strip()
	payload = str(message_data.get("payload") or "").strip()

	# Retrieve or initialize active EGS Bot Session
	session = None
	sessions = frappe.get_all(
		"EGS Bot Session",
		filters={"chat_id": chat_id, "platform": platform_label},
		limit=1,
	)
	if sessions:
		session = frappe.get_doc("EGS Bot Session", sessions[0].name)
	else:
		session = frappe.get_doc({
			"doctype": "EGS Bot Session",
			"chat_id": chat_id,
			"platform": platform_label,
			"current_conversation_state": "IDLE",
			"session_data": "{}",
		})
		session.insert(ignore_permissions=True)
		frappe.db.commit()

	session.flags.ignore_version = True

	# If session was logged out and user sends a new message, reset to IDLE for fresh re-authentication
	if session.current_conversation_state == "LOGGED_OUT":
		session.student_participant = None
		session.current_conversation_state = "IDLE"
		session.save(ignore_permissions=True)
		frappe.db.commit()

	# --- IDENTITY BINDING LOGIC ---

	# 1. WhatsApp Identity Binding: Match by sender's phone number
	if platform_label == "WhatsApp":
		if not session.student_participant:
			cleaned_phone = re.sub(r"\D", "", chat_id)
			phone_10 = cleaned_phone[-10:] if len(cleaned_phone) >= 10 else cleaned_phone
			matched_student = None

			if len(cleaned_phone) >= 10:
				students = frappe.get_all(
					"EGS Student Participant",
					filters={"phone_number": ["like", f"%{phone_10}"]},
					limit=1,
				)
				if students:
					matched_student = frappe.get_doc("EGS Student Participant", students[0].name)

			if matched_student:
				session.student_participant = matched_student.name
				session.current_conversation_state = "IDLE"
				session.save(ignore_permissions=True)
				frappe.db.commit()
			else:
				# Check if this is the "I have registered" refresh tap
				if payload in ("I_HAVE_REGISTERED", "REFRESH_REGISTRATION") or "registered" in text.lower():
					engine = EGS5DsWorkflowEngine(session, provider)
					engine.handle_unlinked_session(text, payload)
					return {
						"status": "unregistered_check",
						"chat_id": chat_id,
						"platform": platform_label,
						"conversation_state": session.current_conversation_state,
					}

				# Unknown user on WhatsApp: Trigger Registration State
				session.current_conversation_state = "AWAITING_REGISTRATION"
				session.update_context({"unregistered_phone": phone_10})
				session.save(ignore_permissions=True)
				frappe.db.commit()

				engine = EGS5DsWorkflowEngine(session, provider)
				engine.send_registration_prompt(phone_10)
				return {
					"status": "unregistered",
					"chat_id": chat_id,
					"platform": platform_label,
					"conversation_state": "AWAITING_REGISTRATION",
					"registration_url": get_registration_url(),
				}

	# 2. Telegram Identity Binding: Native Contact Sharing & Phone Matching
	elif platform_label == "Telegram":
		# Query EGS Student Participant for telegram_chat_id
		student_by_chat = frappe.get_all(
			"EGS Student Participant",
			filters={"telegram_chat_id": chat_id},
			limit=1,
		)

		if student_by_chat:
			if session.student_participant != student_by_chat[0].name:
				session.student_participant = student_by_chat[0].name
				session.save(ignore_permissions=True)
				frappe.db.commit()
		elif session.student_participant:
			# Session had student linked, ensure telegram_chat_id is saved on student
			frappe.db.set_value("EGS Student Participant", session.student_participant, "telegram_chat_id", chat_id)
			frappe.db.commit()
		else:
			# Not linked yet
			curr_state = session.current_conversation_state or "IDLE"

			# Check if user sent /start with an ID or token directly (e.g. /start STU-26-0092)
			if text.startswith("/start ") and len(text.split()) > 1:
				candidate_id = text.split(maxsplit=1)[1].strip()
				matched = find_student_by_identifier(candidate_id)
				if matched:
					frappe.db.set_value("EGS Student Participant", matched.name, "telegram_chat_id", chat_id)
					frappe.db.commit()
					session.student_participant = matched.name
					session.current_conversation_state = "IDLE"
					session.save(ignore_permissions=True)
					provider.send_text(
						chat_id,
						f"🎉 Welcome **{matched.student_name}**!\n\n"
						f"Your Telegram account has been successfully connected to your **DREAM BIG Journey** (`{matched.name}`)."
					)
					engine = EGS5DsWorkflowEngine(session, provider)
					engine.trigger_stage_prompt(matched)
					return {
						"status": "success",
						"chat_id": chat_id,
						"platform": platform_label,
						"conversation_state": session.current_conversation_state,
					}

			# Check if user tapped "[🔄 I have registered]" button
			if payload in ("I_HAVE_REGISTERED", "REFRESH_REGISTRATION") or (curr_state == "AWAITING_REGISTRATION" and "registered" in text.lower()):
				engine = EGS5DsWorkflowEngine(session, provider)
				engine.handle_unlinked_session(text, payload)
				return {
					"status": "unregistered_check",
					"chat_id": chat_id,
					"platform": platform_label,
					"conversation_state": session.current_conversation_state,
				}

			# Check if message contains a native shared contact OR a phone number reply
			contact = message_data.get("contact")
			phone_candidate = str(
				message_data.get("phone_number")
				or (contact.get("phone_number") if isinstance(contact, dict) else "")
				or ""
			)
			if not phone_candidate and curr_state == "AWAITING_MOBILE_BINDING" and text:
				phone_candidate = text

			if phone_candidate:
				cleaned = re.sub(r"\D", "", phone_candidate)
				matched_student = None
				phone_10 = cleaned[-10:] if len(cleaned) >= 10 else cleaned

				if len(cleaned) >= 10:
					matched_rows = frappe.get_all(
						"EGS Student Participant",
						filters={"phone_number": ["like", f"%{phone_10}"]},
						limit=1,
					)
					if matched_rows:
						matched_student = frappe.get_doc("EGS Student Participant", matched_rows[0].name)

				if not matched_student:
					matched_student = find_student_by_identifier(phone_candidate)

				if matched_student:
					# Link telegram_chat_id to student participant
					frappe.db.set_value("EGS Student Participant", matched_student.name, "telegram_chat_id", chat_id)
					frappe.db.commit()
					session.student_participant = matched_student.name
					session.clear_context()
					session.current_conversation_state = "IDLE"
					session.save(ignore_permissions=True)

					provider.send_text(
						chat_id,
						f"🎉 Welcome **{matched_student.student_name}**!\n\n"
						f"Your Telegram account has been linked to your **DREAM BIG profile** (`{matched_student.name}`)."
					)
					engine = EGS5DsWorkflowEngine(session, provider)
					engine.trigger_stage_prompt(matched_student)
					return {
						"status": "success",
						"chat_id": chat_id,
						"platform": platform_label,
						"conversation_state": session.current_conversation_state,
					}
				else:
					# Shared contact or entered phone is NOT registered -> Trigger Registration Flow
					session.current_conversation_state = "AWAITING_REGISTRATION"
					session.update_context({"unregistered_phone": phone_10})
					session.save(ignore_permissions=True)
					frappe.db.commit()

					engine = EGS5DsWorkflowEngine(session, provider)
					engine.send_registration_prompt(phone_10)
					return {
						"status": "unregistered",
						"chat_id": chat_id,
						"platform": platform_label,
						"conversation_state": "AWAITING_REGISTRATION",
						"registration_url": get_registration_url(),
					}
			else:
				# User sends /start or hi or any text when unrecognized:
				# Transition to AWAITING_MOBILE_BINDING and respond with native "📱 Share Contact" button
				session.current_conversation_state = "AWAITING_MOBILE_BINDING"
				session.save(ignore_permissions=True)
				frappe.db.commit()

				provider.send_contact_request(
					chat_id,
					"👋 Welcome to the **EARLY GOAL SETTING: DREAM BIG** Assistant!\n\n"
					"Your Telegram account is not yet connected to your student profile.\n\n"
					"Tap **📱 Share Contact** below to automatically verify your registered mobile number:",
					button_text="📱 Share Contact",
				)
				return {
					"status": "contact_prompted",
					"chat_id": chat_id,
					"platform": platform_label,
					"conversation_state": "AWAITING_MOBILE_BINDING",
				}

	# Delegate to 5Ds Chatbot Workflow Engine
	process_bot_message(session=session, message_data=message_data, provider=provider)
	frappe.db.commit()

	return {
		"status": "success",
		"chat_id": chat_id,
		"platform": platform_label,
		"conversation_state": session.current_conversation_state,
	}
