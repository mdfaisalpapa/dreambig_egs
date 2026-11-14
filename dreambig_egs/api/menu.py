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
    active 5Ds stage (DREAM, DISCOVER, DECIDE, DEVELOP, DELIVER), event attendance,
    and Follow-Up Check-In status.

    :param for_user: Student email or student ID
    """
    user_key = (for_user or "").strip()

    # Unauthenticated / Guest state (Layer 1: Register in the room)
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
                    "action": "register",
                    "url": reg_url,
                },
            ],
            "count": 2,
        }

    # Locate student participant
    student = frappe.db.get_value(
        "EGS Student Participant",
        {"name": user_key},
        [
            "name",
            "student_name",
            "student_email",
            "phone_number",
            "current_5ds_stage",
            "event_status",
            "access_token",
            "city",
            "course",
            "university_college",
            "final_chosen_career_goal",
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
                "current_5ds_stage",
                "event_status",
                "access_token",
                "city",
                "course",
                "university_college",
                "final_chosen_career_goal",
            ],
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

    # Stage Badge matching Web Portal
    stage_badges = {
        "DREAM": "Stage 1: DREAM",
        "DISCOVER": "Stage 2: DISCOVER",
        "DECIDE": "Stage 3: DECIDE",
        "DEVELOP": "Stage 4: DEVELOP / PREPARE",
        "DEVELOP/PREPARE": "Stage 4: DEVELOP / PREPARE",
        "DELIVER": "Stage 5: DELIVER",
    }
    badge = stage_badges.get(stage, f"Stage: {stage}")

    welcome = (
        f"🎓 *Welcome, {student_name}!*\n"
        f"🆔 `{stu_id}` | 🏷️ *{badge}*\n\n"
        f"Select an option below to manage your Dream Big journey:"
    )

    # Fetch student's shortlisted goals count
    saved_goals_count = frappe.db.count(
        "EGS Student Career Choice",
        {"parent": stu_id, "parenttype": "EGS Student Participant"}
    )

    options = []

    # RULE 1: If NOT Checked-In, ONLY Event Check-In is visible (along with WebApp & Logout)
    if event_status != "Checked-In":
        welcome = (
            f"🎓 *Welcome, {student_name}!*\n"
            f"🆔 `{stu_id}` | 🏷️ *{badge}*\n\n"
            f"📍 *Event Attendance Required*\n"
            f"You have registered for the Dream Big EGS Orientation. Please check in on the day of the event using the QR code at the venue to unlock Stage 1 (DREAM) & your Food Coupon."
        )
        options.append({
            "id": "event_checkin",
            "label": "🎟️ Event Check-In",
            "desc": "Check in using event QR / passcode",
            "action": "event_checkin",
        })
        options.append({
            "id": "open_webapp",
            "label": "📱 Open Dream Big WebApp",
            "desc": "View Event Details & Registration",
            "action": "open_webapp",
            "url": f"{get_url()}/my-dream-big?id={stu_id}&key={token}",
        })
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

    # RULE 2: If Checked-In, check 5Ds Stage & Goals
    # Stage 1: DREAM - On-the-spot selection of 5 career goals
    if "DREAM" in stage or saved_goals_count < 5:
        welcome = (
            f"🎓 *Welcome, {student_name}!*\n"
            f"🆔 `{stu_id}` | 🏷️ *Stage 1: DREAM*\n\n"
            f"🎉 *Checked in to Event!*\n"
            f"You have selected *{saved_goals_count}/5* Dream Big career goals.\n"
            f"Complete your on-the-spot selection of 5 goals to advance to Stage 2: DISCOVER."
        )
        options.append({
            "id": "select_5_goals",
            "label": f"💭 Select 5 Goals ({saved_goals_count}/5)",
            "desc": "Choose 5 aspirational career paths",
            "action": "select_5_goals",
        })
        options.append({
            "id": "student_profile",
            "label": "👤 My Profile & Meal Coupon",
            "desc": "Registration info & food coupon",
            "action": "student_profile",
        })
        options.append({
            "id": "open_webapp",
            "label": "📱 Open Dream Big WebApp",
            "desc": "Interactive 5Ds Dashboard",
            "action": "open_webapp",
            "url": f"{get_url()}/my-dream-big?id={stu_id}&key={token}",
        })
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
            "stage": "DREAM",
            "event_status": event_status,
            "welcome_message": welcome,
            "options": options,
            "count": len(options),
        }

    # RULE 3: Checked-In AND 5 Goals Selected -> Stages 2 to 5
    if "DISCOVER" in stage:
        options.append({
            "id": "view_shortlist",
            "label": "📋 View Shortlist (5 Goals)",
            "desc": "Inspect top 5 choices",
            "action": "view_shortlist",
        })
        options.append({
            "id": "followup_checkin",
            "label": "📋 Follow-Up Check-In",
            "desc": "Self-assessment & progress check",
            "action": "followup_checkin",
        })
        options.append({
            "id": "advance_decide",
            "label": "🎯 Finalize Decision (Stage 3)",
            "desc": "Declare commitment & Promise to Self",
            "action": "advance_decide",
        })
    elif "DECIDE" in stage:
        options.append({
            "id": "view_commitment",
            "label": "🎯 Chosen Career & Promise",
            "desc": "Inspect single goal & vision statement",
            "action": "view_commitment",
        })
        options.append({
            "id": "followup_checkin",
            "label": "📋 Follow-Up Check-In",
            "desc": "Quarterly accountability review",
            "action": "followup_checkin",
        })
        options.append({
            "id": "advance_develop",
            "label": "🚀 Advance to DEVELOP (Stage 4)",
            "desc": "Unlock mentorship & prep roadmap",
            "action": "advance_develop",
        })
    elif "DEVELOP" in stage:
        options.append({
            "id": "mentorship",
            "label": "🤝 Mentorship & Milestones",
            "desc": "Domain DB coordinator & mentor match",
            "action": "mentorship",
        })
        options.append({
            "id": "followup_checkin",
            "label": "📋 Follow-Up Check-In",
            "desc": "Quarterly progress check",
            "action": "followup_checkin",
        })
    elif "DELIVER" in stage:
        options.append({
            "id": "certificates",
            "label": "🏆 Accomplishments & Flywheel",
            "desc": "Exam success & junior mentoring",
            "action": "certificates",
        })
        options.append({
            "id": "followup_checkin",
            "label": "📋 Follow-Up Check-In",
            "desc": "Alumni giving back log",
            "action": "followup_checkin",
        })

    # Universal Options
    options.append({
        "id": "student_profile",
        "label": "👤 Student Profile",
        "desc": "Academic & guardian info",
        "action": "student_profile",
    })
    options.append({
        "id": "coordinator_help",
        "label": "🆘 Teacher-Mentor Help",
        "desc": "Raise ticket with institution anchor",
        "action": "coordinator_help",
    })
    options.append({
        "id": "open_webapp",
        "label": "📱 Open Dream Big WebApp",
        "desc": "Interactive PWA Dashboard",
        "action": "open_webapp",
        "url": f"{get_url()}/my-dream-big?id={stu_id}&key={token}",
    })
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
