import frappe

PWA_HEAD_HTML = """
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#1e3a8a">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="DREAM BIG">
<link rel="apple-touch-icon" href="/assets/dreambig_egs/icons/icon-192.png">
<link rel="apple-touch-icon" sizes="512x512" href="/assets/dreambig_egs/icons/icon-512.png">
"""

def update_website_context(context):
	"""
	Injects PWA metadata, manifest link, and touch icons into website context head_html.
	"""
	existing = context.get("head_html") or ""
	if "manifest.json" not in existing:
		context["head_html"] = existing + "\n" + PWA_HEAD_HTML
	return context
