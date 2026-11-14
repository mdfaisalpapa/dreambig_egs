# Copyright (c) 2026, Dream Big and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_url
from dreambig_egs.api.utils import portal_api


@frappe.whitelist(allow_guest=True)
@portal_api
def get_student_menu(for_user: str = None) -> dict:
    """
    Returns the dynamically tailored menu for the student participant based on their
    active 5Ds stage (DREAM, DISCOVER, DECIDE, DEVELOP, DELIVER) and event attendance.

    :param for_user: Student email or student ID
    """
    user_key = (for_user or "").strip()

    # Unauthenticated / Guest state
    if not user_key or user_key.lower() in ("guest", "none", "null", "undefined"):
        reg_url = f"{get_url()}/egs-student-participant/new"
        return {
            "authenticated": False,
            "welcome_message": (
                "🎓 *Welcome to Dream Big Early Goal Setting (EGS)!*\n\n"
                "🌟 _No student should be left unguided and be left behind._\n\n"
                "Please tap *📱 Share Contact to Login* below to link your student profile, "
                "or register if you are new:"
            ),
            "options": [
                {
                    "id": "share_contact",
                    "label": "📱 Share Contact to Login",
                    "desc": "1-Click Verify Mobile Number",
                    "action": "share_contact",
                    "request_contact": True,
                },
                {
                    "id": "register",
                    "label": "📝 Register for EGS",
                    "desc": "Join First-Year Cohort",
                    "action": "open_url",
                    "url": reg_url,
                },
            ],
            "count": 2,
        }

    # Locate student participant
    student = frappe.db.get_value(
        "EGS Student Participant",
        {"name": user_key},
        ["name", "student_name", "student_email", "phone_number", "current_5ds_stage", "event_status", "access_token", "city", "course", "university_college", "final_chosen_career_goal"],
        as_dict=True,
    )
    if not student:
        student = frappe.db.get_value(
            "EGS Student Participant",
            {"student_email": user_key},
            ["name", "student_name", "student_email", "phone_number", "current_5ds_stage", "event_status", "access_token", "city", "course", "university_college", "final_chosen_career_goal"],
            as_dict=True,
        )

    if not student:
        return {
            "authenticated": False,
            "welcome_message": "⚠️ Could not locate your student participant record. Please register or tap below to re-verify:",
            "options": [
                {
                    "id": "share_contact",
                    "label": "📱 Share Contact to Login",
                    "desc": "1-Click Verify Mobile Number",
                    "action": "share_contact",
                    "request_contact": True,
                }
            ],
            "count": 1,
        }

    stage = (student.get("current_5ds_stage") or "DREAM").upper()
    event_status = student.get("event_status") or "Registered"
    token = student.get("access_token") or ""
    stu_id = student.get("name")
    student_name = student.get("student_name") or "Student"

    # Stage Badge & Greeting
    stage_badges = {
        "DREAM": "💭 Stage 1: DREAM",
        "DISCOVER": "🔍 Stage 2: DISCOVER",
        "DECIDE": "🎯 Stage 3: DECIDE",
        "DEVELOP": "🚀 Stage 4: DEVELOP / PREPARE",
        "DELIVER": "🏆 Stage 5: DELIVER",
    }
    badge = stage_badges.get(stage, f"🌟 Stage: {stage}")

    welcome = (
        f"🎓 *Welcome, {student_name}!*\n"
        f"🆔 `{stu_id}` | 🏷️ *{badge}*\n\n"
        f"Select an option below to manage your Dream Big journey:"
    )

    options = []

    # 1. Event Check-in (if not yet checked in)
    if event_status != "Checked-In":
        options.append({
            "id": "event_checkin",
            "label": "🎟️ Event Check-In",
            "desc": "Confirm your presence at the EGS orientation",
            "action": "call_action",
        })

    # 2. Stage-Specific Primary Action
    if "DREAM" in stage:
        options.append({
            "id": "explore_careers",
            "label": "💭 Explore Dream Careers",
            "desc": "Select up to 5 aspirational career paths",
            "action": "call_action",
        })
    elif "DISCOVER" in stage:
        options.append({
            "id": "view_shortlist",
            "label": "📋 View Shortlisted Careers",
            "desc": "Inspect and refine your top career choices",
            "action": "call_action",
        })
        options.append({
            "id": "advance_decide",
            "label": "🎯 Finalize Career Decision",
            "desc": "Lock in your final career path & promise",
            "action": "call_action",
        })
    elif "DECIDE" in stage:
        options.append({
            "id": "view_commitment",
            "label": "🎯 My Chosen Career & Promise",
            "desc": "Inspect your chosen goal & vision statement",
            "action": "call_action",
        })
        options.append({
            "id": "advance_develop",
            "label": "🚀 Advance to DEVELOP Stage",
            "desc": "Unlock mentorship & skill milestones",
            "action": "call_action",
        })
    elif "DEVELOP" in stage:
        options.append({
            "id": "mentorship",
            "label": "🤝 Mentorship & Milestones",
            "desc": "View your mentor match and progress",
            "action": "call_action",
        })
    elif "DELIVER" in stage:
        options.append({
            "id": "certificates",
            "label": "🏆 Accomplishments & Certificates",
            "desc": "View validated milestones and achievements",
            "action": "call_action",
        })

    # 3. Universal Student Services
    options.append({
        "id": "student_profile",
        "label": "👤 My Student Profile",
        "desc": "View academic & contact details",
        "action": "call_action",
    })
    options.append({
        "id": "coordinator_help",
        "label": "🆘 Need Help / Contact Coordinator",
        "desc": "Raise an escalation ticket with your cohort lead",
        "action": "call_action",
    })
    options.append({
        "id": "open_webapp",
        "label": "📱 Open Dream Big WebApp",
        "desc": "Interactive PWA Dashboard",
        "action": "open_url",
        "url": f"{get_url()}/my-dream-big?id={stu_id}&key={token}",
    })

    # 4. Logout / Switch User
    options.append({
        "id": "logout",
        "label": "🚪 Logout / Switch Account",
        "desc": "Unlink this chat account",
        "action": "logout",
    })

    return {
        "authenticated": True,
        "student_id": stu_id,
        "student_name": student_name,
        "stage": stage,
        "event_status": event_status,
        "welcome_message": welcome,
        "options": options,
        "count": len(options),
    }
