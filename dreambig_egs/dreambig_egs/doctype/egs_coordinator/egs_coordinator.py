from frappe.model.document import Document

class EGSCoordinator(Document):
	def validate(self):
		if self.coordinator_name and not self.full_name:
			self.full_name = self.coordinator_name
