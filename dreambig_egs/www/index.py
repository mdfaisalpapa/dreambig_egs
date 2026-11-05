# Copyright (c) 2026, Mohammed Faisal and contributors
# For license information, please see license.txt

import frappe

def get_context(context):
	context.no_cache = 1
	context.title = "EGS Portal Home"
	context.show_sidebar = False
