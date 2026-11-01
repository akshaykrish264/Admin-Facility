# Copyright (c) 2026, facility and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime


class HallBookingRequest(Document):
	def validate(self):
		start, end = self.get("from"), self.get("to")
		if get_datetime(end) <= get_datetime(start):
			frappe.throw(_("To must be after From"))
		self.validate_hall_clash(start, end)

	def validate_hall_clash(self, start, end):
		# Draft bookings are ignored; only submitted bookings hold the hall
		clash = frappe.db.get_value(
			"Hall Booking Request",
			{
				"hall_name": self.hall_name,
				"docstatus": 1,
				"name": ["!=", self.name or ""],
				"from": ["<", end],
				"to": [">", start],
			},
			["name", "from", "to"],
			as_dict=True,
		)
		if clash:
			frappe.throw(
				_("{0} is already booked from {1} to {2} in {3}").format(
					self.hall_name, clash["from"], clash["to"], clash.name
				)
			)
