# Copyright (c) 2026, facility and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Parcel(Document):
	def validate(self):
		if self.from_location == self.to_location:
			frappe.throw(_("From and To location cannot be the same"))

	@frappe.whitelist()
	def mark_received(self):
		self._set_receival_status("Received")

	@frappe.whitelist()
	def mark_rejected(self):
		self._set_receival_status("Rejected")

	def _set_receival_status(self, status):
		self.check_permission("submit")
		if self.docstatus != 1 or self.status != "Pending For Receival":
			frappe.throw(_("Only a submitted parcel pending receival can be marked {0}").format(status))
		self.db_set("status", status)
