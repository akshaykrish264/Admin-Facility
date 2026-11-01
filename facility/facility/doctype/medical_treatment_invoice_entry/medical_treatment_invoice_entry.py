# Copyright (c) 2026, facility and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class MedicalTreatmentInvoiceEntry(Document):
	def validate(self):
		if self.from_date and self.to_date and self.to_date < self.from_date:
			frappe.throw(_("To Date must be on or after From Date"))
		self.validate_already_invoiced()
		self.total = sum(flt(row.bill_amount) for row in self.medical_requests)

	def validate_already_invoiced(self):
		req_nos = [row.req_no for row in self.medical_requests if row.req_no]
		if len(req_nos) != len(set(req_nos)):
			frappe.throw(_("The same Medical Treatment Request is listed more than once"))
		if not req_nos:
			return

		invoiced = frappe.get_all(
			"Medical Invoice Detail",
			filters={
				"parenttype": self.doctype,
				"req_no": ["in", req_nos],
				"docstatus": 1,
				"parent": ["!=", self.name or ""],
			},
			fields=["req_no", "parent"],
		)
		if invoiced:
			frappe.throw(
				_("Already invoiced: {0}").format(
					", ".join(f"{d.req_no} ({d.parent})" for d in invoiced)
				)
			)

	@frappe.whitelist()
	def get_medical_requests(self):
		"""Adds submitted treatment requests for clinics billed by this
		supplier, in the From/To date range, that are not yet invoiced."""
		if not self.supplier:
			frappe.throw(_("Select a Supplier first"))

		clinics = frappe.get_all("Clinic Master", filters={"supplier": self.supplier}, pluck="name")
		if not clinics:
			frappe.throw(_("No Clinic Master is linked to supplier {0}").format(self.supplier))

		filters = {"docstatus": 1, "clinic": ["in", clinics]}
		if self.from_date and self.to_date:
			filters["medical_date"] = ["between", [self.from_date, self.to_date]]

		invoiced = set(
			frappe.get_all(
				"Medical Invoice Detail",
				filters={"parenttype": self.doctype, "docstatus": 1},
				pluck="req_no",
			)
		)
		existing = {row.req_no for row in self.medical_requests}

		added = 0
		for req in frappe.get_all(
			"Medical Treatment Request",
			filters=filters,
			fields=["name", "employee", "employee_name", "clinic", "medical_date"],
			order_by="medical_date",
		):
			if req.name in invoiced or req.name in existing:
				continue
			self.append(
				"medical_requests",
				{
					"req_no": req.name,
					"emp_no": req.employee,
					"emp_name": req.employee_name,
					"clinic": req.clinic,
					"treatment_date": req.medical_date,
				},
			)
			added += 1

		if not added:
			frappe.msgprint(_("No pending treatment requests found"))
