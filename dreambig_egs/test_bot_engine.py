import frappe
import requests
import json
from frappe.utils import today
from dreambig_egs.bot_engine.provider import BaseMessagingProvider, TelegramProvider, get_messaging_provider
from dreambig_egs.bot_engine.workflow import process_bot_message, create_escalation_ticket_for_student
from dreambig_egs.api import bot_webhook


def run_tests():
	print("=" * 60)
	print("TESTING PLATFORM-AGNOSTIC BOT ENGINE & 5Ds WORKFLOW")
	print("=" * 60)

	# 1. Test Provider Architecture & Abstraction
	print("\n--- 1. Testing BaseMessagingProvider & TelegramProvider ---")
	prov = get_messaging_provider("telegram")
	assert isinstance(prov, BaseMessagingProvider)
	assert isinstance(prov, TelegramProvider)

	# Test mock sending
	send_res = prov.send_text("99999", "Test Hello")
	assert send_res.get("status") == "mock_sent"
	assert send_res.get("chat_id") == "99999"

	# Test interactive buttons structure
	buttons = [
		{"title": "① Yes, decided", "payload": "DISCOVER_YES"},
		{"title": "② Still deciding", "payload": "DISCOVER_STILL_DECIDING"},
		{"title": "③ I need help", "payload": "DISCOVER_NEED_HELP"},
	]
	btn_res = prov.send_interactive_buttons("99999", "Question text", buttons)
	assert btn_res.get("status") == "mock_sent"
	assert len(btn_res.get("buttons")) == 3
	print("✓ BaseMessagingProvider and TelegramProvider send methods operational")

	# Test Telegram incoming webhook parsing
	raw_msg_webhook = {
		"update_id": 10001,
		"message": {
			"message_id": 1,
			"from": {"id": 888111, "first_name": "Faisal", "last_name": "Khan"},
			"chat": {"id": 888111, "type": "private"},
			"text": "Hello bot"
		}
	}
	parsed_msg = prov.parse_incoming_webhook(raw_msg_webhook)
	assert parsed_msg["chat_id"] == "888111"
	assert parsed_msg["text"] == "Hello bot"
	assert parsed_msg["is_button"] is False
	assert parsed_msg["sender_name"] == "Faisal Khan"

	raw_cb_webhook = {
		"update_id": 10002,
		"callback_query": {
			"id": "cb_001",
			"from": {"id": 888111, "first_name": "Faisal"},
			"message": {"chat": {"id": 888111}, "message_id": 2},
			"data": "DISCOVER_YES"
		}
	}
	parsed_cb = prov.parse_incoming_webhook(raw_cb_webhook)
	assert parsed_cb["chat_id"] == "888111"
	assert parsed_cb["payload"] == "DISCOVER_YES"
	assert parsed_cb["is_button"] is True
	print("✓ Telegram webhook parser correctly normalizes text messages and callback queries")

	# 2. Setup Test Student Participant & Coordinator
	print("\n--- 2. Setting up Test Participant & Coordinator ---")
	test_email = "bot.student@example.com"
	# Clean up previous runs
	for s in frappe.get_all("EGS Student Participant", filters={"student_email": test_email}):
		for b in frappe.get_all("EGS Bot Session", filters={"student_participant": s.name}):
			frappe.delete_doc("EGS Bot Session", b.name, force=True)
		for t in frappe.get_all("EGS Escalation Ticket", filters={"student_reference": s.name}):
			frappe.delete_doc("EGS Escalation Ticket", t.name, force=True)
		for c in frappe.get_all("EGS Check-in Log", filters={"student_reference": s.name}):
			frappe.delete_doc("EGS Check-in Log", c.name, force=True)
		for cg in frappe.get_all("EGS Career Goal", filters={"student_reference": s.name}):
			for com in frappe.get_all("EGS Commitment", filters={"career_goal_reference": cg.name}):
				frappe.delete_doc("EGS Commitment", com.name, force=True)
			frappe.delete_doc("EGS Career Goal", cg.name, force=True)
		frappe.delete_doc("EGS Student Participant", s.name, force=True)
	frappe.db.commit()

	# Ensure a coordinator exists for Jamia Millia Islamia / Delhi
	coord_name = "Delhi Test Coordinator"
	if not frappe.db.exists("EGS Coordinator", {"coordinator_name": coord_name}):
		frappe.get_doc({
			"doctype": "EGS Coordinator",
			"coordinator_name": coord_name,
			"role": "Coordinator",
			"city": "Delhi",
			"institution": "Jamia Millia Islamia",
		}).insert(ignore_permissions=True)
		frappe.db.commit()

	student = frappe.get_doc({
		"doctype": "EGS Student Participant",
		"student_name": "Bot Test Student",
		"student_email": test_email,
		"phone_number": "9123456777",
		"guardian_phone_number": "9876543277",
		"city": "Delhi",
		"university_college": "Jamia Millia Islamia",
		"faculty_department": "Faculty of Engineering & Technology",
		"course": "B.Tech Computer Science",
		"cohort_year": "2026",
		"event_status": "Checked-In",
		"current_5ds_stage": "DISCOVER",
	}).insert(ignore_permissions=True)
	frappe.db.commit()
	print(f"✓ Test student created: {student.name} ({student.student_name}) in DISCOVER stage")

	# 3. Test Bot Session Creation and Student Connection
	print("\n--- 3. Testing EGS Bot Session & Account Connection ---")
	chat_id = "777888999"
	# Clean up any existing session for this chat_id
	for bs in frappe.get_all("EGS Bot Session", filters={"chat_id": chat_id}):
		frappe.delete_doc("EGS Bot Session", bs.name, force=True)
	frappe.db.commit()

	# User sends /start with student ID
	start_payload = {
		"message": {
			"chat": {"id": chat_id},
			"text": f"/start {student.name}",
			"from": {"first_name": "Bot", "last_name": "Student"}
		}
	}
	res = bot_webhook(platform="telegram", **start_payload)
	assert res["status"] == "success"
	assert res["chat_id"] == chat_id

	# Verify session in DB
	session_names = frappe.get_all("EGS Bot Session", filters={"chat_id": chat_id})
	assert len(session_names) == 1
	session = frappe.get_doc("EGS Bot Session", session_names[0].name)
	assert session.student_participant == student.name
	assert session.platform == "Telegram"
	assert session.current_conversation_state == "DISCOVER_AWAITING_CHOICE"
	print("✓ Bot webhook successfully connected Telegram chat to EGS Student Participant and triggered DISCOVER prompt")

	# 4. Test Stage 2 (DISCOVER) - Escalation Flow ('I need help')
	print("\n--- 4. Testing Stage 2: 'I need help' -> Escalation Ticket Creation ---")
	help_payload = {
		"callback_query": {
			"id": "cb_help",
			"chat": {"id": chat_id},
			"message": {"chat": {"id": chat_id}},
			"data": "DISCOVER_NEED_HELP",
			"from": {"id": chat_id, "first_name": "Bot"}
		}
	}
	res_help = bot_webhook(platform="telegram", **help_payload)
	assert res_help["status"] == "success"

	# Verify Escalation Ticket and Check-in Log created
	tickets = frappe.get_all(
		"EGS Escalation Ticket",
		filters={"student_reference": student.name},
		fields=["name", "escalation_route", "assigned_coordinator", "status"]
	)
	assert len(tickets) >= 1, "Escalation ticket was not created!"
	ticket = tickets[0]
	assert ticket.escalation_route == "Stuck"
	assert ticket.status == "Open"
	assert ticket.assigned_coordinator is not None

	checkins = frappe.get_all(
		"EGS Check-in Log",
		filters={"student_reference": student.name},
		fields=["name", "triage_route", "student_response"]
	)
	assert len(checkins) >= 1
	assert checkins[0].triage_route == "Stuck"
	assert checkins[0].student_response == "I need help"
	print(f"✓ Support & Escalate cycle verified: EGS Escalation Ticket ({ticket.name}) assigned to {ticket.assigned_coordinator}")

	# 5. Test Stage 2 (DISCOVER) - Decision Flow ('Yes, decided')
	print("\n--- 5. Testing Stage 2: 'Yes, decided' -> DECIDE Transition ---")
	decided_payload = {
		"callback_query": {
			"id": "cb_decided",
			"chat": {"id": chat_id},
			"message": {"chat": {"id": chat_id}},
			"data": "DISCOVER_YES",
			"from": {"id": chat_id}
		}
	}
	res_dec = bot_webhook(platform="telegram", **decided_payload)
	assert res_dec["status"] == "success"
	session.reload()
	assert session.current_conversation_state == "DECIDE_AWAITING_GOAL"
	print("✓ 'Yes, decided' successfully transitioned session state to DECIDE_AWAITING_GOAL")

	# 6. Test Stage 3 (DECIDE) Flow - Goal and Vision Input
	print("\n--- 6. Testing Stage 3 (DECIDE): Goal & Vision Statement -> DEVELOP Advance ---")
	# 6.1 Send chosen career goal
	pw_records = frappe.get_all("EGS Career Pathway", limit=1)
	chosen_pathway = pw_records[0].name

	goal_msg = {
		"message": {
			"chat": {"id": chat_id},
			"text": chosen_pathway,
			"from": {"id": chat_id}
		}
	}
	res_goal = bot_webhook(platform="telegram", **goal_msg)
	assert res_goal["status"] == "success"
	session.reload()
	assert session.current_conversation_state == "DECIDE_AWAITING_VISION"
	assert session.get_context_data().get("pending_goal") == chosen_pathway
	print("✓ Career Goal captured; state advanced to DECIDE_AWAITING_VISION")

	# 6.2 Send Personal Vision Statement
	vision_text = "I aspire to build ethical AI solutions that empower underserved communities."
	vision_msg = {
		"message": {
			"chat": {"id": chat_id},
			"text": vision_text,
			"from": {"id": chat_id}
		}
	}
	res_vision = bot_webhook(platform="telegram", **vision_msg)
	assert res_vision["status"] == "success"
	session.reload()
	assert session.current_conversation_state == "DEVELOP_AWAITING_ACTION"

	# Verify backend student and career goal records
	student.reload()
	assert student.current_5ds_stage == "DEVELOP/PREPARE"
	assert student.final_chosen_career_goal == chosen_pathway
	assert student.personal_vision_statement == vision_text

	goals = frappe.get_all("EGS Career Goal", filters={"student_reference": student.name}, fields=["current_5ds_stage", "finalized_career_goal", "name"])
	assert len(goals) == 1
	assert goals[0].current_5ds_stage == "DEVELOP/PREPARE"
	assert goals[0].finalized_career_goal == chosen_pathway
	career_goal_id = goals[0].name
	print(f"✓ submit_decide_stage() and advance_to_develop() executed via bot: student and EGS Career Goal ({career_goal_id}) in DEVELOP/PREPARE")

	# 7. Test Stage 4 (DEVELOP) Flow - Action Item and Due Date Commitment
	print("\n--- 7. Testing Stage 4 (DEVELOP): Action Item & Due Date -> EGS Commitment ---")
	# 7.1 Send action item
	action_text = "Complete 3 full-length mock tests and review weak areas"
	action_msg = {
		"message": {
			"chat": {"id": chat_id},
			"text": action_text,
			"from": {"id": chat_id}
		}
	}
	res_act = bot_webhook(platform="telegram", **action_msg)
	assert res_act["status"] == "success"
	session.reload()
	assert session.current_conversation_state == "DEVELOP_AWAITING_DUE_DATE"
	assert session.get_context_data().get("pending_action") == action_text
	print("✓ Next action captured; state advanced to DEVELOP_AWAITING_DUE_DATE")

	# 7.2 Send invalid date format to test validation
	bad_date_msg = {
		"message": {
			"chat": {"id": chat_id},
			"text": "next monday",
			"from": {"id": chat_id}
		}
	}
	res_bad = bot_webhook(platform="telegram", **bad_date_msg)
	assert res_bad["status"] == "success"
	session.reload()
	assert session.current_conversation_state == "DEVELOP_AWAITING_DUE_DATE"
	print("✓ Invalid date handled gracefully with re-prompt")

	# 7.3 Send valid YYYY-MM-DD due date
	due_date_str = "2026-12-20"
	date_msg = {
		"message": {
			"chat": {"id": chat_id},
			"text": due_date_str,
			"from": {"id": chat_id}
		}
	}
	res_date = bot_webhook(platform="telegram", **date_msg)
	assert res_date["status"] == "success"
	session.reload()
	assert session.current_conversation_state == "IDLE"

	# Verify EGS Commitment record created in DB
	commitments = frappe.get_all(
		"EGS Commitment",
		filters={"career_goal_reference": career_goal_id},
		fields=["name", "action_required", "due_date", "progress_status"]
	)
	assert len(commitments) == 1
	com = commitments[0]
	assert com.action_required == action_text
	assert str(com.due_date) == due_date_str
	assert com.progress_status in ["Pending", "In Progress"]
	print(f"✓ Dated commitment verified: EGS Commitment ({com.name}) linked to goal with due date {com.due_date}")

	# 8. Test HTTP Guest Endpoint via requests
	print("\n--- 8. Testing Guest HTTP Webhook Router ---")
	guest_url = "http://127.0.0.1:8000/api/method/dreambig_egs.api.bot_webhook?platform=telegram"
	headers = {"Host": "egs.localhost", "Content-Type": "application/json"}
	http_payload = {
		"message": {
			"chat": {"id": chat_id},
			"text": "/status",
			"from": {"id": chat_id}
		}
	}
	r = requests.post(guest_url, json=http_payload, headers=headers)
	assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
	data = r.json().get("message", {})
	assert data.get("status") == "success"
	assert data.get("chat_id") == chat_id
	print("✓ HTTP POST /api/method/dreambig_egs.api.bot_webhook returned HTTP 200 with valid routing")

	# Clean up test records
	for bs in frappe.get_all("EGS Bot Session", filters={"chat_id": chat_id}):
		frappe.delete_doc("EGS Bot Session", bs.name, force=True)
	for t in frappe.get_all("EGS Escalation Ticket", filters={"student_reference": student.name}):
		frappe.delete_doc("EGS Escalation Ticket", t.name, force=True)
	for c in frappe.get_all("EGS Check-in Log", filters={"student_reference": student.name}):
		frappe.delete_doc("EGS Check-in Log", c.name, force=True)
	for cg in frappe.get_all("EGS Career Goal", filters={"student_reference": student.name}):
		for com in frappe.get_all("EGS Commitment", filters={"career_goal_reference": cg.name}):
			frappe.delete_doc("EGS Commitment", com.name, force=True)
		frappe.delete_doc("EGS Career Goal", cg.name, force=True)
	frappe.delete_doc("EGS Student Participant", student.name, force=True)
	frappe.db.commit()
	print("✓ Cleaned up test bot session, student, ticket, and commitment records")

	print("\n" + "=" * 60)
	print("ALL BOT ENGINE TESTS PASSED SUCCESSFULLY!")
	print("=" * 60)


if __name__ == "__main__":
	run_tests()
