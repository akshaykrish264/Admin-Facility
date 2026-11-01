# Copyright (c) 2026, facility and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class FlightTicketBooking(Document):
	def validate(self):
		if self.from_location == self.to_location:
			frappe.throw(_("From and To location cannot be the same"))

		if self.way == "One Way":
			self.return_date = None
		elif self.return_date and self.return_date < self.departure_date:
			frappe.throw(_("Return Date cannot be before Departure Date"))

	def before_submit(self):
		if not self.passengers:
			frappe.throw(_("Add at least one passenger before submitting"))
