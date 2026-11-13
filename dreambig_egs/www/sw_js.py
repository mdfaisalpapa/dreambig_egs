import frappe

def get_context(context):
	sw_path = frappe.get_app_path("dreambig_egs", "public", "sw.js")
	with open(sw_path, "r", encoding="utf-8") as f:
		content = f.read()

	context.content = content
	frappe.response["headers"] = {
		"Content-Type": "text/javascript; charset=utf-8",
		"Service-Worker-Allowed": "/",
	}
