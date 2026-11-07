import frappe
import requests
from dreambig_egs.api import (
    revert_5ds_stage,
    submit_decide_stage,
    advance_to_develop,
    step_back_stage,
    advance_to_deliver,
)

def simulate_student_flow():
    student_id = "STU-26-0092"
    if not frappe.db.exists("EGS Student Participant", student_id):
        print(f"Student {student_id} not found in database!")
        return

    doc = frappe.get_doc("EGS Student Participant", student_id)
    token = doc.access_token
    print(f"Testing Student {doc.name} ({doc.student_name})")

    headers = {"Host": "egs.localhost"}
    url = f"http://127.0.0.1:8000/my-dream-big?id={student_id}&key={token}"

    # Step 1: Revert to DISCOVER
    print("\n--- 1. Revert to DISCOVER ---")
    rev = revert_5ds_stage(student_id=student_id, reason="Cycle test revert", token=token)
    print("revert_5ds_stage:", rev)

    doc.reload()
    assert doc.current_5ds_stage == "DISCOVER"
    assert doc.final_chosen_career_goal is None
    goals = frappe.get_all("EGS Career Goal", filters={"student_reference": student_id})
    assert len(goals) == 0, f"Expected 0 goals, got {len(goals)}"

    # Check HTTP response for DISCOVER state
    r1 = requests.get(url, headers=headers)
    assert r1.status_code == 200
    assert "Pending Commitment" in r1.text
    assert "Commit to DECIDE Stage" in r1.text
    assert "Stage 2 (DISCOVER) is Locked" not in r1.text
    assert "Stage 3: DECIDE is Locked" in r1.text
    assert "btn-open-decide-modal" in r1.text
    print("✓ HTTP view reflects live DISCOVER stage, unlocked Exercise 2, relocated 'Commit to DECIDE Stage' button, and locked Stage 3 banner")

    # Step 2: Re-commit to DECIDE
    print("\n--- 2. Re-commit to DECIDE ---")
    pathways = frappe.get_all("EGS Career Pathway", limit=1)
    chosen_pw = pathways[0].name
    dec = submit_decide_stage(
        student_id=student_id,
        token=token,
        final_chosen_career_goal=chosen_pw,
        personal_vision_statement="Vision for cyclical test",
        a_promise_to_self="Promise for cyclical test",
        date_of_decision="2026-11-25"
    )
    print("submit_decide_stage:", dec)

    doc.reload()
    assert doc.current_5ds_stage == "DECIDE"
    assert doc.final_chosen_career_goal == chosen_pw
    goals = frappe.get_all("EGS Career Goal", filters={"student_reference": student_id}, fields=["name", "current_5ds_stage"])
    assert len(goals) == 1
    assert goals[0].current_5ds_stage == "DECIDE"

    # Check HTTP response for DECIDE state
    r2 = requests.get(url, headers=headers)
    assert r2.status_code == 200
    assert "✓ Stage Committed" in r2.text
    assert "Stage 3: DECIDE is Locked" not in r2.text
    assert "Update Promise to Self" in r2.text
    assert "btn-update-decide-modal" in r2.text
    assert "Proceed to Stage 4: DEVELOP" in r2.text
    print("✓ HTTP view reflects live DECIDE stage with unlocked actions, 'Update Promise to Self', and 'Proceed to Stage 4: DEVELOP'")

    # Step 3: Advance to DEVELOP
    print("\n--- 3. Advance to DEVELOP ---")
    adv = advance_to_develop(student_id=student_id, token=token)
    print("advance_to_develop:", adv)

    doc.reload()
    assert doc.current_5ds_stage == "DEVELOP/PREPARE"
    goals = frappe.get_all("EGS Career Goal", filters={"student_reference": student_id}, fields=["name", "current_5ds_stage"])
    assert len(goals) == 1
    assert goals[0].current_5ds_stage == "DEVELOP/PREPARE"

    # Step 4: Rapid Front-and-Back Cycling (Testing Timestamp Mismatch Resilience)
    print("\n--- 4. Rapid Front-and-Back Cycling (DELIVER <-> DEVELOP <-> DECIDE <-> DISCOVER) ---")
    
    # 4.1 Advance to DELIVER
    adv_del = advance_to_deliver(student_id=student_id, token=token)
    assert adv_del.get("current_5ds_stage") == "DELIVER"
    print("✓ Advanced to DELIVER")

    # 4.2 Step back to DEVELOP
    sb_dev = step_back_stage(student_id=student_id, token=token, target_stage="DEVELOP/PREPARE")
    assert sb_dev.get("current_5ds_stage") == "DEVELOP/PREPARE"
    print("✓ Stepped back to DEVELOP/PREPARE")

    # 4.3 Advance back to DELIVER immediately
    adv_del2 = advance_to_deliver(student_id=student_id, token=token)
    assert adv_del2.get("current_5ds_stage") == "DELIVER"
    print("✓ Rapidly re-advanced to DELIVER")

    # 4.4 Step back to DEVELOP
    sb_dev2 = step_back_stage(student_id=student_id, token=token, target_stage="DEVELOP/PREPARE")
    assert sb_dev2.get("current_5ds_stage") == "DEVELOP/PREPARE"
    print("✓ Stepped back to DEVELOP/PREPARE")

    # 4.5 Step back to DECIDE
    sb_dec = step_back_stage(student_id=student_id, token=token, target_stage="DECIDE")
    assert sb_dec.get("current_5ds_stage") == "DECIDE"
    print("✓ Stepped back to DECIDE")

    # 4.6 Re-advance to DEVELOP
    adv_dev2 = advance_to_develop(student_id=student_id, token=token)
    assert adv_dev2.get("current_5ds_stage") == "DEVELOP/PREPARE"
    print("✓ Re-advanced to DEVELOP")

    # 4.7 Re-step back to DECIDE
    sb_dec2 = step_back_stage(student_id=student_id, token=token, target_stage="DECIDE")
    assert sb_dec2.get("current_5ds_stage") == "DECIDE"
    print("✓ Re-stepped back to DECIDE")

    # 4.8 Revert to DISCOVER
    rev2 = revert_5ds_stage(student_id=student_id, reason="Rapid cycling back to discovery", token=token)
    assert rev2.get("current_5ds_stage") == "DISCOVER"
    print("✓ Reverted back to DISCOVER")

    # 4.9 Re-commit to DECIDE
    dec2 = submit_decide_stage(
        student_id=student_id,
        token=token,
        final_chosen_career_goal=chosen_pw,
        personal_vision_statement="Final vision after rapid cycle",
        a_promise_to_self="Final promise",
        date_of_decision="2026-11-25"
    )
    assert dec2.get("current_5ds_stage") == "DECIDE"
    print("✓ Re-committed to DECIDE")

    # 4.10 Advance to DEVELOP
    adv_final = advance_to_develop(student_id=student_id, token=token)
    assert adv_final.get("current_5ds_stage") == "DEVELOP/PREPARE"
    print("✓ Final advance to DEVELOP")

    print("\nSUCCESS: STU-26-0092 passed rapid front-and-back progression with zero TimestampMismatchError!")
