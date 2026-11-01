# Copyright (c) 2026, facility and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime


class ContractDetailRegistration(Document):
	def validate(self):
		if (
			self.contract_period_from
			and self.contract_period_to
			and get_datetime(self.contract_period_to) <= get_datetime(self.contract_period_from)
		):
			frappe.throw(_("Contract Period To must be after Contract Period From"))
