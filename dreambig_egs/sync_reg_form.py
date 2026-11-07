import json
import os
import frappe

def sync_student_reg_form():
    base_dir = frappe.get_app_path("dreambig_egs")
    wf_json_path = os.path.join(base_dir, "dreambig_egs", "web_form", "egs_student_participant", "egs_student_participant.json")
    wf_js_path = os.path.join(base_dir, "dreambig_egs", "web_form", "egs_student_participant", "egs_student_participant.js")
    
    with open(wf_js_path, "r") as f:
        js_content = f.read()

    with open(wf_json_path, "r") as f:
        wf_data = json.load(f)

    # Filter out career_goals_section, career_checklist_html, top_5_career_goals, email_otp, year_of_study
    fields_to_remove = {"career_goals_section", "career_checklist_html", "top_5_career_goals", "email_otp", "year_of_study"}
    existing_fields = [fld for fld in wf_data.get("web_form_fields", []) if fld.get("fieldname") not in fields_to_remove]

    # Ensure first_year_notice is present at the beginning
    has_notice = any(f.get("fieldname") == "first_year_notice" for f in existing_fields)
    notice_fld_def = {
        "allow_read_on_all_link_options": 0,
        "default": "",
        "depends_on": "",
        "description": "",
        "fieldname": "first_year_notice",
        "fieldtype": "HTML",
        "hidden": 0,
        "label": "First Year Notice",
        "mandatory_depends_on": "",
        "max_length": 0,
        "max_value": 0,
        "options": "<div class=\"alert alert-info\" style=\"margin-top:10px;\"><strong>Notice:</strong> The EGS:DB program is exclusively for First-Year Undergraduate students.</div>",
        "placeholder": "",
        "precision": "",
        "read_only": 0,
        "read_only_depends_on": "",
        "reqd": 0,
        "show_in_filter": 0
    }

    # Ensure cohort_year is present after course
    has_cohort_year = any(f.get("fieldname") == "cohort_year" for f in existing_fields)
    cohort_year_fld_def = {
        "allow_read_on_all_link_options": 0,
        "default": "2026",
        "depends_on": "",
        "description": "",
        "fieldname": "cohort_year",
        "fieldtype": "Data",
        "hidden": 0,
        "label": "Cohort / Admission Year",
        "mandatory_depends_on": "",
        "max_length": 0,
        "max_value": 0,
        "options": "",
        "placeholder": "2026",
        "precision": "",
        "read_only": 0,
        "read_only_depends_on": "",
        "reqd": 1,
        "show_in_filter": 0
    }
    
    # Check if event field is present, if not add it
    has_event = any(f.get("fieldname") == "event" for f in existing_fields)
    event_fld_def = {
        "allow_read_on_all_link_options": 1,
        "default": "",
        "depends_on": "",
        "description": "Select the DREAM BIG Event open for registration in your city.",
        "fieldname": "event",
        "fieldtype": "Link",
        "hidden": 0,
        "label": "Event",
        "mandatory_depends_on": "",
        "max_length": 0,
        "max_value": 0,
        "options": "EGS Event",
        "placeholder": "Select Event",
        "precision": "",
        "read_only": 0,
        "read_only_depends_on": "",
        "reqd": 0,
        "show_in_filter": 0
    }

    new_fields = []
    if not has_notice:
        new_fields.append(notice_fld_def)

    for fld in existing_fields:
        if fld.get("fieldname") == "first_year_notice":
            # Already at top or will be placed
            new_fields.append(fld)
            continue
        new_fields.append(fld)
        if fld.get("fieldname") == "university_college" and not has_event:
            new_fields.append(event_fld_def)
        if fld.get("fieldname") == "course" and not has_cohort_year:
            new_fields.append(cohort_year_fld_def)

    for fld in new_fields:
        if fld.get("fieldtype") == "Link":
            fld["allow_read_on_all_link_options"] = 1

    wf_data["web_form_fields"] = new_fields
    wf_data["client_script"] = js_content

    with open(wf_json_path, "w") as f:
        json.dump(wf_data, f, indent=1)

    print(f"✓ Updated egs_student_participant.json with {len(new_fields)} fields.")

    # Update Database tabWeb Form record
    if frappe.db.exists("Web Form", "egs-student-participant"):
        doc = frappe.get_doc("Web Form", "egs-student-participant")
        doc.client_script = js_content
        doc.set("web_form_fields", [])
        for fld in new_fields:
            doc.append("web_form_fields", fld)
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        print("✓ Updated tabWeb Form egs-student-participant in database.")

if __name__ == "__main__":
    sync_student_reg_form()
