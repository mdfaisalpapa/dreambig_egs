import frappe

def get_context(context):
	context.no_cache = 1
	student_id = frappe.form_dict.get("id")
	access_key = frappe.form_dict.get("key")
	if student_id and access_key:
		student = frappe.db.get_value(
			"EGS Student Participant",
			student_id,
			["name", "access_token"],
			as_dict=True,
		)
		if student and student.access_token == access_key:
			frappe.form_dict.name = student_id
			try:
				context.doc = frappe.get_doc("EGS Student Participant", student_id)
			except Exception:
				pass
