# Copyright (c) 2026, facility and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TransportationRequest(Document):
	def validate(self):
		if self.from_location == self.to_location:
			frappe.throw(_("From and To location cannot be the same"))

	def before_submit(self):
		if not self.passengers:
			frappe.throw(_("Add at least one passenger before submitting"))
