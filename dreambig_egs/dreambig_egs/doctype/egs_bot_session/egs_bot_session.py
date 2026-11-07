# Copyright (c) 2026, Dream Big and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.model.document import Document


class EGSBotSession(Document):
	def get_context_data(self) -> dict:
		if not self.session_data:
			return {}
		try:
			return json.loads(self.session_data)
		except Exception:
			return {}

	def set_context_data(self, data: dict):
		self.session_data = json.dumps(data or {})

	def update_context(self, updates: dict):
		curr = self.get_context_data()
		curr.update(updates)
		self.set_context_data(curr)

	def clear_context(self):
		self.session_data = "{}"
