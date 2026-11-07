import frappe
from frappe import _

def get_context(context):
	context.no_cache = 1
	context.show_sidebar = False
	context.title = _("Event Check-In | DREAM BIG")

	student_id = frappe.form_dict.get("id")
	token = frappe.form_dict.get("key")

	context.student_id = student_id or ""
	context.token = token or ""
	context.auto_checkin = False

	if student_id and token:
		students = frappe.get_all(
			"EGS Student Participant",
			filters={"name": student_id, "access_token": token},
			fields=["name", "student_name", "event_status"],
		)
		if students:
			st = students[0]
			if st.event_status != "Checked-In":
				frappe.db.set_value("EGS Student Participant", st.name, "event_status", "Checked-In")
				frappe.db.commit()
			context.auto_checkin = True
			context.student_name = st.student_name
			context.redirect_url = f"/my-dream-big?id={student_id}&key={token}"
