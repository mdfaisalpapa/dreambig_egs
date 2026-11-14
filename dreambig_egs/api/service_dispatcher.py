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
                "event",
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
                f"You have confirmed your presence at the physical event.{coupon_info}\n\n"
                f"Please proceed with *Stage 1: DREAM* by shortlisting your 5 career goals."
            )
            return {
                "title": "Event Check-In",
                "prompt": prompt,
                "options": [
                    {"label": "💭 Select 5 Dream Goals", "value": "select_5_goals"},
                    {"label": "🔙 Back to Main Menu", "value": "menu"},
                ],
            }

        # Check event date validation
        event_doc = None
        if student.get("event"):
            event_doc = frappe.db.get_value("EGS Event", student.get("event"), ["name", "event_name", "event_date", "allow_digital_checkins", "allow_digital_food_coupons"], as_dict=True)

        today_str = str(frappe.utils.today())
        if event_doc and event_doc.get("event_date"):
            evt_date_str = str(event_doc.get("event_date"))[:10]
            if today_str != evt_date_str:
                return {
                    "title": "Event Check-In",
                    "prompt": (
                        f"📅 *Event Check-In Not Yet Open*\n\n"
                        f"Event: **{event_doc.get('event_name') or event_doc.get('name')}**\n"
                        f"Date: **{evt_date_str}**\n\n"
                        f"Check-in is permitted **only on the day of the event** after scanning the QR code pasted at the venue.\n"
                        f"Today's date is `{today_str}`."
                    ),
                    "options": [{"label": "🔙 Back to Main Menu", "value": "menu"}],
                }

        try:
            frappe.db.set_value("EGS Student Participant", student["name"], "event_status", "Checked-In")
            frappe.db.set_value("EGS Student Participant", student["name"], "physical_attendance", 1)
            # Student enters Stage 1: DREAM
            frappe.db.set_value("EGS Student Participant", student["name"], "current_5ds_stage", "DREAM")

            coupon = student.get("food_coupon_code")
            if not coupon:
                coupon = f"MEAL-{frappe.generate_hash(length=6).upper()}"
                frappe.db.set_value("EGS Student Participant", student["name"], "food_coupon_code", coupon)
                frappe.db.set_value("EGS Student Participant", student["name"], "food_coupon_issued", 1)
            frappe.db.commit()

            prompt = (
                f"🎉 *Event Check-In Successful!*\n\n"
                f"Welcome to Dream Big EGS, **{student.get('student_name')}**!\n"
                f"🎟️ *Your Digital Food Coupon:* `{coupon}`\n\n"
                f"Your attendance is verified. You are now in **Stage 1: DREAM**.\n"
                f"Next step: On-the-spot career selection exercise — shortlist **5 goals** from the 40+ career pathways."
            )
        except Exception as e:
            prompt = f"⚠️ Check-in encountered an issue: {e}"

        return {
            "title": "Event Check-In",
            "prompt": prompt,
            "options": [
                {"label": "💭 Select 5 Dream Goals", "value": "select_5_goals"},
                {"label": "📱 Open Dashboard WebApp", "value": "open_webapp", "url": webapp_url},
                {"label": "🔙 Back to Main Menu", "value": "menu"},
            ],
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

    # --- 4. Stage 1: DREAM - Select 5 Career Goals ---
    elif action_id.startswith("select_5_goals") or action_id.startswith("toggle_goal_") or action_id == "save_5_goals" or action_id.startswith("grp_"):
        if not student:
            return {"title": "Select 5 Goals", "prompt": "⚠️ Student record required.", "options": [{"label": "🔙 Back", "value": "menu"}]}

        from dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant import get_all_career_pathways

        # Current shortlisted goals
        current_choices = frappe.get_all(
            "EGS Student Career Choice",
            filters={"parent": student["name"], "parenttype": "EGS Student Participant"},
            fields=["career_pathway"],
            order_by="idx asc",
        )
        selected_goals = [c["career_pathway"] for c in current_choices]

        # Handle toggle action if triggered
        if action_id.startswith("toggle_goal_"):
            goal_key = action_id[len("toggle_goal_"):].strip()
            # Match goal_key to actual pathway name
            matching = frappe.get_all("EGS Career Pathway", filters={"name": ["like", f"%{goal_key}%"]}, limit=1)
            target_goal = matching[0].name if matching else goal_key

            if target_goal in selected_goals:
                selected_goals.remove(target_goal)
            else:
                if len(selected_goals) >= 5:
                    return {
                        "title": "Stage 1: DREAM",
                        "prompt": (
                            f"⚠️ *Goal Limit Reached (5/5)*\n\n"
                            f"You have already shortlisted 5 career goals:\n"
                            + "\n".join([f"  {idx+1}. {g}" for idx, g in enumerate(selected_goals)])
                            + "\n\nTap *Save 5 Goals* or remove a goal before adding another."
                        ),
                        "options": [
                            {"label": "💾 Save 5 Goals & Complete DREAM", "value": "save_5_goals"},
                            {"label": "📋 View/Edit Goals", "value": "select_5_goals"},
                            {"label": "🔙 Back to Main Menu", "value": "menu"},
                        ],
                    }
                selected_goals.append(target_goal)

            # Update in DB
            frappe.db.delete("EGS Student Career Choice", {"parent": student["name"], "parenttype": "EGS Student Participant"})
            for idx, g in enumerate(selected_goals):
                frappe.get_doc({
                    "doctype": "EGS Student Career Choice",
                    "parent": student["name"],
                    "parenttype": "EGS Student Participant",
                    "parentfield": "top_5_career_goals",
                    "career_pathway": g,
                    "idx": idx + 1,
                }).insert(ignore_permissions=True)
            frappe.db.commit()

        # Handle Save 5 Goals finalization
        if action_id == "save_5_goals":
            if len(selected_goals) < 5:
                return {
                    "title": "Stage 1: DREAM",
                    "prompt": (
                        f"⚠️ *Incomplete Shortlist ({len(selected_goals)}/5)*\n\n"
                        f"Please select exactly 5 goals from the pathways list before saving.\n"
                        f"Current selections:\n"
                        + "\n".join([f"  {idx+1}. {g}" for idx, g in enumerate(selected_goals)])
                    ),
                    "options": [
                        {"label": "💭 Continue Selecting Goals", "value": "select_5_goals"},
                        {"label": "📱 Select in WebApp (Easy)", "value": "open_webapp", "url": webapp_url},
                        {"label": "🔙 Back to Main Menu", "value": "menu"},
                    ],
                }

            # Advance to Stage 2: DISCOVER
            frappe.db.set_value("EGS Student Participant", student["name"], "current_5ds_stage", "DISCOVER")
            frappe.db.commit()

            return {
                "title": "Stage 1 Complete: DREAM",
                "prompt": (
                    f"🎉 *Stage 1: DREAM Complete!*\n\n"
                    f"Congratulations, **{student.get('student_name')}**! Your 5 DREAM BIG Career Goals have been locked:\n"
                    + "\n".join([f"  {idx+1}. {g}" for idx, g in enumerate(selected_goals)])
                    + "\n\n🌟 *You have advanced to Stage 2: DISCOVER!*\n"
                    f"Over the next few months, you will research these paths, connect with DB Domain Coordinators, and narrow down to 1–2 final goals."
                ),
                "options": [
                    {"label": "📋 View Shortlist (Stage 2)", "value": "view_shortlist"},
                    {"label": "📱 Open Dashboard WebApp", "value": "open_webapp", "url": webapp_url},
                    {"label": "🔙 Back to Main Menu", "value": "menu"},
                ],
            }

        # Show Category / Group Browse or Selected Summary
        all_paths = get_all_career_pathways()
        shortlist_display = "\n".join([f"  ✅ {idx+1}. {g}" for idx, g in enumerate(selected_goals)]) if selected_goals else "  _(No goals shortlisted yet)_"

        prompt = (
            f"💭 *Stage 1: DREAM — On-the-spot Goal Selection*\n\n"
            f"Shortlist exactly **5 Career Goals** representing your highest aspirations.\n\n"
            f"*Current Shortlist ({len(selected_goals)}/5):*\n{shortlist_display}\n\n"
            f"You can choose career goals below or tap *Open WebApp* for the 1-click checklist:"
        )

        options = []
        if len(selected_goals) == 5:
            options.append({"label": "💾 Save & Advance to DISCOVER", "value": "save_5_goals"})

        options.append({"label": "📱 Open WebApp Checklist (Fast)", "value": "open_webapp", "url": webapp_url})

        # Offer quick popular career pathway options
        sample_pathways = [
            "Honest & effective-IAS/IPS/IFS/Central Civil Services",
            "Judges in Supreme Court & High Court/Attorney General of India",
            "AI, Data Science, Quantum Tech, Biotech, Bioengineering, Robotics",
            "Global CEOs/CTOs/COOs of Top Companies of the World",
            "Nobel Laureates",
            "Unicorn Companies",
            "Professors in Top Ranking Global Universities",
            "Top firms of India - Law / Chartered Accountancy",
        ]
        for p in sample_pathways:
            is_sel = p in selected_goals
            prefix = "❌ Remove: " if is_sel else "➕ Add: "
            short_lbl = p[:25] + "..." if len(p) > 28 else p
            short_key = p[:15].strip()
            options.append({
                "label": f"{prefix}{short_lbl}",
                "value": f"toggle_goal_{short_key}",
            })

        options.append({"label": "🔙 Back to Main Menu", "value": "menu"})

        return {
            "title": "Stage 1: DREAM",
            "prompt": prompt,
            "sso_url": webapp_url,
            "options": options[:10],
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
