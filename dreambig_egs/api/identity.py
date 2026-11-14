# Copyright (c) 2026, Dream Big and contributors
# For license information, please see license.txt

import re
import frappe
from frappe import _
from dreambig_egs.api.utils import portal_api


@frappe.whitelist(allow_guest=True)
@portal_api
def resolve_chat_user(channel: str, channel_user_id: str, phone_number: str = None) -> dict:
    """
    Called by universal_chatbot to identify and authenticate incoming messages for Dream Big EGS.
    If phone_number is provided (e.g. via 1-click Contact Sharing), automatically links
    and verifies the student participant.

    :param channel: 'Telegram' or 'WhatsApp'
    :param channel_user_id: Telegram chat_id or WhatsApp phone number
    :param phone_number: Verified phone number shared by user
    :return: Clean JSON payload with student profile context or unauthenticated status
    """
    if not channel or not channel_user_id:
        return {
            "authenticated": False,
            "reason": "Missing channel or channel_user_id",
        }

    channel_norm = channel.strip().capitalize()
    user_id_norm = str(channel_user_id).strip()

    # 1. 1-Click Auto-linking via Shared Phone Number
    if phone_number:
        clean_phone = "".join(c for c in str(phone_number) if c.isdigit())
        if len(clean_phone) > 10:
            clean_phone = clean_phone[-10:]

        if clean_phone:
            matched_student = frappe.db.sql(
                """
                SELECT name, student_name, student_email, phone_number, current_5ds_stage, event_status
                FROM `tabEGS Student Participant`
                WHERE RIGHT(REPLACE(REPLACE(phone_number, ' ', ''), '-', ''), 10) = %s
                ORDER BY creation DESC LIMIT 1
                """,
                (clean_phone,),
                as_dict=True,
            )

            if matched_student:
                student = matched_student[0]
                # Save telegram_chat_id or whatsapp ID directly if Telegram
                if channel_norm == "Telegram":
                    frappe.db.set_value("EGS Student Participant", student["name"], "telegram_chat_id", user_id_norm)
                    frappe.db.commit()

                # Also store or update Channel Identity if table exists
                if frappe.db.table_exists("Channel Identity"):
                    existing_ci = frappe.db.get_value(
                        "Channel Identity",
                        {"channel": channel_norm, "channel_user_id": user_id_norm},
                        "name",
                    )
                    if existing_ci:
                        frappe.db.set_value("Channel Identity", existing_ci, "resident_email", student["student_email"])
                    else:
                        ci_doc = frappe.get_doc({
                            "doctype": "Channel Identity",
                            "channel": channel_norm,
                            "channel_user_id": user_id_norm,
                            "resident_email": student["student_email"],
                            "verified": 1,
                        })
                        ci_doc.insert(ignore_permissions=True)
                    frappe.db.commit()

    # 2. Lookup existing binding by telegram_chat_id or phone match (for WhatsApp)
    student_doc = None
    if channel_norm == "Telegram":
        students = frappe.get_all(
            "EGS Student Participant",
            filters={"telegram_chat_id": user_id_norm},
            fields=["name", "student_name", "student_email", "phone_number", "current_5ds_stage", "event_status", "access_token", "city", "course", "university_college", "final_chosen_career_goal"],
            limit=1,
        )
        if students:
            student_doc = students[0]
    elif channel_norm == "WhatsApp":
        clean_wa = re.sub(r"\D", "", user_id_norm)
        phone_10 = clean_wa[-10:] if len(clean_wa) >= 10 else clean_wa
        if len(phone_10) >= 10:
            students = frappe.get_all(
                "EGS Student Participant",
                filters={"phone_number": ["like", f"%{phone_10}"]},
                fields=["name", "student_name", "student_email", "phone_number", "current_5ds_stage", "event_status", "access_token", "city", "course", "university_college", "final_chosen_career_goal"],
                limit=1,
            )
            if students:
                student_doc = students[0]

    # 3. Check Channel Identity table as fallback
    if not student_doc and frappe.db.table_exists("Channel Identity"):
        ci = frappe.db.get_value(
            "Channel Identity",
            {"channel": channel_norm, "channel_user_id": user_id_norm, "verified": 1},
            ["resident_email"],
            as_dict=True,
        )
        if ci and ci.get("resident_email"):
            students = frappe.get_all(
                "EGS Student Participant",
                filters={"student_email": ci["resident_email"]},
                fields=["name", "student_name", "student_email", "phone_number", "current_5ds_stage", "event_status", "access_token", "city", "course", "university_college", "final_chosen_career_goal"],
                limit=1,
            )
            if students:
                student_doc = students[0]

    if not student_doc:
        return {
            "authenticated": False,
            "channel": channel_norm,
            "channel_user_id": user_id_norm,
            "reason": "Student record not linked to this chat account",
        }

    return {
        "authenticated": True,
        "channel": channel_norm,
        "channel_user_id": user_id_norm,
        "student_id": student_doc["name"],
        "student_name": student_doc["student_name"],
        "student_email": student_doc["student_email"],
        "phone_number": student_doc["phone_number"],
        "current_5ds_stage": (student_doc.get("current_5ds_stage") or "DREAM").upper(),
        "event_status": student_doc.get("event_status") or "Registered",
        "city": student_doc.get("city") or "",
        "course": student_doc.get("course") or "",
        "institution": student_doc.get("university_college") or "",
        "chosen_career_goal": student_doc.get("final_chosen_career_goal") or "",
    }


@frappe.whitelist(allow_guest=True)
@portal_api
def logout_chat_user(channel: str, channel_user_id: str) -> dict:
    """
    Unlinks the chat channel account from any student participant record.
    """
    if not channel or not channel_user_id:
        return {"logged_out": False, "reason": "Missing channel or channel_user_id"}

    channel_norm = channel.strip().capitalize()
    user_id_norm = str(channel_user_id).strip()

    if channel_norm == "Telegram":
        frappe.db.sql(
            """
            UPDATE `tabEGS Student Participant`
            SET telegram_chat_id = NULL
            WHERE telegram_chat_id = %s
            """,
            (user_id_norm,),
        )
        frappe.db.commit()

    if frappe.db.table_exists("Channel Identity"):
        frappe.db.sql(
            """
            DELETE FROM `tabChannel Identity`
            WHERE channel = %s AND channel_user_id = %s
            """,
            (channel_norm, user_id_norm),
        )
        frappe.db.commit()

    # Also reset EGS Bot Session if present
    if frappe.db.table_exists("EGS Bot Session"):
        frappe.db.sql(
            """
            UPDATE `tabEGS Bot Session`
            SET student_participant = NULL, current_conversation_state = 'LOGGED_OUT'
            WHERE chat_id = %s
            """,
            (user_id_norm,),
        )
        frappe.db.commit()

    return {"logged_out": True, "message": "Successfully unlinked student identity"}
