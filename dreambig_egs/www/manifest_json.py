import frappe

def get_context(context):
	manifest_path = frappe.get_app_path("dreambig_egs", "public", "manifest.json")
	with open(manifest_path, "r", encoding="utf-8") as f:
		content = f.read()

	context.content = content
	frappe.response["headers"] = {"Content-Type": "application/manifest+json; charset=utf-8"}
