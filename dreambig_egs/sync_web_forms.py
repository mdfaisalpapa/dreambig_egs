import frappe
import json
import os

def sync():
    base_dir = frappe.get_app_path("dreambig_egs")
    
    # 1. Sync egs-decide-stage
    decide_js_path = os.path.join(base_dir, "dreambig_egs", "web_form", "egs_decide_stage", "egs_decide_stage.js")
    decide_json_path = os.path.join(base_dir, "dreambig_egs", "web_form", "egs_decide_stage", "egs_decide_stage.json")
    
    with open(decide_js_path, "r") as f:
        decide_js = f.read()
        
    with open(decide_json_path, "r") as f:
        decide_data = json.load(f)
        
    decide_data["client_script"] = decide_js
    decide_data["login_required"] = 0
    decide_data["apply_document_permissions"] = 0
    
    with open(decide_json_path, "w") as f:
        json.dump(decide_data, f, indent=1)
        
    # Update tabWeb Form in DB directly
    if frappe.db.exists("Web Form", "egs-decide-stage"):
        doc = frappe.get_doc("Web Form", "egs-decide-stage")
        doc.client_script = decide_js
        doc.login_required = 0
        doc.apply_document_permissions = 0
        doc.set("web_form_fields", [])
        for f in decide_data.get("web_form_fields", []):
            doc.append("web_form_fields", f)
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        print("✓ Updated egs-decide-stage and fields in DB and JSON")

    # 2. Sync egs-check-in-log
    checkin_js_path = os.path.join(base_dir, "dreambig_egs", "web_form", "egs_check_in_log", "egs_check_in_log.js")
    checkin_json_path = os.path.join(base_dir, "dreambig_egs", "web_form", "egs_check_in_log", "egs_check_in_log.json")

    with open(checkin_js_path, "r") as f:
        checkin_js = f.read()

    with open(checkin_json_path, "r") as f:
        checkin_data = json.load(f)

    checkin_data["client_script"] = checkin_js
    checkin_data["login_required"] = 0
    checkin_data["apply_document_permissions"] = 0

    with open(checkin_json_path, "w") as f:
        json.dump(checkin_data, f, indent=1)

    # Update tabWeb Form in DB directly
    if frappe.db.exists("Web Form", "egs-check-in-log"):
        frappe.db.set_value("Web Form", "egs-check-in-log", {
            "client_script": checkin_js,
            "login_required": 0,
            "apply_document_permissions": 0
        })
        frappe.db.commit()
        print("✓ Updated egs-check-in-log in DB and JSON")

    print("\nAll Web Forms synced successfully!")
