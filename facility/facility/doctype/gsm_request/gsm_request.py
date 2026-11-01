# Copyright (c) 2026, facility and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# Request types that change an existing GSM Number, and the GSM Number
# field + request field each one applies on approval
LIMIT_CHANGES = {
	"Increase Data limit": ("data_limit", "new_data_limit"),
	"Decrease Data limit": ("data_limit", "new_data_limit"),
	"Increase Call limit": ("credit_limit", "new_credit_limit"),
	"Decrease Call limit": ("credit_limit", "new_credit_limit"),
	"Request for GSM Limit": ("credit_limit", "new_credit_limit"),
}

NEEDS_GSM_NO = set(LIMIT_CHANGES) | {"Cancel SIM Card", "Re Issue SIM Card"}


class GSMRequest(Document):
	def validate(self):
		if self.request_type in NEEDS_GSM_NO and not self.gsm_no:
			frappe.throw(_("GSM No is required for {0}").format(self.request_type))

		if self.gsm_no:
			owner = frappe.db.get_value("GSM Number", self.gsm_no, "employee")
			if owner != self.employee:
				frappe.throw(_("GSM No {0} does not belong to employee {1}").format(self.gsm_no, self.employee))

		if self.request_type in LIMIT_CHANGES:
			target, source = LIMIT_CHANGES[self.request_type]
			new_value = self.get(source)
			if not new_value:
				frappe.throw(_("{0} is required for {1}").format(self.meta.get_label(source), self.request_type))

			current = frappe.db.get_value("GSM Number", self.gsm_no, target) or 0
			if self.request_type.startswith("Increase") and new_value <= current:
				frappe.throw(_("New limit must be higher than the current limit {0}").format(current))
			if self.request_type.startswith("Decrease") and new_value >= current:
				frappe.throw(_("New limit must be lower than the current limit {0}").format(current))

	def on_submit(self):
		# Approved limit change is applied to the GSM Number master
		if self.request_type in LIMIT_CHANGES:
			target, source = LIMIT_CHANGES[self.request_type]
			frappe.db.set_value("GSM Number", self.gsm_no, target, self.get(source))
