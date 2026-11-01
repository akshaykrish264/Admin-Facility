# Copyright (c) 2026, facility and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class InsuranceCardRequest(Document):
	pass


@frappe.whitelist()
def get_employee_insurance(employee):
	"""Members of the employee's approved Insurance Card Requests, shown on the Employee Insurance tab."""
	frappe.has_permission("Employee", doc=employee, throw=True)

	req = frappe.qb.DocType("Insurance Card Request")
	member = frappe.qb.DocType("Insurance Card Member")
	return (
		frappe.qb.from_(member)
		.join(req)
		.on(member.parent == req.name)
		.select(
			req.name.as_("request"),
			member.relation,
			member.member_name,
			member.category,
			member.dob,
			member.nationality,
			member.issue_date,
			member.cost,
		)
		.where(
			(member.parenttype == "Insurance Card Request")
			& (req.employee == employee)
			& (req.docstatus == 1)
			& (req.status == "Approved")
		)
		.orderby(member.issue_date, order=frappe.qb.desc)
		.orderby(member.idx)
		.run(as_dict=True)
	)
