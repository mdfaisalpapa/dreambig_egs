import frappe
from frappe import _

def get_context(context):
	context.no_cache = 1
	context.show_sidebar = False
	context.title = _("Event Check-In | DREAM BIG")

	student_id = frappe.form_dict.get("id")
	token = frappe.form_dict.get("key")
	qr_code = frappe.form_dict.get("qr") or frappe.form_dict.get("code")

	context.student_id = student_id or ""
	context.token = token or ""
	context.auto_checkin = False

	if student_id and token:
		try:
			from dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant import event_checkin
			res = event_checkin(student_id, token)
			st = frappe.db.get_value("EGS Student Participant", student_id, ["student_name"], as_dict=True)
			context.auto_checkin = True
			context.student_name = st.student_name if st else "Student"
			context.redirect_url = f"/my-dream-big?id={student_id}&key={token}"
		except Exception as e:
			context.auto_checkin = False
			context.error_message = str(e)
