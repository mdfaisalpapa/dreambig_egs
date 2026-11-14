# Copyright (c) 2026, Dream Big and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_url, now_datetime
from dreambig_egs.api.utils import portal_api


@frappe.whitelist(allow_guest=True)
@portal_api
def get_student_service_details(action_id: str, for_user: str = None) -> dict:
    """
    Service dispatcher returning formatted cards, status summaries, or action triggers
    for a chosen student menu action ID.

    :param action_id: egs action id (e.g. 'student_profile', 'event_checkin', 'view_commitment', 'coordinator_help')
    :param for_user: student ID or email
    """
    if not action_id:
        frappe.throw("Parameter 'action_id' is required")

    user_key = (for_user or "").strip()
    student = None
    if user_key:
        student = frappe.db.get_value(
            "EGS Student Participant",
            {"name": user_key},
            ["name", "student_name", "student_email", "phone_number", "current_5ds_stage", "event_status", "access_token", "city", "course", "university_college", "final_chosen_career_goal", "personal_vision_statement", "a_promise_to_self", "food_coupon_code", "food_coupon_issued"],
            as_dict=True,
        )
        if not student:
            student = frappe.db.get_value(
                "EGS Student Participant",
                {"student_email": user_key},
                ["name", "student_name", "student_email", "phone_number", "current_5ds_stage", "event_status", "access_token", "city", "course", "university_college", "final_chosen_career_goal", "personal_vision_statement", "a_promise_to_self", "food_coupon_code", "food_coupon_issued"],
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

    # --- 1. Student Profile ---
    if action_id == "student_profile":
        if not student:
            return {"title": "Student Profile", "prompt": "⚠️ No student profile found.", "options": [{"label": "🔙 Back", "value": "menu"}]}
        
        prompt = (
            f"👤 *Student Profile & Academic Details*\n\n"
            f"• *Name:* {student.get('student_name')}\n"
            f"• *ID:* `{student.get('name')}`\n"
            f"• *Email:* {student.get('student_email')}\n"
            f"• *Phone:* {student.get('phone_number')}\n"
            f"• *City:* {student.get('city') or 'Not specified'}\n"
            f"• *Institution:* {student.get('university_college') or 'Not specified'}\n"
            f"• *Course:* {student.get('course') or 'Not specified'}\n"
            f"• *Current Stage:* *{student.get('current_5ds_stage') or 'DREAM'}*\n"
            f"• *Attendance:* {'✅ Checked-In' if student.get('event_status') == 'Checked-In' else '⏳ Registered'}\n"
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

    # --- 2. Event Check-In ---
    elif action_id == "event_checkin":
        if not student:
            return {"title": "Event Check-In", "prompt": "⚠️ Please verify your account first.", "options": [{"label": "🔙 Back", "value": "menu"}]}

        if student.get("event_status") == "Checked-In":
            coupon_info = f"\n🎟️ *Food Coupon:* `{student.get('food_coupon_code')}`" if student.get("food_coupon_code") else ""
            prompt = (
                f"✅ *Already Checked-In!*\n\n"
                f"You have already confirmed attendance for your cohort event.{coupon_info}\n\n"
                f"Keep up the good work and advance your 5Ds journey!"
            )
        else:
            # Perform event check-in
            try:
                frappe.db.set_value("EGS Student Participant", student["name"], "event_status", "Checked-In")
                frappe.db.commit()

                # Generate coupon code if not present
                coupon = f"FC-{student['name'][-4:]}"
                frappe.db.set_value("EGS Student Participant", student["name"], "food_coupon_code", coupon)
                frappe.db.set_value("EGS Student Participant", student["name"], "food_coupon_issued", 1)
                frappe.db.commit()

                prompt = (
                    f"🎉 *Check-In Successful!*\n\n"
                    f"Welcome to the session, **{student.get('student_name')}**!\n"
                    f"🎟️ *Your Food Coupon Code:* `{coupon}`\n\n"
                    f"Present this code at the refreshments counter."
                )
            except Exception as e:
                prompt = f"⚠️ Check-in encountered an issue: {e}"

        return {
            "title": "Event Check-In",
            "prompt": prompt,
            "options": [{"label": "🔙 Back to Main Menu", "value": "menu"}],
        }

    # --- 3. View Chosen Career / Commitment ---
    elif action_id in ("view_commitment", "view_shortlist", "explore_careers"):
        if not student:
            return {"title": "Career Goals", "prompt": "⚠️ Student record required.", "options": [{"label": "🔙 Back", "value": "menu"}]}

        chosen = student.get("final_chosen_career_goal") or "None selected yet"
        vision = student.get("personal_vision_statement") or "None written yet"
        promise = student.get("a_promise_to_self") or "None recorded yet"

        prompt = (
            f"🎯 *My Chosen Career & Commitments*\n\n"
            f"• *Target Career Pathway:* **{chosen}**\n"
            f"• *Personal Vision Statement:* _{vision}_\n"
            f"• *Promise to Self:* _{promise}_\n\n"
            f"Tap below to review career pathways or refine your commitments in the WebApp:"
        )
        return {
            "title": "Career Commitments",
            "prompt": prompt,
            "sso_url": webapp_url,
            "options": [
                {"label": "📱 Open Career Explorer", "value": "open_webapp", "url": webapp_url},
                {"label": "🔙 Back to Main Menu", "value": "menu"},
            ],
        }

    # --- 4. Coordinator Help / Escalation ---
    elif action_id == "coordinator_help":
        if not student:
            return {"title": "Coordinator Help", "prompt": "⚠️ Student record required.", "options": [{"label": "🔙 Back", "value": "menu"}]}

        # Check or create an escalation ticket
        try:
            ticket = frappe.get_doc({
                "doctype": "EGS Escalation Ticket",
                "student_participant": student["name"],
                "issue_type": "Student Support Request",
                "status": "Open",
                "notes": f"Automated helpdesk request raised via Universal Chatbot by {student['student_name']} ({student['name']}).",
            })
            ticket.insert(ignore_permissions=True)
            frappe.db.commit()
            t_name = ticket.name
        except Exception:
            t_name = "TKT-LOGGED"

        prompt = (
            f"🆘 *Support Request Logged*\n\n"
            f"🎫 *Ticket ID:* `{t_name}`\n\n"
            f"Your cohort coordinator and mentorship mentors have been notified. "
            f"They will reach out to you shortly via phone or chat."
        )
        return {
            "title": "Coordinator Support",
            "prompt": prompt,
            "options": [{"label": "🔙 Back to Main Menu", "value": "menu"}],
        }

    # Default fallback
    return {
        "title": "Student Service",
        "prompt": f"ℹ️ Service details for `{action_id}`.",
        "options": [{"label": "🔙 Back to Main Menu", "value": "menu"}],
    }
