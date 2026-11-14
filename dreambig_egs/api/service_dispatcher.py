# Copyright (c) 2026, Dream Big and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_url, now_datetime
from dreambig_egs.api.utils import portal_api


@frappe.whitelist(allow_guest=True)
@portal_api
def get_student_service_details(action_id: str, for_user: str = None) -> dict:
    """
    Service dispatcher aligned with the Dream Big EGS 5Ds Web Portal and the
    Follow-up Mechanism Framework (Register -> Check-ins -> 3-Route Escalation).

    :param action_id: Action identifier
    :param for_user: Student ID or email
    """
    if not action_id:
        frappe.throw("Parameter 'action_id' is required")

    user_key = (for_user or "").strip()
    student = None
    if user_key:
        student = frappe.db.get_value(
            "EGS Student Participant",
            {"name": user_key},
            [
                "name",
                "student_name",
                "student_email",
                "phone_number",
                "guardian_phone_number",
                "current_5ds_stage",
                "event_status",
                "access_token",
                "city",
                "course",
                "university_college",
                "final_chosen_career_goal",
                "personal_vision_statement",
                "a_promise_to_self",
                "food_coupon_code",
                "food_coupon_issued",
                "date_of_decision",
            ],
            as_dict=True,
        )
        if not student:
            student = frappe.db.get_value(
                "EGS Student Participant",
                {"student_email": user_key},
                [
                    "name",
                    "student_name",
                    "student_email",
                    "phone_number",
                    "guardian_phone_number",
                    "current_5ds_stage",
                    "event_status",
                    "access_token",
                    "city",
                    "course",
                    "university_college",
                    "final_chosen_career_goal",
                    "personal_vision_statement",
                    "a_promise_to_self",
                    "food_coupon_code",
                    "food_coupon_issued",
                    "date_of_decision",
                ],
                as_dict=True,
            )

    stu_id = student.get("name") if student else ""
    token = student.get("access_token") if student else ""
    webapp_url = f"{get_url()}/my-dream-big?id={stu_id}&key={token}" if stu_id else f"{get_url()}/my-dream-big"

    # --- 0. Registration Form Link ---
    if action_id == "register":
        reg_url = f"{get_url()}/egs-student-participant/new"
        return {
            "title": "Register for EGS",
            "prompt": (
                "📝 *Join the Dream Big Early Goal Setting (EGS) Cohort!*\n\n"
                "First-Year undergraduate students can register online using the link below:\n\n"
                f"🔗 [Click here to Open Registration Form]({reg_url})\n\n"
                "After registering, return here and tap *📱 Share Contact to Login*."
            ),
            "sso_url": reg_url,
            "options": [
                {"label": "📝 Open Registration Form", "value": "open_reg", "url": reg_url},
                {"label": "🔙 Back to Main Menu", "value": "menu"},
            ],
        }

    # --- 1. Student Profile & Register Status (Layer 1: Register) ---
    if action_id == "student_profile":
        if not student:
            return {"title": "Student Profile", "prompt": "⚠️ No student profile found.", "options": [{"label": "🔙 Back", "value": "menu"}]}

        guardian_str = f"\n• *Guardian Phone:* `{student.get('guardian_phone_number')}`" if student.get("guardian_phone_number") else "\n• *Guardian Phone:* _(Missing - needed for safeguarding)_"

        prompt = (
            f"👤 *Student Profile & Register Status*\n\n"
            f"• *Name:* **{student.get('student_name')}**\n"
            f"• *ID:* `{student.get('name')}`\n"
            f"• *Institution:* {student.get('university_college') or 'Not specified'}\n"
            f"• *Course:* {student.get('course') or 'Not specified'}\n"
            f"• *City:* {student.get('city') or 'Not specified'}\n"
            f"• *Student Mobile:* `{student.get('phone_number')}`{guardian_str}\n"
            f"• *Active 5Ds Stage:* *{student.get('current_5ds_stage') or 'DREAM'}*\n"
            f"• *Orientation Attendance:* {'✅ Checked-In' if student.get('event_status') == 'Checked-In' else '⏳ Registered'}\n"
        )
        return {
            "title": "Student Profile",
            "prompt": prompt,
            "sso_url": webapp_url,
            "options": [
                {"label": "📱 Open PWA Dashboard", "value": "open_webapp", "url": webapp_url},
                {"label": "🔙 Back to Main Menu", "value": "menu"},
            ],
        }

    # --- 2. Orientation Event Check-In & Meal Coupon ---
    elif action_id == "event_checkin":
        if not student:
            return {"title": "Event Check-In", "prompt": "⚠️ Please verify your account first.", "options": [{"label": "🔙 Back", "value": "menu"}]}

        if student.get("event_status") == "Checked-In":
            coupon_info = f"\n🎟️ *Food Coupon:* `{student.get('food_coupon_code')}`" if student.get("food_coupon_code") else ""
            prompt = (
                f"✅ *Already Checked-In!*\n\n"
                f"You have confirmed your presence at the cohort orientation session.{coupon_info}\n\n"
                f"Your stage is now active. Explore careers or complete your check-in."
            )
        else:
            try:
                frappe.db.set_value("EGS Student Participant", student["name"], "event_status", "Checked-In")
                if getattr(student, "current_5ds_stage", None) in (None, "", "DREAM"):
                    frappe.db.set_value("EGS Student Participant", student["name"], "current_5ds_stage", "DISCOVER")

                coupon = f"MEAL-{frappe.generate_hash(length=6).upper()}"
                frappe.db.set_value("EGS Student Participant", student["name"], "food_coupon_code", coupon)
                frappe.db.set_value("EGS Student Participant", student["name"], "food_coupon_issued", 1)
                frappe.db.commit()

                prompt = (
                    f"🎉 *Orientation Check-In Successful!*\n\n"
                    f"Welcome to the session, **{student.get('student_name')}**!\n"
                    f"🎟️ *Your Digital Food Coupon:* `{coupon}`\n\n"
                    f"Present this passcode at the lunch/refreshment counter.\n"
                    f"Your 5Ds stage has advanced to **Stage 2: DISCOVER**!"
                )
            except Exception as e:
                prompt = f"⚠️ Check-in encountered an issue: {e}"

        return {
            "title": "Event Check-In",
            "prompt": prompt,
            "options": [{"label": "🔙 Back to Main Menu", "value": "menu"}],
        }

    # --- 3. Follow-Up Check-In Flow (Layer 2: Nudge & Self-Assessment) ---
    elif action_id in ("check_in", "followup_checkin", "view_shortlist"):
        if not student:
            return {"title": "Periodic Check-In", "prompt": "⚠️ Student record required.", "options": [{"label": "🔙 Back", "value": "menu"}]}

        # Fetch shortlisted career choices
        choices = frappe.get_all(
            "EGS Student Career Choice",
            filters={"parent": student["name"], "parenttype": "EGS Student Participant"},
            fields=["career_pathway", "notes"],
            order_by="idx asc",
        )
        shortlist_str = "\n".join([f"  {idx+1}. {c['career_pathway']}" for idx, c in enumerate(choices)]) if choices else "  _(No careers shortlisted yet)_"

        # Check latest Check-in log
        last_log = frappe.db.get_value(
            "EGS Check-in Log",
            {"student_reference": student["name"]},
            ["check_in_round", "triage_route", "student_response", "next_dated_action"],
            as_dict=True,
            order_by="creation desc",
        )
        round_num = (last_log.get("check_in_round") or 0) + 1 if last_log else 1

        prompt = (
            f"📋 *Round {round_num} Follow-Up Check-In*\n\n"
            f"Your current shortlisted pathways:\n{shortlist_str}\n\n"
            f"*Self-Assessment Question:*\n"
            f"_Have you narrowed your shortlist and made progress towards your goal?_\n\n"
            f"Select one of the 3 assessment options below:"
        )
        return {
            "title": "Periodic Check-In",
            "prompt": prompt,
            "options": [
                {"label": "① Yes, on track & decided", "value": "checkin_yes"},
                {"label": "② Still deciding / researching", "value": "checkin_still"},
                {"label": "③ I need help (Stuck)", "value": "checkin_help"},
                {"label": "🔙 Back to Main Menu", "value": "menu"},
            ],
        }

    # --- 3b. Handle Check-In Responses (Layer 3: Triage & Escalation) ---
    elif action_id == "checkin_yes":
        if not student:
            return {"title": "Check-In", "prompt": "⚠️ Student record required.", "options": [{"label": "🔙 Back", "value": "menu"}]}

        # Log Route 1: On Track
        try:
            log_doc = frappe.get_doc({
                "doctype": "EGS Check-in Log",
                "student_reference": student["name"],
                "student_response": "Yes decided",
                "triage_route": "On track",
                "next_dated_action": f"Decided goal: {student.get('final_chosen_career_goal') or 'Self-affirmed'}",
            })
            log_doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception:
            pass

        prompt = (
            f"🌟 *Route 1: On Track!*\n\n"
            f"Excellent work, **{student.get('student_name')}**! Your progress has been recorded in the central register.\n\n"
            f"Because you are on track, you are eligible for **Stage 4 Mentorship Matching** in your chosen field:\n"
            f"🎯 *Target Pathway:* **{student.get('final_chosen_career_goal') or 'Selected Career'}**\n\n"
            f"Tap below to review your commitments or explore mentor matching in the WebApp:"
        )
        return {
            "title": "On Track - Route 1",
            "prompt": prompt,
            "sso_url": webapp_url,
            "options": [
                {"label": "🤝 View Mentorship & Milestones", "value": "mentorship"},
                {"label": "📱 Open Dashboard WebApp", "value": "open_webapp", "url": webapp_url},
                {"label": "🔙 Back to Main Menu", "value": "menu"},
            ],
        }

    elif action_id == "checkin_still":
        if not student:
            return {"title": "Check-In", "prompt": "⚠️ Student record required.", "options": [{"label": "🔙 Back", "value": "menu"}]}

        try:
            log_doc = frappe.get_doc({
                "doctype": "EGS Check-in Log",
                "student_reference": student["name"],
                "student_response": "Still deciding",
                "triage_route": "On track",
                "next_dated_action": "Exploring top 5 shortlisted career brochures",
            })
            log_doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception:
            pass

        prompt = (
            f"🔍 *Exploring & Deciding*\n\n"
            f"Take your time, **{student.get('student_name')}**! Review the curriculum requirements, exam timelines, and day-in-the-life profiles of your top choices.\n\n"
            f"💡 *Remember:* Implementation research shows that narrowing to 1 specific goal with a dated deadline gives the highest success rate."
        )
        return {
            "title": "Still Deciding",
            "prompt": prompt,
            "options": [
                {"label": "💭 Explore Career Pathways", "value": "explore_careers"},
                {"label": "📱 Open Career Explorer WebApp", "value": "open_webapp", "url": webapp_url},
                {"label": "🔙 Back to Main Menu", "value": "menu"},
            ],
        }

    elif action_id == "checkin_help":
        if not student:
            return {"title": "Check-In", "prompt": "⚠️ Student record required.", "options": [{"label": "🔙 Back", "value": "menu"}]}

        # Log Route 2: Stuck -> Triggers Escalation Ticket to Teacher-Mentor Anchor
        ticket_id = "LOGGED"
        try:
            log_doc = frappe.get_doc({
                "doctype": "EGS Check-in Log",
                "student_reference": student["name"],
                "student_response": "I need help",
                "triage_route": "Stuck",
                "next_dated_action": "Awaiting conversation with Teacher-Mentor",
            })
            log_doc.insert(ignore_permissions=True)
            frappe.db.commit()

            # Find generated escalation ticket
            t_doc = frappe.get_all(
                "EGS Escalation Ticket",
                filters={"triggering_check_in": log_doc.name},
                fields=["name", "assigned_coordinator"],
                limit=1,
            )
            if t_doc:
                ticket_id = t_doc[0].name
        except Exception:
            ticket_id = "ESC-STUCK"

        prompt = (
            f"🆘 *Route 2: Escalation to Teacher-Mentor Anchor*\n\n"
            f"We hear you, **{student.get('student_name')}**! You don't have to navigate this alone.\n\n"
            f"🎫 *Escalation Ticket:* `{ticket_id}`\n"
            f"🏫 *Institution:* {student.get('university_college') or 'College Anchor'}\n\n"
            f"An amber flag has been raised on your institution anchor's triage board. Your designated **Teacher-Mentor** has been notified and will schedule a 1-on-1 counseling check-in."
        )
        return {
            "title": "Teacher-Mentor Escalation",
            "prompt": prompt,
            "options": [
                {"label": "📱 Open Dashboard WebApp", "value": "open_webapp", "url": webapp_url},
                {"label": "🔙 Back to Main Menu", "value": "menu"},
            ],
        }

    # --- 4. Career Pathways & Explorer (Stage 1 & 2) ---
    elif action_id == "explore_careers":
        prompt = (
            f"💭 *Explore DREAM BIG Career Pathways*\n\n"
            f"Our curriculum covers 19 career clusters across 2 major tracks:\n\n"
            f"👔 *Track 1: Employee Category (Individual Leadership)*\n"
            f"• Civil Services & Government (IAS/IPS/IFS)\n"
            f"• Regulatory & Public Sector (RBI, SEBI)\n"
            f"• Financial, Scientific, Academic & Arts\n\n"
            f"🏢 *Track 2: Employer Category (Enterprise & Institution Building)*\n"
            f"• Technology & Digital Innovation\n"
            f"• Entrepreneurship & Social Enterprise\n"
            f"• Healthcare, Education & Consulting\n\n"
            f"Tap below to shortlist up to 5 pathways in the WebApp:"
        )
        return {
            "title": "Explore Careers",
            "prompt": prompt,
            "sso_url": webapp_url,
            "options": [
                {"label": "📱 Open Interactive Explorer", "value": "open_webapp", "url": webapp_url},
                {"label": "🔙 Back to Main Menu", "value": "menu"},
            ],
        }

    # --- 5. Chosen Career & Commitment (Stage 3: DECIDE) ---
    elif action_id in ("view_commitment", "advance_decide"):
        if not student:
            return {"title": "Career Commitments", "prompt": "⚠️ Student record required.", "options": [{"label": "🔙 Back", "value": "menu"}]}

        chosen = student.get("final_chosen_career_goal") or "None locked in yet"
        vision = student.get("personal_vision_statement") or "None written yet"
        promise = student.get("a_promise_to_self") or "None recorded yet"
        date_dec = student.get("date_of_decision") or "Pending"

        prompt = (
            f"🎯 *Stage 3: DECIDE — A Promise to Self*\n\n"
            f"• *Target Career Pathway:* **{chosen}**\n"
            f"• *Decision Date:* {date_dec}\n"
            f"• *Personal Vision Statement:*\n  _{vision}_\n"
            f"• *Promise to Self:*\n  _{promise}_\n\n"
            f"Locking in your single path unlocks personalized mentor matching in Stage 4."
        )
        return {
            "title": "Stage 3: DECIDE",
            "prompt": prompt,
            "sso_url": webapp_url,
            "options": [
                {"label": "🚀 Advance to DEVELOP", "value": "advance_develop"},
                {"label": "📱 Refine in WebApp", "value": "open_webapp", "url": webapp_url},
                {"label": "🔙 Back to Main Menu", "value": "menu"},
            ],
        }

    # --- 6. Advance Stage to DEVELOP (Stage 4) ---
    elif action_id == "advance_develop":
        if not student:
            return {"title": "Advance Stage", "prompt": "⚠️ Student record required.", "options": [{"label": "🔙 Back", "value": "menu"}]}

        if not student.get("final_chosen_career_goal"):
            return {
                "title": "Advance Stage",
                "prompt": (
                    "⚠️ *Cannot advance to DEVELOP yet!*\n\n"
                    "You must first finalize your single target career goal and vision statement in the **DECIDE** stage before unlocking DEVELOP mentorship."
                ),
                "options": [
                    {"label": "🎯 Finalize Decision in WebApp", "value": "open_webapp", "url": webapp_url},
                    {"label": "🔙 Back to Main Menu", "value": "menu"},
                ],
            }

        try:
            frappe.db.set_value("EGS Student Participant", student["name"], "current_5ds_stage", "DEVELOP/PREPARE")
            frappe.db.commit()
            prompt = (
                f"🚀 *Welcome to Stage 4: DEVELOP / PREPARE!*\n\n"
                f"Congratulations, **{student.get('student_name')}**! Your profile is now marked as **Mentor-Ready**.\n\n"
                f"Our coordinators are pairing you with an accomplished industry mentor in:\n"
                f"🎯 **{student.get('final_chosen_career_goal')}**"
            )
        except Exception as e:
            prompt = f"⚠️ Could not advance stage: {e}"

        return {
            "title": "Stage 4: DEVELOP",
            "prompt": prompt,
            "options": [
                {"label": "🤝 View Mentorship", "value": "mentorship"},
                {"label": "🔙 Back to Main Menu", "value": "menu"},
            ],
        }

    # --- 7. Mentorship & Milestones (Stage 4) ---
    elif action_id == "mentorship":
        if not student:
            return {"title": "Mentorship", "prompt": "⚠️ Student record required.", "options": [{"label": "🔙 Back", "value": "menu"}]}

        # Query active mentorship match
        matches = frappe.get_all(
            "EGS Mentorship Match",
            filters={"student_reference": student["name"]},
            fields=["name", "mentor_reference", "match_status", "start_date"],
            limit=1,
        )

        if matches:
            m = matches[0]
            mentor_doc = frappe.get_doc("EGS Mentor Profile", m["mentor_reference"])
            prompt = (
                f"🤝 *Active Mentorship Match*\n\n"
                f"• *Mentor:* **{mentor_doc.mentor_name}**\n"
                f"• *Organization:* {mentor_doc.organization or 'Industry Leader'}\n"
                f"• *Designation:* {mentor_doc.designation or 'Expert'}\n"
                f"• *Status:* {m.get('match_status') or 'Active'}\n"
                f"• *Start Date:* {m.get('start_date') or 'Recently matched'}\n\n"
                f"🔒 *Safeguarding Protocol:* All sessions are supervised with your institution anchor."
            )
        else:
            prompt = (
                f"🤝 *Mentorship Matching in Progress*\n\n"
                f"• *Field of Interest:* **{student.get('final_chosen_career_goal') or 'Under Evaluation'}**\n"
                f"• *Match Criteria:* Rigorous interest-aligned pairing\n\n"
                f"Our regional coordinator is matching you with an accredited mentor. You will receive an invitation once scheduled."
            )

        return {
            "title": "Mentorship Matching",
            "prompt": prompt,
            "options": [
                {"label": "📱 Open Mentorship Portal", "value": "open_webapp", "url": webapp_url},
                {"label": "🔙 Back to Main Menu", "value": "menu"},
            ],
        }

    # --- 8. Coordinator Help (Manual Escalation) ---
    elif action_id == "coordinator_help":
        if not student:
            return {"title": "Coordinator Help", "prompt": "⚠️ Student record required.", "options": [{"label": "🔙 Back", "value": "menu"}]}

        ticket_name = "TKT-LOGGED"
        try:
            ticket = frappe.get_doc({
                "doctype": "EGS Escalation Ticket",
                "student_reference": student["name"],
                "escalation_route": "Stuck",
                "status": "Open",
                "resolution_notes": f"Manual student support request raised via Telegram Bot by {student['student_name']} ({student['name']}).",
            })
            ticket.insert(ignore_permissions=True)
            frappe.db.commit()
            ticket_name = ticket.name
        except Exception:
            pass

        prompt = (
            f"🆘 *Support Request Logged*\n\n"
            f"🎫 *Ticket ID:* `{ticket_name}`\n"
            f"🏫 *Institution:* {student.get('university_college') or 'Institution Lead'}\n\n"
            f"Your cohort captain and designated teacher-mentor have been flagged. They will reach out to you directly."
        )
        return {
            "title": "Coordinator Support",
            "prompt": prompt,
            "options": [{"label": "🔙 Back to Main Menu", "value": "menu"}],
        }

    # Fallback
    return {
        "title": "Student Service",
        "prompt": f"ℹ️ Service details for `{action_id}`.",
        "options": [{"label": "🔙 Back to Main Menu", "value": "menu"}],
    }
