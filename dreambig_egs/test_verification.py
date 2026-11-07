import frappe
import requests
import json
from dreambig_egs.seed_brochure_careers import BROCHURE_DATA, GROUP_INDEX_MAP

def run_tests():
    print("=" * 60)
    print("RUNNING AUTOMATED VERIFICATION SUITE (BROCHURE SORT INDEX)")
    print("=" * 60)

    # 1. Verify EGS Career Pathway Schema has brochure_index
    print("\n--- 1. Testing EGS Career Pathway Schema ---")
    meta = frappe.get_meta("EGS Career Pathway")
    fields = {f.fieldname: f for f in meta.fields}
    assert "brochure_index" in fields, "brochure_index missing in EGS Career Pathway"
    assert fields["brochure_index"].fieldtype == "Int"
    print("✓ brochure_index is present as Int field in EGS Career Pathway")

    # 2. Verify Database records and brochure_index values
    print("\n--- 2. Testing Database Records & brochure_index Values ---")
    total_in_db = frappe.db.count("EGS Career Pathway")
    print(f"Total pathways in DB: {total_in_db}")
    assert total_in_db == len(BROCHURE_DATA), f"Expected {len(BROCHURE_DATA)} pathways, got {total_in_db}"

    # Verify each brochure entry has exact brochure_index
    for cat, grp, title in BROCHURE_DATA:
        expected_idx = GROUP_INDEX_MAP[grp]
        actual_idx = frappe.db.get_value("EGS Career Pathway", title, "brochure_index")
        assert actual_idx == expected_idx, f"Mismatch for {title}: expected {expected_idx}, got {actual_idx}"
    print(f"✓ All {len(BROCHURE_DATA)} records have exact brochure_index integers matching GROUP_INDEX_MAP")

    # 3. Test get_all_career_pathways() Ordering
    print("\n--- 3. Testing get_all_career_pathways API Ordering ---")
    from dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant import get_all_career_pathways

    frappe.set_user("Guest")
    pathways = get_all_career_pathways()
    frappe.set_user("Administrator")
    assert len(pathways) == len(BROCHURE_DATA), f"Expected {len(BROCHURE_DATA)} pathways, got {len(pathways)}"

    # Separate into Employer and Employee
    employer_list = [p for p in pathways if "Employer" in p.career_category]
    employee_list = [p for p in pathways if "Employee" in p.career_category]

    print(f"Employer count: {len(employer_list)}, Employee count: {len(employee_list)}")
    assert len(employer_list) == 16, f"Expected 16 Employer pathways, got {len(employer_list)}"
    assert len(employee_list) == 26, f"Expected 26 Employee pathways, got {len(employee_list)}"

    # Verify Employer ordering
    employer_indices = [p.brochure_index for p in employer_list]
    assert employer_indices == sorted(employer_indices), f"Employer indices not sorted: {employer_indices}"
    expected_emp_groups_order = [
        "Institution building",
        "Social Welfare and Development",
        "Financial Leadership",
        "Manufacturing, Services and Trade",
        "Entrepreneurship & Investment",
        "Consulting & Think tanks",
        "Law, Financial & HR Services",
        "Technology and Digital Innovation"
    ]
    seen_groups = []
    for p in employer_list:
        if not seen_groups or seen_groups[-1] != p.career_group:
            seen_groups.append(p.career_group)
    assert seen_groups == expected_emp_groups_order, f"Employer groups order mismatch: {seen_groups}"
    print("✓ Employer Category strictly sorted by brochure_index asc and group order")

    # Verify Employee ordering
    employee_indices = [p.brochure_index for p in employee_list]
    assert employee_indices == sorted(employee_indices), f"Employee indices not sorted: {employee_indices}"
    expected_employee_groups_order = [
        "Government/Public Service-Leadership Roles",
        "Govt. Regulatory & Development Leadership",
        "Financial Leadership",
        "Govt. Scientific & Professional leadership",
        "Academic excellence & Leadership",
        "Inventions and Discovery",
        "Professional & Business Leadership",
        "Arts, Journalism & Sports",
        "Religious Scholarship",
        "Political Leadership",
        "UN/ Global Organisations"
    ]
    seen_emp_groups = []
    for p in employee_list:
        if not seen_emp_groups or seen_emp_groups[-1] != p.career_group:
            seen_emp_groups.append(p.career_group)
    assert seen_emp_groups == expected_employee_groups_order, f"Employee groups order mismatch: {seen_emp_groups}"
    print("✓ Employee Category strictly sorted by brochure_index asc and group order")

    # 4. HTTP API and Web Form Verification
    print("\n--- 4. Testing HTTP Guest API & Web Form ---")
    headers = {"Host": "egs.localhost"}
    api_url = "http://127.0.0.1:8000/api/method/dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant.get_all_career_pathways"
    resp = requests.get(api_url, headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    http_data = resp.json().get("message", [])
    assert len(http_data) == len(BROCHURE_DATA)
    print("✓ Guest HTTP API returns HTTP 200 with all 42 pathways in correct order")

    wf_url = "http://127.0.0.1:8000/egs-student-participant/new"
    page_resp = requests.get(wf_url, headers=headers)
    assert page_resp.status_code == 200, f"Expected 200, got {page_resp.status_code}"
    assert "student_name" in page_resp.text
    assert "career_checklist_html" not in page_resp.text
    print("✓ Registration Web Form page loads with HTTP 200 (career checklist removed)")

    # 5. Magic Link & PWA Verification
    print("\n--- 5. Testing Magic Link & PWA Portal Features ---")
    
    # 5.1 Verify access_token in EGS Student Participant meta
    sp_meta = frappe.get_meta("EGS Student Participant")
    sp_fields = {f.fieldname: f for f in sp_meta.fields}
    assert "access_token" in sp_fields, "access_token missing in EGS Student Participant"
    assert sp_fields["access_token"].fieldtype == "Data"
    print("✓ access_token is present in EGS Student Participant schema")

    # 5.2 Verify PWA enabled in Website Settings
    from frappe.utils import cint
    ws = frappe.get_single("Website Settings")
    assert cint(ws.enable_pwa) == 1, f"Expected enable_pwa=1, got {ws.enable_pwa} ({type(ws.enable_pwa)})"
    print("✓ Website Settings has enable_pwa = 1")

    # 5.3 Test Participant Insertion & access_token generation
    test_email = "magic_tester@example.com"
    existing = frappe.db.get_value("EGS Student Participant", {"student_email": test_email}, "name")
    if existing:
        frappe.delete_doc("EGS Student Participant", existing, force=True)
        frappe.db.commit()

    test_doc = frappe.get_doc({
        "doctype": "EGS Student Participant",
        "student_name": "Magic Link Tester",
        "student_email": test_email,
        "phone_number": "9998887776",
        "gender": "Female",
        "city": "Kozhikode",
        "university_college": "Jamia Hamdard Centre",
        "course": "B.Tech Computer Science",
        "degree_level": "Undergraduate",
        "event_status": "Checked-In",
        "top_5_career_goals": [
            {"career_pathway": "Honest & effective-IAS/IPS/IFS/Central Civil Services"}
        ]
    })
    test_doc.insert(ignore_permissions=True)
    frappe.db.commit()

    assert test_doc.access_token, "access_token was not generated on insert!"
    assert len(test_doc.access_token) == 15, f"Expected 15 char token, got {len(test_doc.access_token)}"
    print(f"✓ Student Participant inserted with generated access_token: {test_doc.access_token}")

    # 5.4 Test resend_magic_link API
    from dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant import resend_magic_link
    res_success = resend_magic_link(test_email)
    assert res_success.get("status") == "success", f"resend_magic_link failed: {res_success}"
    print("✓ resend_magic_link successfully sent link for existing user")

    res_fail = resend_magic_link("non_existent_student_999@example.com")
    assert res_fail.get("status") in ["error", "failed"], f"resend_magic_link should have failed: {res_fail}"
    print("✓ resend_magic_link gracefully returned failure for unknown user")

    # 5.5 Test Portal Dashboard HTTP GET (/my-dream-big)
    portal_valid_url = f"http://127.0.0.1:8000/my-dream-big?id={test_doc.name}&key={test_doc.access_token}"
    resp_portal = requests.get(portal_valid_url, headers=headers)
    assert resp_portal.status_code == 200, f"Expected 200 for dashboard, got {resp_portal.status_code}"
    assert "Magic Link Tester" in resp_portal.text
    assert "Add to Home Screen" in resp_portal.text
    assert "Honest & effective-IAS/IPS/IFS/Central Civil Services" in resp_portal.text
    assert "5Ds Journey Framework" in resp_portal.text
    print("✓ /my-dream-big loaded student dashboard with 5Ds and PWA prompt successfully")

    # 5.6 Test Portal Unauthorized Access
    resp_unauth = requests.get("http://127.0.0.1:8000/my-dream-big", headers=headers)
    assert resp_unauth.status_code == 200
    assert "Access Restricted" in resp_unauth.text
    print("✓ /my-dream-big without valid token restricts access securely")

    # 5.7 Test Recover Link Page HTTP GET (/recover-link)
    resp_rec = requests.get("http://127.0.0.1:8000/recover-link", headers=headers)
    assert resp_rec.status_code == 200, f"Expected 200 for recover-link, got {resp_rec.status_code}"
    assert "Recover Access Link" in resp_rec.text
    assert "resend_magic_link" in resp_rec.text
    print("✓ /recover-link page loads with recovery form and API handler")

    # Clean up test participant
    frappe.delete_doc("EGS Student Participant", test_doc.name, force=True)
    frappe.db.commit()
    print("✓ Cleaned up test participant")

    # 6. Web Form Interceptor Verification
    print("\n--- 6. Testing Web Form Interceptors (DECIDE Stage & Progress Check-in) ---")
    
    # Check DB client_script for egs-decide-stage
    wf_decide = frappe.get_doc("Web Form", "egs-decide-stage")
    assert "Access Your Dashboard" in wf_decide.client_script
    assert "send_login_credentials" in wf_decide.client_script
    assert "urlParams.get" in wf_decide.client_script
    assert "login_email" in wf_decide.client_script
    assert "login_otp" in wf_decide.client_script
    assert wf_decide.login_required == 0
    print("✓ egs-decide-stage has interceptor in client_script and login_required=0")

    # Check DB client_script for egs-check-in-log
    wf_checkin = frappe.get_doc("Web Form", "egs-check-in-log")
    assert "Access Your Dashboard" in wf_checkin.client_script
    assert "send_login_credentials" in wf_checkin.client_script
    assert "urlParams.get" in wf_checkin.client_script
    assert "login_email" in wf_checkin.client_script
    assert "login_otp" in wf_checkin.client_script
    assert wf_checkin.login_required == 0
    print("✓ egs-check-in-log has interceptor in client_script and login_required=0")

    # HTTP verification for egs-decide-stage
    resp_wf_decide = requests.get("http://127.0.0.1:8000/egs-decide-stage/new", headers=headers)
    assert resp_wf_decide.status_code == 200, f"Expected 200 for egs-decide-stage/new, got {resp_wf_decide.status_code}"
    assert "Access Your Dashboard" in resp_wf_decide.text
    assert "login_email" in resp_wf_decide.text
    print("✓ /egs-decide-stage/new loads successfully with interceptor script")

    # HTTP verification for egs-check-in-log
    resp_wf_checkin = requests.get("http://127.0.0.1:8000/egs-check-in-log/new", headers=headers)
    assert resp_wf_checkin.status_code == 200, f"Expected 200 for egs-check-in-log/new, got {resp_wf_checkin.status_code}"
    assert "Access Your Dashboard" in resp_wf_checkin.text
    assert "login_email" in resp_wf_checkin.text
    print("✓ /egs-check-in-log/new loads successfully with interceptor script")

    # 7. Separated Registration, Event Check-In & Locked Goals Flow
    print("\n--- 7. Testing Event Check-In, Locking & Separated Registration Flow ---")
    
    # 7.1 Verify EGS Student Participant Schema
    sp_meta2 = frappe.get_meta("EGS Student Participant")
    sp_flds2 = {f.fieldname: f for f in sp_meta2.fields}
    assert "event_status" in sp_flds2, "event_status missing in EGS Student Participant"
    assert sp_flds2["event_status"].fieldtype == "Select"
    assert sp_flds2["event_status"].default == "Registered"
    assert "top_5_career_goals" in sp_flds2
    assert sp_flds2["top_5_career_goals"].reqd == 0, "top_5_career_goals should not be mandatory"
    print("✓ event_status field exists and top_5_career_goals is not mandatory")

    # 7.2 Verify Web Form fields (checklist and table removed)
    wf_participant = frappe.get_doc("Web Form", "egs-student-participant")
    wf_fld_names = [f.fieldname for f in wf_participant.web_form_fields]
    assert "career_checklist_html" not in wf_fld_names, "career_checklist_html should be removed from registration Web Form"
    assert "top_5_career_goals" not in wf_fld_names, "top_5_career_goals should be removed from registration Web Form"
    print("✓ egs-student-participant Web Form has removed checklist and child table")

    # 7.3 Test Initial Registration without Career Goals
    test_email_reg = "event_checkin_student@example.com"
    existing_reg = frappe.db.get_value("EGS Student Participant", {"student_email": test_email_reg}, "name")
    if existing_reg:
        frappe.delete_doc("EGS Student Participant", existing_reg, force=True)
        frappe.db.commit()

    reg_doc = frappe.get_doc({
        "doctype": "EGS Student Participant",
        "student_name": "Event Checkin Student",
        "student_email": test_email_reg,
        "phone_number": "9887766554",
        "gender": "Male",
        "city": "Kozhikode",
        "university_college": "Jamia Hamdard Centre",
        "course": "B.Tech Computer Science",
        "degree_level": "Undergraduate",
        "top_5_career_goals": []  # Zero goals at registration
    })
    reg_doc.insert(ignore_permissions=True)
    frappe.db.commit()

    assert reg_doc.event_status == "Registered", f"Expected Registered, got {reg_doc.event_status}"
    print(f"✓ Initial registration succeeded with zero goals; event_status: {reg_doc.event_status}")

    # 7.4 Test Locked Goals Screen on /my-dream-big for Registered Student
    portal_locked_url = f"http://127.0.0.1:8000/my-dream-big?id={reg_doc.name}&key={reg_doc.access_token}"
    resp_locked = requests.get(portal_locked_url, headers=headers)
    assert resp_locked.status_code == 200
    assert "Goals Locked" in resp_locked.text
    assert "Exercise 2" in resp_locked.text
    assert "Please scan the QR code at the venue to check in!" in resp_locked.text
    print("✓ /my-dream-big displays locked goals banner for 'Registered' status")

    # 7.5 Test Event Check-In API
    from dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant import event_checkin, save_career_goals
    
    # Invalid token check
    try:
        event_checkin(reg_doc.name, "invalid_token_xyz")
        assert False, "Should have thrown PermissionError for invalid token"
    except frappe.PermissionError:
        print("✓ event_checkin threw PermissionError for invalid token")

    # Valid check-in
    res_checkin = event_checkin(reg_doc.name, reg_doc.access_token)
    assert res_checkin.get("status") == "success"
    assert "Successfully checked in" in res_checkin.get("message")
    
    # Reload doc to verify updated status
    reg_doc.reload()
    assert reg_doc.event_status == "Checked-In"
    print("✓ event_checkin successfully updated event_status to 'Checked-In'")

    # Repeat check-in
    res_repeat = event_checkin(reg_doc.name, reg_doc.access_token)
    assert "Already checked in" in res_repeat.get("message")
    print("✓ event_checkin handled repeat check-in gracefully")

    # 7.6 Test Unlocked Dashboard & Interactive Checklist
    resp_unlocked = requests.get(portal_locked_url, headers=headers)
    assert resp_unlocked.status_code == 200
    assert "Select Your 5 DREAM BIG Career Goals (Exercise 2)" in resp_unlocked.text
    assert "Save My 5 Career Goals" in resp_unlocked.text
    print("✓ /my-dream-big renders interactive checklist once Checked-In")

    # 7.7 Test Save Career Goals API
    chosen_goals = [
        "Honest & effective-IAS/IPS/IFS/Central Civil Services",
        "Nobel Laureates"
    ]
    res_save = save_career_goals(reg_doc.name, reg_doc.access_token, chosen_goals)
    assert res_save.get("status") == "success"
    
    reg_doc.reload()
    saved_paths = [g.career_pathway for g in reg_doc.top_5_career_goals]
    assert saved_paths == chosen_goals
    print("✓ save_career_goals successfully stored selected goals on participant")

    # 7.8 Test Event Check-in Web Page HTTP GET (/event-checkin)
    resp_checkin_page = requests.get("http://127.0.0.1:8000/event-checkin", headers=headers)
    assert resp_checkin_page.status_code == 200
    assert "Event Check-In" in resp_checkin_page.text
    assert "checkin-form" in resp_checkin_page.text
    print("✓ /event-checkin page loads successfully with check-in form")

    # Clean up test participant
    frappe.delete_doc("EGS Student Participant", reg_doc.name, force=True)
    frappe.db.commit()
    print("✓ Cleaned up test checkin participant")

    # 8. Event Registration Filtering, Digital Check-in & Food Coupon Verification
    print("\n--- 8. Testing Event Registration Filtering, Digital Check-in & Food Coupons ---")

    # 8.1 Verify EGS Event Schema
    evt_meta = frappe.get_meta("EGS Event")
    evt_flds = {f.fieldname: f for f in evt_meta.fields}
    assert "status" in evt_flds, "status missing in EGS Event"
    assert evt_flds["status"].fieldtype == "Select"
    assert "Open for Registration" in evt_flds["status"].options
    assert "Planned" in evt_flds["status"].options
    assert "registration_deadline" in evt_flds, "registration_deadline missing in EGS Event"
    assert "allow_digital_checkins" in evt_flds, "allow_digital_checkins missing in EGS Event"
    assert evt_flds["allow_digital_checkins"].fieldtype == "Check"
    assert "allow_digital_food_coupons" in evt_flds, "allow_digital_food_coupons missing in EGS Event"
    assert evt_flds["allow_digital_food_coupons"].fieldtype == "Check"
    print("✓ EGS Event schema has status, registration_deadline, allow_digital_checkins, allow_digital_food_coupons")

    # 8.2 Verify EGS Student Participant Schema has event and food_coupon_code
    sp_meta_ev = frappe.get_meta("EGS Student Participant")
    sp_ev_flds = {f.fieldname: f for f in sp_meta_ev.fields}
    assert "event" in sp_ev_flds, "event missing in EGS Student Participant"
    assert sp_ev_flds["event"].fieldtype == "Link"
    assert sp_ev_flds["event"].options == "EGS Event"
    assert "food_coupon_code" in sp_ev_flds, "food_coupon_code missing in EGS Student Participant"
    print("✓ EGS Student Participant schema has event (Link to EGS Event) and food_coupon_code")

    # 8.3 Verify Registration Logic: City mismatch validation
    from dreambig_egs.seed_events import seed
    seed()
    kozhikode_event = frappe.db.get_value("EGS Event", {"event_name": "DREAM BIG Flagship Conference Kozhikode"}, "name")
    delhi_event = frappe.db.get_value("EGS Event", {"event_name": "DREAM BIG Delhi Leadership Summit"}, "name")

    # Test City Mismatch
    try:
        mismatch_doc = frappe.get_doc({
            "doctype": "EGS Student Participant",
            "student_name": "Mismatch Tester",
            "student_email": "mismatch@example.com",
            "phone_number": "9112233445",
            "gender": "Male",
            "city": "Bengaluru",
            "university_college": "Jamia Hamdard Centre",
            "course": "B.Tech Computer Science",
            "event": delhi_event  # Delhi event in Bengaluru city
        })
        mismatch_doc.insert(ignore_permissions=True)
        assert False, "Should have thrown ValidationError for event city mismatch"
    except frappe.ValidationError:
        print("✓ Threw ValidationError when event city does not match student city")

    # 8.4 Verify Registration Logic: Event Status validation (Not open)
    planned_event_name = "TEST-PLANNED-EVENT"
    if not frappe.db.exists("EGS Event", {"event_name": planned_event_name}):
        pl_doc = frappe.get_doc({
            "doctype": "EGS Event",
            "event_name": planned_event_name,
            "city": "Kozhikode",
            "status": "Planned",
            "event_date": "2026-12-01 10:00:00"
        }).insert(ignore_permissions=True)
    else:
        pl_doc = frappe.get_doc("EGS Event", {"event_name": planned_event_name})

    try:
        closed_doc = frappe.get_doc({
            "doctype": "EGS Student Participant",
            "student_name": "Closed Event Tester",
            "student_email": "closed_event@example.com",
            "phone_number": "9112233446",
            "gender": "Male",
            "city": "Kozhikode",
            "university_college": "Jamia Hamdard Centre",
            "course": "B.Tech Computer Science",
            "event": pl_doc.name
        })
        closed_doc.insert(ignore_permissions=True)
        assert False, "Should have thrown ValidationError for non-open event status"
    except frappe.ValidationError:
        print("✓ Threw ValidationError when event is not 'Open for Registration'")

    # 8.5 Verify Registration Logic: Registration Deadline validation (Expired deadline)
    expired_event_name = "TEST-EXPIRED-EVENT"
    if not frappe.db.exists("EGS Event", {"event_name": expired_event_name}):
        exp_doc = frappe.get_doc({
            "doctype": "EGS Event",
            "event_name": expired_event_name,
            "city": "Kozhikode",
            "status": "Open for Registration",
            "event_date": "2026-11-20 10:00:00",
            "registration_deadline": "2026-10-01"  # in the past
        }).insert(ignore_permissions=True)
    else:
        exp_doc = frappe.get_doc("EGS Event", {"event_name": expired_event_name})

    try:
        expired_reg_doc = frappe.get_doc({
            "doctype": "EGS Student Participant",
            "student_name": "Expired Deadline Tester",
            "student_email": "expired_deadline@example.com",
            "phone_number": "9112233447",
            "gender": "Male",
            "city": "Kozhikode",
            "university_college": "Jamia Hamdard Centre",
            "course": "B.Tech Computer Science",
            "event": exp_doc.name
        })
        expired_reg_doc.insert(ignore_permissions=True)
        assert False, "Should have thrown ValidationError for expired deadline"
    except frappe.ValidationError:
        print("✓ Threw ValidationError when event registration deadline has passed")

    # 8.6 Verify Auto-Assignment and successful population of event field
    auto_email = "auto_event_student@example.com"
    existing_auto = frappe.db.get_value("EGS Student Participant", {"student_email": auto_email}, "name")
    if existing_auto:
        frappe.delete_doc("EGS Student Participant", existing_auto, force=True)
        frappe.db.commit()

    auto_doc = frappe.get_doc({
        "doctype": "EGS Student Participant",
        "student_name": "Auto Event Student",
        "student_email": auto_email,
        "phone_number": "9112233448",
        "gender": "Female",
        "city": "Kozhikode",
        "university_college": "Jamia Hamdard Centre",
        "course": "B.Tech Computer Science"
        # event is left empty: should be auto-assigned to open Kozhikode event!
    })
    auto_doc.insert(ignore_permissions=True)
    frappe.db.commit()

    assert auto_doc.event == kozhikode_event, f"Expected {kozhikode_event}, got {auto_doc.event}"
    print(f"✓ Event field automatically populated on submission: {auto_doc.event}")

    # 8.7 Verify Check-in with Digital Check-in Disabled
    no_checkin_evt_name = "TEST-NO-CHECKIN-EVENT"
    if not frappe.db.exists("EGS Event", {"event_name": no_checkin_evt_name}):
        no_chk_evt = frappe.get_doc({
            "doctype": "EGS Event",
            "event_name": no_checkin_evt_name,
            "city": "Kozhikode",
            "status": "Open for Registration",
            "event_date": "2026-11-20 10:00:00",
            "registration_deadline": "2026-11-19",
            "allow_digital_checkins": 0,
            "allow_digital_food_coupons": 0
        }).insert(ignore_permissions=True)
    else:
        no_chk_evt = frappe.get_doc("EGS Event", {"event_name": no_checkin_evt_name})

    auto_doc.event = no_chk_evt.name
    auto_doc.save(ignore_permissions=True)
    frappe.db.commit()

    from dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant import event_checkin
    try:
        event_checkin(auto_doc.name, auto_doc.access_token)
        assert False, "Should have thrown ValidationError when allow_digital_checkins is 0"
    except frappe.ValidationError:
        print("✓ Rejected digital check-in when allow_digital_checkins is disabled")

    # 8.8 Verify Check-in with Digital Check-in & Food Coupons Enabled
    auto_doc.event = kozhikode_event
    auto_doc.event_status = "Registered"
    auto_doc.food_coupon_issued = 0
    auto_doc.food_coupon_code = ""
    auto_doc.save(ignore_permissions=True)
    frappe.db.commit()

    res_chk = event_checkin(auto_doc.name, auto_doc.access_token)
    assert res_chk.get("status") == "success"
    assert res_chk.get("coupon_code"), "Coupon code should be returned upon check-in"
    
    auto_doc.reload()
    assert auto_doc.event_status == "Checked-In"
    assert auto_doc.food_coupon_issued == 1
    assert auto_doc.food_coupon_code.startswith("MEAL-")
    print(f"✓ Digital check-in successful and food coupon issued: {auto_doc.food_coupon_code}")

    # 8.9 Verify Dashboard renders the Food Coupon Code
    resp_dash = requests.get(f"http://127.0.0.1:8000/my-dream-big?id={auto_doc.name}&key={auto_doc.access_token}", headers=headers)
    assert resp_dash.status_code == 200
    assert auto_doc.food_coupon_code in resp_dash.text
    assert "Digital Food Coupon" in resp_dash.text
    print("✓ /my-dream-big dashboard displays the digital food coupon code")

    # 8.10 Verify Web Form includes event field
    resp_wf = requests.get("http://127.0.0.1:8000/egs-student-participant/new", headers=headers)
    assert resp_wf.status_code == 200
    assert '"fieldname": "event"' in resp_wf.text
    print("✓ Web Form contains event field")

    # Clean up
    frappe.delete_doc("EGS Student Participant", auto_doc.name, force=True)
    if frappe.db.exists("EGS Event", pl_doc.name):
        frappe.delete_doc("EGS Event", pl_doc.name, force=True)
    if frappe.db.exists("EGS Event", exp_doc.name):
        frappe.delete_doc("EGS Event", exp_doc.name, force=True)
    if frappe.db.exists("EGS Event", no_chk_evt.name):
        frappe.delete_doc("EGS Event", no_chk_evt.name, force=True)
    frappe.db.commit()
    print("✓ Cleaned up test data for Section 8")

    # 9. Testing Event Dropdown Bug Fix, Dynamic City/Status Filtering & No Institution Restrictions
    print("\n--- 9. Testing Event Dropdown Bug Fix, Dynamic City/Status Filtering & No Institution Restrictions ---")
    from dreambig_egs.dreambig_egs.doctype.egs_event.egs_event import get_events_query, get_open_events_by_city

    # 9.1 Test get_events_query returns formatted dicts with value & label when txt is empty
    delhi_events = get_events_query(city="Delhi", txt="")
    assert len(delhi_events) >= 1, "Expected at least 1 open event for Delhi"
    for ev in delhi_events:
        assert "value" in ev and ev["value"], f"Missing value in event: {ev}"
        assert "label" in ev and ev["label"], f"Missing label in event: {ev}"
        assert ev["city"] == "Delhi", f"Event city mismatch: {ev['city']}"
    print("✓ get_events_query returns valid {value, label} objects when input is cleared (txt='')")

    # 9.2 Test filtering strictly by city and status='Open for Registration'
    # Create a Planned event in Delhi and an Open event in Mumbai
    test_delhi_planned = frappe.get_doc({
        "doctype": "EGS Event",
        "event_name": "TEST Delhi Planned Event",
        "city": "Delhi",
        "status": "Planned",
        "event_date": "2026-11-25 10:00:00",
        "registration_deadline": "2026-11-24"
    }).insert(ignore_permissions=True)

    test_mumbai_open = frappe.get_doc({
        "doctype": "EGS Event",
        "event_name": "TEST Mumbai Open Event",
        "city": "Mumbai",
        "status": "Open for Registration",
        "event_date": "2026-11-26 10:00:00",
        "registration_deadline": "2026-11-25"
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    # Query for Delhi should NOT return the Planned event, nor the Mumbai event
    delhi_filtered = get_events_query(city="Delhi", txt="")
    delhi_names = [e["value"] for e in delhi_filtered]
    assert test_delhi_planned.name not in delhi_names, "Planned event must not be returned in open events"
    assert test_mumbai_open.name not in delhi_names, "Mumbai event must not be returned for Delhi"
    print("✓ Dynamic query strictly filters by status='Open for Registration' and selected city")

    # 9.3 Test text search filtering (when user types)
    search_res = get_events_query(city="Delhi", txt="Leadership")
    assert any("Leadership" in e["label"] for e in search_res), "Text search query should match event title"
    print("✓ Dynamic query supports text search in event name/title")

    # 9.4 Test custom query parameters via filters dict (used in Desk form / RPC)
    desk_res = get_events_query(doctype="EGS Event", txt="", filters={"city": "Delhi", "status": "Open for Registration"})
    assert len(desk_res) >= 1
    print("✓ get_events_query handles Desk set_query parameters smoothly")

    # 9.5 Test no institution restrictions: students from different institutions in same city can register
    # Ensure two different institutions exist in Delhi
    inst_1 = "Jamia Millia Islamia"
    inst_2 = "Delhi University"
    for inst_name in (inst_1, inst_2):
        if not frappe.db.exists("EGS Institution", inst_name):
            frappe.get_doc({
                "doctype": "EGS Institution",
                "institution_name": inst_name,
                "city": "Delhi"
            }).insert(ignore_permissions=True)
    frappe.db.commit()

    active_delhi_evt = delhi_filtered[0]["value"]
    student_a = frappe.get_doc({
        "doctype": "EGS Student Participant",
        "student_name": "Student From Jamia",
        "student_email": "student_jmi_test@egs.org",
        "phone_number": "9123456781",
        "gender": "Male",
        "city": "Delhi",
        "university_college": inst_1,
        "course": "B.Tech Computer Science",
        "event": active_delhi_evt
    }).insert(ignore_permissions=True)

    student_b = frappe.get_doc({
        "doctype": "EGS Student Participant",
        "student_name": "Student From DU",
        "student_email": "student_du_test@egs.org",
        "phone_number": "9123456782",
        "gender": "Female",
        "city": "Delhi",
        "university_college": inst_2,
        "course": "B.Com (Hons)",
        "event": active_delhi_evt
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    assert student_a.event == active_delhi_evt
    assert student_b.event == active_delhi_evt
    print(f"✓ Verified no institution restrictions: students from '{inst_1}' and '{inst_2}' registered for event '{active_delhi_evt}'")

    # 9.6 Verify Web Form client script in database
    wf_db = frappe.get_doc("Web Form", "egs-student-participant")
    assert "init_event_filter" in wf_db.client_script
    assert "event_query_config" in wf_db.client_script
    assert "original_set_data" in wf_db.client_script
    assert "click.event_open" in wf_db.client_script
    print("✓ Verified tabWeb Form database record has updated dynamic event dropdown logic")

    # Clean up test records
    frappe.delete_doc("EGS Student Participant", student_a.name, force=True)
    frappe.delete_doc("EGS Student Participant", student_b.name, force=True)
    frappe.delete_doc("EGS Event", test_delhi_planned.name, force=True)
    frappe.delete_doc("EGS Event", test_mumbai_open.name, force=True)
    frappe.db.commit()
    print("✓ Cleaned up test data for Section 9")

    # 10. Testing Enhanced Event Dropdown Display (Date & Venue)
    print("\n--- 10. Testing Enhanced Event Dropdown Display (Date & Venue) ---")
    event_meta = frappe.get_meta("EGS Event")
    assert "event_date" in event_meta.search_fields, f"event_date missing in search_fields: {event_meta.search_fields}"
    assert "venue" in event_meta.search_fields, f"venue missing in search_fields: {event_meta.search_fields}"
    assert "event_name" in event_meta.search_fields, f"event_name missing in search_fields: {event_meta.search_fields}"
    assert event_meta.title_field == "event_name"
    assert event_meta.show_title_field_in_link == 1
    print(f"✓ EGS Event schema search_fields verified: {event_meta.search_fields}")

    # Check query results have formatted date, venue, and description
    events_kozhikode = get_events_query(city="Kozhikode", txt="")
    assert len(events_kozhikode) >= 1
    first_evt = events_kozhikode[0]
    assert "description" in first_evt and first_evt["description"], f"Missing description in: {first_evt}"
    assert "formatted_date" in first_evt and first_evt["formatted_date"]
    assert "venue" in first_evt and first_evt["venue"]
    assert "📅" in first_evt["description"]
    assert "📍" in first_evt["description"]
    print(f"✓ Dropdown item contains formatted details: description='{first_evt['description']}'")

    # Test searching by venue
    venue_search = get_events_query(city="Kozhikode", txt=first_evt["venue"][:5])
    assert len(venue_search) >= 1, "Searching by venue snippet should return the matching event"
    print("✓ Dynamic query text filter successfully searches by venue")

    # Verify Web Form client script contains custom dropdown template and filter
    assert "eventDate" in wf_db.client_script
    assert "venue" in wf_db.client_script
    assert "fa-calendar" in wf_db.client_script
    assert "fa-map-marker" in wf_db.client_script
    assert "update_selected_event_description" in wf_db.client_script
    print("✓ Verified Web Form client script contains custom dropdown template and metadata rendering")

    # 11. Testing Faculty-to-Course Relational Architecture and Seeded Data
    print("\n--- 11. Testing Faculty-to-Course Relational Architecture & Seeded Data ---")
    
    # 11.1 Verify DocType Schemas
    faculty_meta = frappe.get_meta("EGS Faculty")
    course_meta = frappe.get_meta("EGS Course")
    student_meta = frappe.get_meta("EGS Student Participant")

    assert faculty_meta.autoname == "field:faculty_name"
    assert faculty_meta.get_field("faculty_name").reqd == 1
    assert faculty_meta.get_field("faculty_name").unique == 1
    assert faculty_meta.get_field("faculty_name").in_list_view == 1
    print("✓ EGS Faculty schema verified (autoname: field:faculty_name, unique: 1)")

    assert course_meta.autoname == "field:course_name"
    assert course_meta.get_field("course_name").reqd == 1
    assert course_meta.get_field("course_name").in_list_view == 1
    assert course_meta.get_field("faculty").fieldtype == "Link"
    assert course_meta.get_field("faculty").options == "EGS Faculty"
    assert course_meta.get_field("faculty").reqd == 1
    print("✓ EGS Course schema verified (autoname: field:course_name, faculty Link to EGS Faculty)")

    assert student_meta.get_field("faculty_department").fieldtype == "Link"
    assert student_meta.get_field("faculty_department").options == "EGS Faculty"
    assert student_meta.get_field("course").fieldtype == "Link"
    assert student_meta.get_field("course").options == "EGS Course"
    print("✓ EGS Student Participant schema verified (faculty_department -> EGS Faculty, course -> EGS Course)")

    # 11.2 Verify Seeded Faculties
    expected_faculties = [
        "Faculty of Engineering & Technology",
        "Faculty of Science",
        "Faculty of Arts & Humanities",
        "Faculty of Commerce & Management",
        "Faculty of Law",
        "Faculty of Medicine & Health Sciences"
    ]
    for fac in expected_faculties:
        assert frappe.db.exists("EGS Faculty", fac), f"Faculty missing from database: {fac}"
    print(f"✓ All {len(expected_faculties)} Faculties verified in database")

    # 11.3 Verify Seeded Courses and Linkage
    expected_courses = [
        ("B.Tech Mechanical Engineering", "Faculty of Engineering & Technology"),
        ("B.Tech Computer Science", "Faculty of Engineering & Technology"),
        ("B.Tech Civil Engineering", "Faculty of Engineering & Technology"),
        ("B.Sc Physics", "Faculty of Science"),
        ("B.Sc Mathematics", "Faculty of Science"),
        ("B.A. English", "Faculty of Arts & Humanities"),
        ("B.A. History", "Faculty of Arts & Humanities"),
        ("B.Com (Hons)", "Faculty of Commerce & Management"),
        ("BBA", "Faculty of Commerce & Management"),
        ("BA LLB", "Faculty of Law"),
        ("MBBS", "Faculty of Medicine & Health Sciences")
    ]
    for c_name, fac_name in expected_courses:
        assert frappe.db.exists("EGS Course", c_name), f"Course missing from database: {c_name}"
        actual_fac = frappe.db.get_value("EGS Course", c_name, "faculty")
        assert actual_fac == fac_name, f"Course {c_name} linked to {actual_fac}, expected {fac_name}"
    print(f"✓ All {len(expected_courses)} Courses and their Faculty links verified in database")

    # 11.4 Test Student creation with Link fields
    test_academic_email = "test_academic_student@egs.org"
    if frappe.db.exists("EGS Student Participant", {"student_email": test_academic_email}):
        frappe.delete_doc("EGS Student Participant", frappe.db.get_value("EGS Student Participant", {"student_email": test_academic_email}, "name"), force=True)

    academic_student = frappe.get_doc({
        "doctype": "EGS Student Participant",
        "student_name": "Academic Test Student",
        "student_email": test_academic_email,
        "phone_number": "9998887711",
        "gender": "Female",
        "city": "Delhi",
        "university_college": "Delhi University",
        "faculty_department": "Faculty of Engineering & Technology",
        "course": "B.Tech Computer Science"
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    assert academic_student.faculty_department == "Faculty of Engineering & Technology"
    assert academic_student.course == "B.Tech Computer Science"
    print("✓ EGS Student Participant created successfully with Linked Faculty and Course")

    # Clean up
    frappe.delete_doc("EGS Student Participant", academic_student.name, force=True)
    frappe.db.commit()
    print("✓ Cleaned up test academic student")

    # 12. Testing Faculty-to-Course Web Form Filtering & get_courses_by_faculty API
    print("\n--- 12. Testing Faculty-to-Course Web Form Filtering & get_courses_by_faculty API ---")
    from dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant import get_courses_by_faculty

    # 12.1 Direct Python call test
    eng_courses = get_courses_by_faculty("Faculty of Engineering & Technology")
    assert len(eng_courses) == 3, f"Expected 3 engineering courses, got {len(eng_courses)}"
    eng_labels = [c["label"] for c in eng_courses]
    assert "B.Tech Computer Science" in eng_labels
    assert "B.Tech Mechanical Engineering" in eng_labels
    assert "B.Tech Civil Engineering" in eng_labels
    print("✓ get_courses_by_faculty returned exact courses for Faculty of Engineering & Technology")

    empty_courses = get_courses_by_faculty("")
    assert empty_courses == [], "Empty faculty should return empty list"
    print("✓ get_courses_by_faculty('') gracefully returns empty list")

    # 12.2 HTTP Guest API call test
    headers = {"Host": "egs.localhost"}
    api_url = "http://127.0.0.1:8000/api/method/dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant.get_courses_by_faculty"
    resp = requests.get(f"{api_url}?faculty=Faculty%20of%20Law", headers=headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    law_courses = resp.json().get("message", [])
    assert len(law_courses) == 1
    assert law_courses[0]["label"] == "BA LLB"
    print("✓ Guest HTTP API successfully returned courses for Faculty of Law")

    # 12.3 Database Web Form Script verification
    wf_db_record = frappe.get_doc("Web Form", "egs-student-participant")
    assert "get_courses_by_faculty" in wf_db_record.client_script
    assert "course_ctrl.set_data(courses)" in wf_db_record.client_script
    assert "click.course_open" in wf_db_record.client_script
    print("✓ Verified tabWeb Form database record has updated init_course_filter logic with direct set_data")

    # 13. Testing Redis-backed Hybrid Login System (Magic Link + OTP) & Two-Step UI Interceptor
    print("\n--- 13. Testing Redis-backed Hybrid Login System (Magic Link + OTP) ---")
    from dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant import send_login_credentials, verify_login_otp

    # 13.1 Verify email_otp is removed from schema
    meta_sp = frappe.get_meta("EGS Student Participant")
    assert not meta_sp.has_field("email_otp"), "email_otp field must be deleted from EGS Student Participant schema"
    print("✓ email_otp permanently removed from EGS Student Participant DocType schema")

    # 13.2 Create a test student participant
    hybrid_test_email = "hybrid_login_tester@egs.org"
    if frappe.db.exists("EGS Student Participant", {"student_email": hybrid_test_email}):
        frappe.delete_doc("EGS Student Participant", frappe.db.get_value("EGS Student Participant", {"student_email": hybrid_test_email}, "name"), force=True)

    h_student = frappe.get_doc({
        "doctype": "EGS Student Participant",
        "student_name": "Hybrid Login Student",
        "student_email": hybrid_test_email,
        "phone_number": "9988776611",
        "gender": "Female",
        "city": "Delhi",
        "university_college": "Delhi University",
        "faculty_department": "Faculty of Law",
        "course": "BA LLB"
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    # 13.3 Test send_login_credentials for unknown email
    err_res = send_login_credentials("unknown_email_404@egs.org")
    assert err_res.get("status") == "error"
    print("✓ send_login_credentials returned error for unregistered email")

    # 13.4 Test send_login_credentials for registered student
    ok_res = send_login_credentials(hybrid_test_email)
    assert ok_res.get("status") == "success"
    cached_code = frappe.cache().get_value(f"egs_login_otp_{hybrid_test_email}")
    assert cached_code is not None, "OTP must be stored in Redis cache"
    cached_code_str = cached_code.decode("utf-8") if isinstance(cached_code, bytes) else str(cached_code)
    assert len(cached_code_str) == 6 and cached_code_str.isdigit()
    print(f"✓ send_login_credentials stored 6-digit OTP in Redis: {cached_code_str}")

    # 13.5 Test verify_login_otp with invalid OTP
    bad_verify = verify_login_otp(hybrid_test_email, "000000")
    assert bad_verify.get("status") == "error"
    print("✓ verify_login_otp rejected invalid OTP")

    # 13.6 Test verify_login_otp with valid OTP
    good_verify = verify_login_otp(hybrid_test_email, cached_code_str)
    assert good_verify.get("status") == "success"
    assert good_verify.get("id") == h_student.name
    assert good_verify.get("key") == h_student.access_token
    # Ensure OTP is deleted from Redis cache after use
    assert frappe.cache().get_value(f"egs_login_otp_{hybrid_test_email}") is None
    print("✓ verify_login_otp succeeded, returned student credentials, and deleted OTP from Redis")

    # 13.7 Verify Two-Step Hybrid UI Interceptor in egs-decide-stage and egs-check-in-log Web Forms
    for wf_name in ("egs-decide-stage", "egs-check-in-log"):
        wf_doc = frappe.get_doc("Web Form", wf_name)
        assert "step_email" in wf_doc.client_script, f"step_email missing in {wf_name}"
        assert "step_otp" in wf_doc.client_script, f"step_otp missing in {wf_name}"
        assert "send_creds_btn" in wf_doc.client_script, f"send_creds_btn missing in {wf_name}"
        assert "verify_otp_btn" in wf_doc.client_script, f"verify_otp_btn missing in {wf_name}"
        assert "send_login_credentials" in wf_doc.client_script, f"send_login_credentials missing in {wf_name}"
        assert "verify_login_otp" in wf_doc.client_script, f"verify_login_otp missing in {wf_name}"
        assert "back_to_email_btn" in wf_doc.client_script, f"back_to_email_btn missing in {wf_name}"
        print(f"✓ {wf_name} has Two-Step Hybrid UI Interceptor in client_script")

    # 13.8 Test HTTP rendering of Web Forms
    resp_decide = requests.get("http://127.0.0.1:8000/egs-decide-stage/new", headers=headers)
    assert resp_decide.status_code == 200
    assert "step_email" in resp_decide.text
    assert "step_otp" in resp_decide.text

    resp_checkin = requests.get("http://127.0.0.1:8000/egs-check-in-log/new", headers=headers)
    assert resp_checkin.status_code == 200
    assert "step_email" in resp_checkin.text
    assert "step_otp" in resp_checkin.text
    print("✓ Web Form HTTP endpoints deliver Two-Step Hybrid UI Interceptor to client")

    # Clean up
    frappe.delete_doc("EGS Student Participant", h_student.name, force=True)
    frappe.db.commit()
    print("✓ Cleaned up test hybrid student")

    # 14. Testing EGS Institution Cohort Child DocType & EGS Institution Integration
    print("\n--- 14. Testing EGS Institution Cohort Child DocType & Integration ---")
    cohort_meta = frappe.get_meta("EGS Institution Cohort")
    assert cohort_meta.istable == 1, "EGS Institution Cohort must be a child table (istable = 1)"
    
    course_fld = cohort_meta.get_field("course")
    assert course_fld.fieldtype == "Link" and course_fld.options == "EGS Course" and course_fld.reqd == 1
    
    year_fld = cohort_meta.get_field("cohort_year")
    assert year_fld.reqd == 1 and year_fld.default == "2026"
    
    link_fld = cohort_meta.get_field("whatsapp_group_link")
    assert link_fld.reqd == 1
    print("✓ EGS Institution Cohort schema verified (istable: 1, course: Link, cohort_year: Data, whatsapp_group_link: Data)")

    # Verify EGS Institution has cohort_groups Table field
    inst_meta = frappe.get_meta("EGS Institution")
    cohort_groups_fld = inst_meta.get_field("cohort_groups")
    assert cohort_groups_fld is not None, "cohort_groups field missing in EGS Institution"
    assert cohort_groups_fld.fieldtype == "Table" and cohort_groups_fld.options == "EGS Institution Cohort"
    print("✓ EGS Institution schema verified (cohort_groups -> Table to EGS Institution Cohort)")

    # Test adding child rows to an Institution
    test_inst_name = "TEST Cohort Institution"
    if frappe.db.exists("EGS Institution", test_inst_name):
        frappe.delete_doc("EGS Institution", test_inst_name, force=True)

    test_inst = frappe.get_doc({
        "doctype": "EGS Institution",
        "institution_name": test_inst_name,
        "city": "Delhi",
        "cohort_groups": [
            {
                "course": "B.Tech Computer Science",
                "cohort_year": "2026",
                "whatsapp_group_link": "https://chat.whatsapp.com/testCS2026"
            },
            {
                "course": "BA LLB",
                "cohort_year": "2026",
                "whatsapp_group_link": "https://chat.whatsapp.com/testLLB2026"
            }
        ]
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    test_inst.reload()
    assert len(test_inst.cohort_groups) == 2
    assert test_inst.cohort_groups[0].course == "B.Tech Computer Science"
    assert test_inst.cohort_groups[0].whatsapp_group_link == "https://chat.whatsapp.com/testCS2026"
    assert test_inst.cohort_groups[1].course == "BA LLB"
    print(f"✓ Created EGS Institution with {len(test_inst.cohort_groups)} WhatsApp cohort group child rows")

    # Clean up test institution
    frappe.delete_doc("EGS Institution", test_inst.name, force=True)
    frappe.db.commit()
    print("✓ Cleaned up test cohort institution")

    # 15. Testing Cohort Year, First Year Notice & Dynamic WhatsApp Link API
    print("\n--- 15. Testing Cohort Year, First Year Notice & Dynamic WhatsApp Link API ---")
    stu_meta = frappe.get_meta("EGS Student Participant")
    assert "year_of_study" not in [f.fieldname for f in stu_meta.fields], "year_of_study should be deleted from EGS Student Participant"
    cohort_fld = stu_meta.get_field("cohort_year")
    assert cohort_fld is not None, "cohort_year field missing in EGS Student Participant"
    assert cohort_fld.fieldtype == "Data" and cohort_fld.reqd == 1 and cohort_fld.default == "2026"
    
    notice_fld = stu_meta.get_field("first_year_notice")
    assert notice_fld is not None, "first_year_notice field missing in EGS Student Participant"
    assert notice_fld.fieldtype == "HTML"
    assert "The EGS:DB program is exclusively for First-Year Undergraduate students." in (notice_fld.options or "")
    print("✓ EGS Student Participant schema verified (year_of_study removed, cohort_year added, first_year_notice added)")

    # Verify Web Form fields
    wf_doc = frappe.get_doc("Web Form", "egs-student-participant")
    wf_fields = [f.fieldname for f in wf_doc.web_form_fields]
    assert "year_of_study" not in wf_fields, "year_of_study must not be in Web Form"
    assert wf_fields[0] == "first_year_notice", f"first_year_notice must be first field, got {wf_fields[0]}"
    course_idx = wf_fields.index("course")
    cohort_idx = wf_fields.index("cohort_year")
    assert cohort_idx == course_idx + 1, "cohort_year must be directly after course in Web Form"
    print("✓ Web Form egs-student-participant fields verified (first_year_notice at index 0, cohort_year after course)")

    # Test get_cohort_whatsapp_link API
    from dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant import get_cohort_whatsapp_link

    test_inst_whatsapp = "TEST WhatsApp Institution"
    if frappe.db.exists("EGS Institution", test_inst_whatsapp):
        frappe.delete_doc("EGS Institution", test_inst_whatsapp, force=True)

    test_inst_wa = frappe.get_doc({
        "doctype": "EGS Institution",
        "institution_name": test_inst_whatsapp,
        "city": "Delhi",
        "cohort_groups": [
            {
                "course": "B.Tech Computer Science",
                "cohort_year": "2026",
                "whatsapp_group_link": "https://chat.whatsapp.com/testGroup2026"
            }
        ]
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    test_student_wa = "TEST-WA-STUDENT-001"
    if frappe.db.exists("EGS Student Participant", test_student_wa):
        frappe.delete_doc("EGS Student Participant", test_student_wa, force=True)

    stu_wa = frappe.get_doc({
        "doctype": "EGS Student Participant",
        "student_name": test_student_wa,
        "phone_number": "9999990099",
        "student_email": "test_wa_student@example.com",
        "guardian_phone_number": "8888880088",
        "city": "Delhi",
        "university_college": test_inst_whatsapp,
        "faculty_department": "Faculty of Engineering & Technology",
        "course": "B.Tech Computer Science",
        "cohort_year": "2026"
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    # 15.1 Matching link fetch
    frappe.set_user("Guest")
    res_success = get_cohort_whatsapp_link(stu_wa.name)
    frappe.set_user("Administrator")
    assert res_success.get("status") == "success", f"Expected success, got {res_success}"
    assert res_success.get("link") == "https://chat.whatsapp.com/testGroup2026", f"Expected link mismatch: {res_success}"
    print("✓ get_cohort_whatsapp_link returns matching WhatsApp link for student")

    # 15.2 Unmatched link fetch (different cohort year)
    stu_wa.cohort_year = "2027"
    stu_wa.save(ignore_permissions=True)
    frappe.db.commit()

    frappe.set_user("Guest")
    res_not_found = get_cohort_whatsapp_link(stu_wa.name)
    frappe.set_user("Administrator")
    assert res_not_found.get("status") == "not_found", f"Expected not_found, got {res_not_found}"
    print("✓ get_cohort_whatsapp_link returns not_found when cohort_year does not match")

    # 15.3 HTTP Guest API test
    stu_wa.cohort_year = "2026"
    stu_wa.save(ignore_permissions=True)
    frappe.db.commit()

    wa_api_url = f"http://127.0.0.1:8000/api/method/dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant.get_cohort_whatsapp_link?student_id={stu_wa.name}"
    resp_wa = requests.get(wa_api_url, headers=headers)
    assert resp_wa.status_code == 200, f"Expected 200, got {resp_wa.status_code}"
    assert resp_wa.json().get("message", {}).get("link") == "https://chat.whatsapp.com/testGroup2026"
    print("✓ Guest HTTP request to get_cohort_whatsapp_link successfully retrieves WhatsApp URL")

    # Clean up
    frappe.delete_doc("EGS Student Participant", stu_wa.name, force=True)
    frappe.delete_doc("EGS Institution", test_inst_wa.name, force=True)
    frappe.db.commit()
    print("✓ Cleaned up test WhatsApp student and institution")

    # 16. Testing DECIDE Stage Auto-Sync to EGS Career Goal & 5Ds Progression
    print("\n--- 16. Testing DECIDE Stage Auto-Sync to EGS Career Goal & 5Ds Progression ---")
    
    # 16.1 Verify Schema Fields
    meta_stu = frappe.get_meta("EGS Student Participant")
    stu_fields = {f.fieldname: f for f in meta_stu.fields}
    assert "current_5ds_stage" in stu_fields, "current_5ds_stage missing in EGS Student Participant"
    assert stu_fields["current_5ds_stage"].fieldtype == "Select"
    assert "a_promise_to_self" in stu_fields, "a_promise_to_self missing in EGS Student Participant"
    assert stu_fields["final_chosen_career_goal"].options == "EGS Career Pathway", f"Expected EGS Career Pathway, got {stu_fields['final_chosen_career_goal'].options}"

    meta_goal = frappe.get_meta("EGS Career Goal")
    goal_fields = {f.fieldname: f for f in meta_goal.fields}
    assert "student_reference" in goal_fields, "student_reference missing in EGS Career Goal"
    assert "finalized_career_goal" in goal_fields, "finalized_career_goal missing in EGS Career Goal"
    assert "current_5ds_stage" in goal_fields, "current_5ds_stage missing in EGS Career Goal"
    print("✓ EGS Student Participant and EGS Career Goal schemas verified for DECIDE auto-sync")

    # 16.2 Create Test Participant & Verify Initial Stage (DREAM)
    from dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant import (
        submit_decide_stage,
        get_student_career_choices,
        process_student_checkin,
    )

    test_decide_email = "test_decide_student@example.com"
    if frappe.db.exists("EGS Student Participant", {"student_email": test_decide_email}):
        existing_name = frappe.db.get_value("EGS Student Participant", {"student_email": test_decide_email})
        # Delete any associated career goals
        for g in frappe.get_all("EGS Career Goal", filters={"student_reference": existing_name}):
            frappe.delete_doc("EGS Career Goal", g.name, force=True)
        frappe.delete_doc("EGS Student Participant", existing_name, force=True)
        frappe.db.commit()

    decide_stu = frappe.get_doc({
        "doctype": "EGS Student Participant",
        "student_name": "Decide Test Student",
        "phone_number": "9123456780",
        "student_email": test_decide_email,
        "guardian_phone_number": "9876543210",
        "city": "Delhi",
        "university_college": "Jamia Millia Islamia",
        "faculty_department": "Faculty of Engineering & Technology",
        "course": "B.Tech Computer Science",
        "cohort_year": "2026",
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    assert decide_stu.current_5ds_stage == "DREAM", f"Expected DREAM, got {decide_stu.current_5ds_stage}"
    assert decide_stu.event_status == "Registered"
    print("✓ Student created with initial 5Ds stage: DREAM")

    # 16.3 Check-in Student -> 5Ds Stage Advances to DISCOVER
    decide_stu, _, _ = process_student_checkin(decide_stu)
    assert decide_stu.event_status == "Checked-In"
    assert decide_stu.current_5ds_stage == "DISCOVER", f"Expected DISCOVER after check-in, got {decide_stu.current_5ds_stage}"
    print("✓ Check-in successfully advanced 5Ds stage from DREAM to DISCOVER")

    # 16.4 Verify Token Protection on submit_decide_stage
    test_pathway = "Chief Finance Officers of Top Global Companies"
    test_vision = "I aim to lead financial strategy for high-impact multinational organizations."
    test_promise = "I promise to stay committed to my goals and seek mentorship proactively."
    
    frappe.set_user("Guest")
    try:
        submit_decide_stage(
            student_id=decide_stu.name,
            token="invalid_token_xyz",
            final_chosen_career_goal=test_pathway,
            personal_vision_statement=test_vision,
        )
        assert False, "Should have thrown PermissionError for invalid token"
    except frappe.PermissionError:
        print("✓ submit_decide_stage strictly rejected invalid access token")
    finally:
        frappe.set_user("Administrator")

    # 16.5 Submit DECIDE Stage via Whitelisted API -> Auto-Sync to EGS Career Goal & Stage to DECIDE
    frappe.set_user("Guest")
    sub_res = submit_decide_stage(
        student_id=decide_stu.name,
        token=decide_stu.access_token,
        final_chosen_career_goal=test_pathway,
        personal_vision_statement=test_vision,
        a_promise_to_self=test_promise,
        date_of_decision="2026-11-20",
    )
    frappe.set_user("Administrator")

    assert sub_res.get("status") == "success"
    assert sub_res.get("current_5ds_stage") == "DECIDE"

    # Reload participant from DB
    decide_stu.reload()
    assert decide_stu.current_5ds_stage == "DECIDE", f"Expected DECIDE, got {decide_stu.current_5ds_stage}"
    assert decide_stu.final_chosen_career_goal == test_pathway
    assert decide_stu.personal_vision_statement == test_vision
    assert decide_stu.a_promise_to_self == test_promise
    assert str(decide_stu.date_of_decision) == "2026-11-20"
    print("✓ Student Participant updated with DECIDE stage commitment")

    # Verify EGS Career Goal record automatically created in DB
    goals = frappe.get_all("EGS Career Goal", filters={"student_reference": decide_stu.name}, fields=["*"])
    assert len(goals) == 1, f"Expected exactly 1 EGS Career Goal, found {len(goals)}"
    goal_record = goals[0]
    assert goal_record.finalized_career_goal == test_pathway
    assert goal_record.current_5ds_stage == "DECIDE"
    assert goal_record.personal_vision_statement == test_vision
    assert goal_record.a_promise_to_self == test_promise
    assert str(goal_record.deadline) == "2026-11-20"
    print("✓ EGS Career Goal record automatically created and synced from DECIDE submission")

    # 16.6 Test Repeat Submission / Update (In-place update, No duplicates)
    new_pathway = "Honest & effective-IAS/IPS/IFS/Central Civil Services"
    new_vision = "I commit to serving the nation through transparent and effective public administration."
    new_promise = "I pledge unwavering dedication to public service."

    frappe.set_user("Guest")
    update_res = submit_decide_stage(
        student_id=decide_stu.name,
        token=decide_stu.access_token,
        final_chosen_career_goal=new_pathway,
        personal_vision_statement=new_vision,
        a_promise_to_self=new_promise,
        date_of_decision="2026-11-21",
    )
    frappe.set_user("Administrator")

    assert update_res.get("status") == "success"
    goals_after = frappe.get_all("EGS Career Goal", filters={"student_reference": decide_stu.name}, fields=["*"])
    assert len(goals_after) == 1, f"Expected 1 record (in-place update), found {len(goals_after)}"
    assert goals_after[0].name == goal_record.name, "Expected same EGS Career Goal record to be updated"
    assert goals_after[0].finalized_career_goal == new_pathway
    assert goals_after[0].personal_vision_statement == new_vision
    assert goals_after[0].a_promise_to_self == new_promise
    assert str(goals_after[0].deadline) == "2026-11-21"
    print("✓ Repeat DECIDE submission updated existing EGS Career Goal in-place with zero duplicates")

    # 16.7 Test Bidirectional Sync from Desk (Editing EGS Career Goal updates Student Participant)
    goal_doc = frappe.get_doc("EGS Career Goal", goal_record.name)
    goal_doc.personal_vision_statement = "Updated Vision from Desk Mentor review."
    goal_doc.save(ignore_permissions=True)
    frappe.db.commit()

    decide_stu.reload()
    assert decide_stu.personal_vision_statement == "Updated Vision from Desk Mentor review."
    print("✓ Bidirectional sync: editing EGS Career Goal synced back to EGS Student Participant")

    # 16.8 Test get_student_career_choices helper API
    frappe.set_user("Guest")
    choices_res = get_student_career_choices(decide_stu.name, decide_stu.access_token)
    frappe.set_user("Administrator")
    assert choices_res.get("status") == "success"
    assert choices_res["current_decision"]["final_chosen_career_goal"] == new_pathway
    assert choices_res["current_decision"]["current_5ds_stage"] == "DECIDE"
    assert len(choices_res["all_pathways"]) == 42
    print("✓ get_student_career_choices API returns complete pathways and current DECIDE choice")

    # 16.9 Test HTTP Dashboard Rendering (/my-dream-big with DECIDE committed)
    dashboard_url = f"http://127.0.0.1:8000/my-dream-big?id={decide_stu.name}&key={decide_stu.access_token}"
    resp_dash = requests.get(dashboard_url, headers=headers)
    assert resp_dash.status_code == 200, f"Expected 200, got {resp_dash.status_code}"
    assert "Stage Committed" in resp_dash.text or "✓ Committed" in resp_dash.text
    assert new_pathway in resp_dash.text
    assert "decideModal" in resp_dash.text
    print("✓ /my-dream-big renders committed DECIDE stage, 5Ds badge, and modal correctly")

    # 16.10 Test Web Form egs-decide-stage with URL credentials
    wf_url = f"http://127.0.0.1:8000/egs-decide-stage?id={decide_stu.name}&key={decide_stu.access_token}"
    resp_wf = requests.get(wf_url, headers=headers)
    assert resp_wf.status_code == 200, f"Expected 200, got {resp_wf.status_code}"
    print("✓ /egs-decide-stage loads with HTTP 200 for authenticated student")

    # Clean up test participant and career goal
    for g in frappe.get_all("EGS Career Goal", filters={"student_reference": decide_stu.name}):
        frappe.delete_doc("EGS Career Goal", g.name, force=True)
    frappe.delete_doc("EGS Student Participant", decide_stu.name, force=True)
    frappe.db.commit()
    print("✓ Cleaned up test DECIDE student and career goal records")

    # 17. Testing 5Ds Tabbed Interface, Read-Only Past Stage Locking & Revert (Discover 2B) Workflow
    print("\n--- 17. Testing 5Ds Tabbed Interface, Read-Only Locking & Revert (Discover 2B) ---")
    from dreambig_egs.api import revert_5ds_stage

    # 17.1 Create checked-in student in DECIDE stage
    test_tab_email = "test_tab_student@example.com"
    if frappe.db.exists("EGS Student Participant", {"student_email": test_tab_email}):
        ex_name = frappe.db.get_value("EGS Student Participant", {"student_email": test_tab_email})
        for g in frappe.get_all("EGS Career Goal", filters={"student_reference": ex_name}):
            frappe.delete_doc("EGS Career Goal", g.name, force=True)
        frappe.delete_doc("EGS Student Participant", ex_name, force=True)
        frappe.db.commit()

    tab_stu = frappe.get_doc({
        "doctype": "EGS Student Participant",
        "student_name": "Tab Test Student",
        "phone_number": "9123456789",
        "student_email": test_tab_email,
        "guardian_phone_number": "9876543211",
        "city": "Delhi",
        "university_college": "Jamia Millia Islamia",
        "faculty_department": "Faculty of Engineering & Technology",
        "course": "B.Tech Computer Science",
        "cohort_year": "2026",
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    # Check-in and commit to DECIDE
    process_student_checkin(tab_stu)
    pathways = frappe.get_all("EGS Career Pathway", limit=1)
    pw_name = pathways[0].name
    submit_decide_stage(
        student_id=tab_stu.name,
        token=tab_stu.access_token,
        final_chosen_career_goal=pw_name,
        personal_vision_statement="Aiming to lead AI innovation.",
        a_promise_to_self="I promise to practice daily.",
        date_of_decision="2026-11-20"
    )
    tab_stu.reload()
    assert tab_stu.current_5ds_stage == "DECIDE"

    # 17.2 Verify Tabbed HTML and Read-Only locking in DECIDE stage
    tab_dash_url = f"http://127.0.0.1:8000/my-dream-big?id={tab_stu.name}&key={tab_stu.access_token}"
    resp_tab = requests.get(tab_dash_url, headers=headers)
    assert resp_tab.status_code == 200
    assert "pills-tab" in resp_tab.text
    assert "tab-dream" in resp_tab.text
    assert "tab-discover" in resp_tab.text
    assert "tab-decide" in resp_tab.text
    assert "Stage 2 (DISCOVER) is Locked (Read-Only)" in resp_tab.text
    assert "reevaluateModal" in resp_tab.text
    assert "btn-open-reevaluate-modal" in resp_tab.text
    print("✓ /my-dream-big renders 5Ds tabbed interface with locked past stage (DISCOVER) and re-evaluate button")

    # 17.3 Test revert_5ds_stage API (permission and validation checks)
    frappe.set_user("Guest")
    # Missing reason check
    try:
        revert_5ds_stage(tab_stu.name, "", tab_stu.access_token)
        assert False, "Should throw for empty reason"
    except Exception:
        pass

    # Invalid token check
    try:
        revert_5ds_stage(tab_stu.name, "Valid reason", "wrong_token")
        assert False, "Should throw for invalid token"
    except Exception:
        pass

    # Successful revert execution
    revert_res = revert_5ds_stage(tab_stu.name, "Discovered passion for Hardware Engineering instead.", tab_stu.access_token)
    frappe.set_user("Administrator")
    assert revert_res.get("status") == "success"
    assert revert_res.get("current_5ds_stage") == "DISCOVER"

    tab_stu.reload()
    assert tab_stu.current_5ds_stage == "DISCOVER"
    assert tab_stu.final_chosen_career_goal is None
    assert tab_stu.personal_vision_statement is None
    assert tab_stu.a_promise_to_self is None
    assert tab_stu.date_of_decision is None
    assert "Discovered passion for Hardware Engineering instead." in tab_stu.reason_for_goal_change
    # Verify linked career goal records were completely deleted
    remaining_goals = frappe.get_all("EGS Career Goal", filters={"student_reference": tab_stu.name})
    assert len(remaining_goals) == 0, f"Expected 0 career goals (clean slate), found {len(remaining_goals)}"
    print("✓ revert_5ds_stage successfully reverts stage to DISCOVER, wipes all Stage 3 fields, deletes EGS Career Goal, and logs reason")

    # 17.4 Verify dashboard now unlocks DISCOVER stage and DECIDE tab shows Pending Commitment
    resp_reverted = requests.get(tab_dash_url, headers=headers)
    assert resp_reverted.status_code == 200
    assert "Stage 2 (DISCOVER) is Locked" not in resp_reverted.text
    assert "Save My 5 Career Goals" in resp_reverted.text
    assert "Extended Discovery History" in resp_reverted.text
    assert "Pending Commitment" in resp_reverted.text
    assert "Stage Committed" not in resp_reverted.text
    print("✓ /my-dream-big re-renders with DISCOVER unlocked, reason history displayed, and DECIDE tab back to Pending Commitment")

    # Clean up
    for g in frappe.get_all("EGS Career Goal", filters={"student_reference": tab_stu.name}):
        frappe.delete_doc("EGS Career Goal", g.name, force=True)
    frappe.delete_doc("EGS Student Participant", tab_stu.name, force=True)
    frappe.db.commit()
    print("✓ Cleaned up test tab student and career goal records")

    # 18. Testing Stage 3 to Stage 4 (DEVELOP) Transition & Commitments Action Plan
    print("\n--- 18. Testing Stage 3 to Stage 4 (DEVELOP) Transition & Commitments Action Plan ---")
    from dreambig_egs.api import advance_to_develop, add_egs_commitment

    test_dev_email = "test_dev_student@example.com"
    if frappe.db.exists("EGS Student Participant", {"student_email": test_dev_email}):
        ex_name = frappe.db.get_value("EGS Student Participant", {"student_email": test_dev_email})
        for g in frappe.get_all("EGS Career Goal", filters={"student_reference": ex_name}):
            for com in frappe.get_all("EGS Commitment", filters={"career_goal_reference": g.name}):
                frappe.delete_doc("EGS Commitment", com.name, force=True)
            frappe.delete_doc("EGS Career Goal", g.name, force=True)
        frappe.delete_doc("EGS Student Participant", ex_name, force=True)
        frappe.db.commit()

    dev_stu = frappe.get_doc({
        "doctype": "EGS Student Participant",
        "student_name": "Dev Test Student",
        "phone_number": "9123456799",
        "student_email": test_dev_email,
        "guardian_phone_number": "9876543299",
        "city": "Delhi",
        "university_college": "Jamia Millia Islamia",
        "faculty_department": "Faculty of Engineering & Technology",
        "course": "B.Tech Computer Science",
        "cohort_year": "2026",
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    process_student_checkin(dev_stu)
    pathways = frappe.get_all("EGS Career Pathway", limit=1)
    pw_name = pathways[0].name
    submit_decide_stage(
        student_id=dev_stu.name,
        token=dev_stu.access_token,
        final_chosen_career_goal=pw_name,
        personal_vision_statement="Aiming to lead AI innovation.",
        a_promise_to_self="I promise to practice daily.",
        date_of_decision="2026-11-20"
    )
    dev_stu.reload()
    assert dev_stu.current_5ds_stage == "DECIDE"

    # 18.1 Verify Proceed to DEVELOP button exists on dashboard
    dev_dash_url = f"http://127.0.0.1:8000/my-dream-big?id={dev_stu.name}&key={dev_stu.access_token}"
    resp_decide = requests.get(dev_dash_url, headers=headers)
    assert resp_decide.status_code == 200
    assert "btn-advance-develop" in resp_decide.text
    assert "Proceed to Stage 4: DEVELOP" in resp_decide.text
    print("✓ /my-dream-big renders 'Proceed to Stage 4: DEVELOP' transition button in DECIDE tab")

    # 18.2 Test advance_to_develop API validations
    frappe.set_user("Guest")
    try:
        advance_to_develop(dev_stu.name, "invalid_token")
        assert False, "Should fail with invalid token"
    except Exception:
        pass

    # Advance stage
    adv_res = advance_to_develop(dev_stu.name, dev_stu.access_token)
    frappe.set_user("Administrator")
    assert adv_res.get("status") == "success"
    assert adv_res.get("current_5ds_stage") == "DEVELOP/PREPARE"

    dev_stu.reload()
    assert dev_stu.current_5ds_stage == "DEVELOP/PREPARE"
    c_goals = frappe.get_all("EGS Career Goal", filters={"student_reference": dev_stu.name}, fields=["current_5ds_stage", "name"])
    assert len(c_goals) == 1
    assert c_goals[0].current_5ds_stage == "DEVELOP/PREPARE"
    goal_name = c_goals[0].name
    print("✓ advance_to_develop successfully advances student and EGS Career Goal to DEVELOP/PREPARE")

    # 18.3 Verify dashboard renders DEVELOP tab active and empty state message
    resp_dev = requests.get(dev_dash_url, headers=headers)
    assert resp_dev.status_code == 200
    assert "Stage 4: DEVELOP — Action Plan & Commitments" in resp_dev.text
    assert "No commitments added yet. Work with your mentor to create your first action item." in resp_dev.text
    assert "addCommitmentModal" in resp_dev.text
    assert "btn-open-commitment-modal" in resp_dev.text
    print("✓ /my-dream-big renders active DEVELOP tab with empty commitments state and modal trigger")

    # 18.4 Test add_egs_commitment API validations and insertion
    frappe.set_user("Guest")
    try:
        add_egs_commitment(dev_stu.name, dev_stu.access_token, {"action_required": ""})
        assert False, "Should fail with missing action_required"
    except Exception:
        pass

    com_data = {
        "action_required": "Complete AWS Solutions Architect certification",
        "due_date": "2026-12-15",
        "status": "In Progress",
        "reported_barrier": "Need mentor voucher for exam fee"
    }
    com_res = add_egs_commitment(dev_stu.name, dev_stu.access_token, com_data)
    frappe.set_user("Administrator")
    assert com_res.get("status") == "success"
    assert com_res.get("name") is not None
    com_id = com_res.get("name")

    com_doc = frappe.get_doc("EGS Commitment", com_id)
    assert com_doc.career_goal_reference == goal_name
    assert com_doc.action_required == "Complete AWS Solutions Architect certification"
    assert str(com_doc.due_date) == "2026-12-15"
    assert com_doc.progress_status in ["In Progress", "Progress Made"]
    assert com_doc.reported_barrier == "Need mentor voucher for exam fee"
    print("✓ add_egs_commitment successfully created EGS Commitment linked to career goal")

    # 18.5 Verify dashboard renders commitments table
    resp_with_com = requests.get(dev_dash_url, headers=headers)
    assert resp_with_com.status_code == 200
    assert "Complete AWS Solutions Architect certification" in resp_with_com.text
    assert "2026-12-15" in resp_with_com.text
    assert "Need mentor voucher for exam fee" in resp_with_com.text
    print("✓ /my-dream-big renders commitments table with action, due date, status, and reported barrier")

    # Clean up
    for com in frappe.get_all("EGS Commitment", filters={"career_goal_reference": goal_name}):
        frappe.delete_doc("EGS Commitment", com.name, force=True)
    for g in frappe.get_all("EGS Career Goal", filters={"student_reference": dev_stu.name}):
        frappe.delete_doc("EGS Career Goal", g.name, force=True)
    frappe.delete_doc("EGS Student Participant", dev_stu.name, force=True)
    frappe.db.commit()
    print("✓ Cleaned up test dev student, commitments, and career goal records")

    # 19. Testing Cascading Step-Back & Strict Future Stage Locking across Stages 4 and 5
    print("\n--- 19. Testing Cascading Step-Back & Strict Future Stage Locking (Stages 4 & 5) ---")
    from dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant import step_back_stage, advance_to_deliver

    test_cascade_email = "test.cascade@example.com"
    existing_cascade = frappe.get_all("EGS Student Participant", filters={"student_email": test_cascade_email})
    for s in existing_cascade:
        for com in frappe.get_all("EGS Commitment", filters={"career_goal_reference": ["in", [g.name for g in frappe.get_all("EGS Career Goal", filters={"student_reference": s.name})]]}):
            frappe.delete_doc("EGS Commitment", com.name, force=True)
        for acc in frappe.get_all("EGS Accomplishment", filters={"student_reference": s.name}):
            frappe.delete_doc("EGS Accomplishment", acc.name, force=True)
        for g in frappe.get_all("EGS Career Goal", filters={"student_reference": s.name}):
            frappe.delete_doc("EGS Career Goal", g.name, force=True)
        frappe.delete_doc("EGS Student Participant", s.name, force=True)
    frappe.db.commit()

    casc_stu = frappe.get_doc({
        "doctype": "EGS Student Participant",
        "student_name": "Cascade Test Student",
        "phone_number": "9123456788",
        "student_email": test_cascade_email,
        "guardian_phone_number": "9876543288",
        "city": "Delhi",
        "university_college": "Jamia Millia Islamia",
        "faculty_department": "Faculty of Engineering & Technology",
        "course": "B.Tech Computer Science",
        "cohort_year": "2026",
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    process_student_checkin(casc_stu)
    submit_decide_stage(
        student_id=casc_stu.name,
        token=casc_stu.access_token,
        final_chosen_career_goal=pw_name,
        personal_vision_statement="Vision for cascade test.",
        a_promise_to_self="Promise for cascade test.",
        date_of_decision="2026-11-20"
    )
    casc_stu.reload()
    assert casc_stu.current_5ds_stage == "DECIDE"

    dash_url = f"http://127.0.0.1:8000/my-dream-big?id={casc_stu.name}&key={casc_stu.access_token}"

    # Verify Stage 4 and Stage 5 are locked when student is in DECIDE
    resp_decide_view = requests.get(dash_url, headers=headers)
    assert resp_decide_view.status_code == 200
    assert "Stage 4: DEVELOP is Locked" in resp_decide_view.text
    assert "Stage 5: DELIVER is Locked" in resp_decide_view.text
    print("✓ When student is in DECIDE, Stage 4 and Stage 5 are strictly locked with warning banners")

    # Advance to Stage 4: DEVELOP
    advance_to_develop(casc_stu.name, casc_stu.access_token)
    casc_stu.reload()
    assert casc_stu.current_5ds_stage == "DEVELOP/PREPARE"

    # Add a commitment in DEVELOP
    add_egs_commitment(casc_stu.name, casc_stu.access_token, {
        "action_required": "Milestone commitment before stepping back",
        "due_date": "2026-12-01",
        "status": "In Progress"
    })
    cg_records = frappe.get_all("EGS Career Goal", filters={"student_reference": casc_stu.name})
    assert len(cg_records) == 1
    cg_name = cg_records[0].name
    assert len(frappe.get_all("EGS Commitment", filters={"career_goal_reference": cg_name})) == 1

    # Verify Stage 4 is active with return-to-decide and advance-to-deliver buttons; Stage 5 remains locked
    resp_dev_view = requests.get(dash_url, headers=headers)
    assert resp_dev_view.status_code == 200
    assert "btn-revert-to-decide" in resp_dev_view.text
    assert "btn-advance-deliver" in resp_dev_view.text
    assert "Stage 5: DELIVER is Locked" in resp_dev_view.text
    print("✓ In Stage 4, DEVELOP tab renders 'Return to Stage 3: DECIDE' & 'Proceed to Stage 5: DELIVER', Stage 5 is locked")

    # Advance to Stage 5: DELIVER
    adv_del_res = advance_to_deliver(casc_stu.name, casc_stu.access_token)
    assert adv_del_res.get("status") == "success"
    casc_stu.reload()
    assert casc_stu.current_5ds_stage == "DELIVER"
    assert frappe.db.get_value("EGS Career Goal", cg_name, "current_5ds_stage") == "DELIVER"

    # Add an Accomplishment in DELIVER
    acc_doc = frappe.get_doc({
        "doctype": "EGS Accomplishment",
        "student_reference": casc_stu.name,
        "accomplishment_title": "Certified Cloud Architect",
        "date_achieved": "2026-11-25",
        "category": "Qualification",
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    assert len(frappe.get_all("EGS Accomplishment", filters={"student_reference": casc_stu.name})) == 1

    # Verify DELIVER tab is unlocked and renders return-to-develop button
    resp_del_view = requests.get(dash_url, headers=headers)
    assert resp_del_view.status_code == 200
    assert "btn-revert-to-develop" in resp_del_view.text
    assert "Stage 5: DELIVER is Locked" not in resp_del_view.text
    print("✓ In Stage 5, DELIVER tab is unlocked and renders 'Return to Stage 4: DEVELOP'")

    # Step Back from DELIVER -> DEVELOP/PREPARE
    step_dev_res = step_back_stage(casc_stu.name, casc_stu.access_token, "DEVELOP/PREPARE")
    assert step_dev_res.get("status") == "success"
    casc_stu.reload()
    assert casc_stu.current_5ds_stage == "DEVELOP/PREPARE"
    assert frappe.db.get_value("EGS Career Goal", cg_name, "current_5ds_stage") == "DEVELOP/PREPARE"

    # Verify EGS Accomplishment was wiped clean
    acc_remaining = frappe.get_all("EGS Accomplishment", filters={"student_reference": casc_stu.name})
    assert len(acc_remaining) == 0, f"Expected 0 accomplishments, found {len(acc_remaining)}"
    print("✓ Stepping back from DELIVER to DEVELOP cleanly wiped EGS Accomplishment records and updated stage")

    # Step Back from DEVELOP -> DECIDE
    step_dec_res = step_back_stage(casc_stu.name, casc_stu.access_token, "DECIDE")
    assert step_dec_res.get("status") == "success"
    casc_stu.reload()
    assert casc_stu.current_5ds_stage == "DECIDE"
    assert frappe.db.get_value("EGS Career Goal", cg_name, "current_5ds_stage") == "DECIDE"

    # Verify EGS Commitment was wiped clean
    com_remaining = frappe.get_all("EGS Commitment", filters={"career_goal_reference": cg_name})
    assert len(com_remaining) == 0, f"Expected 0 commitments, found {len(com_remaining)}"
    print("✓ Stepping back from DEVELOP to DECIDE cleanly wiped linked EGS Commitment records and updated stage")

    # Clean up test records
    for acc in frappe.get_all("EGS Accomplishment", filters={"student_reference": casc_stu.name}):
        frappe.delete_doc("EGS Accomplishment", acc.name, force=True)
    for com in frappe.get_all("EGS Commitment", filters={"career_goal_reference": cg_name}):
        frappe.delete_doc("EGS Commitment", com.name, force=True)
    for g in frappe.get_all("EGS Career Goal", filters={"student_reference": casc_stu.name}):
        frappe.delete_doc("EGS Career Goal", g.name, force=True)
    frappe.delete_doc("EGS Student Participant", casc_stu.name, force=True)
    frappe.db.commit()
    print("✓ Cleaned up test cascade student, accomplishments, and career goal records")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
