# Copyright (c) 2026, facility and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class GSMBillUpload(Document):
	def validate(self):
		# One upload = one billing month; rows always take the bill's month/year
		# (the row Selects otherwise default to January / 2023)
		for row in self.bill_details:
			row.month = self.month
			row.year = self.year
