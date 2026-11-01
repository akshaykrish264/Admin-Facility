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
		"""Adds approved (submitted) treatment requests in the From/To date range
		that are not already in this table or in another non-cancelled invoice.
		Runs server side: listing the Medical Invoice Detail child table from the
		browser is not permitted."""
		if not self.from_date or not self.to_date:
			frappe.throw(_("Please enter From Date and To Date to fetch Medical Requests."), title=_("Required"))
		if not self.item_code:
			frappe.throw(_("Please select an Item Code first."), title=_("Required"))

		requests = frappe.get_all(
			"Medical Treatment Request",
			filters={"docstatus": 1, "medical_date": ["between", [self.from_date, self.to_date]]},
			fields=["name", "employee", "employee_name", "clinic", "medical_date"],
			order_by="medical_date",
		)
		if not requests:
			frappe.msgprint(
				_("No Approved Medical Treatment Requests found for the selected date range."),
				title=_("No Records"),
				indicator="orange",
			)
			return {"added": 0, "skipped_existing": 0, "skipped_invoiced": 0}

		invoiced = set(
			frappe.get_all(
				"Medical Invoice Detail",
				filters={
					"parenttype": self.doctype,
					"docstatus": ["<", 2],
					"parent": ["!=", self.name or ""],
					"req_no": ["in", [r.name for r in requests]],
				},
				pluck="req_no",
			)
		)
		existing = {row.req_no for row in self.medical_requests}

		counts = {"added": 0, "skipped_existing": 0, "skipped_invoiced": 0}
		for req in requests:
			if req.name in existing:
				counts["skipped_existing"] += 1
				continue
			if req.name in invoiced:
				counts["skipped_invoiced"] += 1
				continue
			self.append(
				"medical_requests",
				{
					"req_no": req.name,
					"emp_no": req.employee,
					"emp_name": req.employee_name,
					"clinic": req.clinic,
					"treatment_date": req.medical_date,
					"bill_amount": 0,
					"ref_date": self.ref_date,
				},
			)
			existing.add(req.name)
			counts["added"] += 1

		self.total = sum(flt(row.bill_amount) for row in self.medical_requests)
		return counts


def get_existing_field(doctype, fieldname):
	"""Fieldname as it exists on the site: custom fields added from the UI get a `custom_` prefix."""
	meta = frappe.get_meta(doctype)
	for name in (fieldname, f"custom_{fieldname}"):
		if meta.has_field(name):
			return name
	frappe.throw(
		_("{0} has no field {1}. Add it as a Custom Field to filter this list.").format(
			_(doctype), frappe.bold(fieldname)
		)
	)


def search_with_filters(doctype, txt, searchfield, start, page_len, filters, title_field):
	"""Link search run server side, so filtering on a custom field does not need
	field-level read permission. The user still needs access to the doctype itself."""
	if not frappe.has_permission(doctype, "select") and not frappe.has_permission(doctype, "read"):
		frappe.throw(_("Not permitted to read {0}").format(_(doctype)), frappe.PermissionError)

	return frappe.get_all(
		doctype,
		filters=filters,
		or_filters={"name": ["like", f"%{txt}%"], title_field: ["like", f"%{txt}%"]},
		fields=["name", title_field],
		order_by="name",
		start=start,
		page_length=page_len,
		as_list=True,
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def medical_item_query(doctype, txt, searchfield, start, page_len, filters):
	"""Items in group Medical Services with item category Medical."""
	return search_with_filters(
		"Item", txt, searchfield, start, page_len,
		{"item_group": "Medical Services", get_existing_field("Item", "item_category"): "Medical", "disabled": 0},
		"item_name",
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def clinic_supplier_query(doctype, txt, searchfield, start, page_len, filters):
	"""Suppliers flagged as clinics."""
	return search_with_filters(
		"Supplier", txt, searchfield, start, page_len,
		{get_existing_field("Supplier", "is_clinic"): 1, "disabled": 0},
		"supplier_name",
	)
