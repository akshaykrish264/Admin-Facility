import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

APPROVER_ROLE = "Facility Approver"

# Booking / request doctypes that go through Draft -> Pending Approval -> Approved / Rejected
APPROVAL_DOCTYPES = (
	"Accommodation Request",
	"Accommodation Booking",
	"Flight Ticket Booking",
	"GSM Request",
	"Insurance Card Request",
	"Medical Treatment Request",
	"Medical Treatment Invoice Entry",
	"Transportation Request",
)

# state, doc_status, role allowed to edit while in that state
WORKFLOW_STATES = (
	("Draft", "0", "All"),
	("Pending Approval", "0", APPROVER_ROLE),
	("Approved", "1", APPROVER_ROLE),
	("Rejected", "0", APPROVER_ROLE),
	("Cancelled", "2", APPROVER_ROLE),
)

# state, action, next_state, allowed role, allow_self_approval
WORKFLOW_TRANSITIONS = (
	("Draft", "Submit for Approval", "Pending Approval", "All", 1),
	("Pending Approval", "Approve", "Approved", APPROVER_ROLE, 0),
	("Pending Approval", "Reject", "Rejected", APPROVER_ROLE, 0),
	("Approved", "Cancel", "Cancelled", APPROVER_ROLE, 1),
)

STATE_STYLES = {
	"Draft": "",
	"Pending Approval": "Warning",
	"Approved": "Success",
	"Rejected": "Danger",
	"Cancelled": "Inverse",
}


def after_install():
	after_migrate()


def after_migrate():
	setup_approval_workflows()
	setup_employee_insurance_tab()


def setup_approval_workflows():
	"""Creates the approve / reject workflow for each booking and request doctype.
	Existing workflows are left untouched so changes made from the UI survive migrate."""
	if not frappe.db.exists("Role", APPROVER_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": APPROVER_ROLE, "desk_access": 1}).insert(
			ignore_permissions=True
		)

	for state, _, _ in WORKFLOW_STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc(
				{"doctype": "Workflow State", "workflow_state_name": state, "style": STATE_STYLES[state]}
			).insert(ignore_permissions=True)

	for _, action, _, _, _ in WORKFLOW_TRANSITIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)

	for doctype in APPROVAL_DOCTYPES:
		workflow_name = f"{doctype} Approval"
		if frappe.db.exists("Workflow", workflow_name):
			continue

		frappe.get_doc(
			{
				"doctype": "Workflow",
				"workflow_name": workflow_name,
				"document_type": doctype,
				"workflow_state_field": "status",
				"is_active": 1,
				"send_email_alert": 0,
				"states": [
					{"state": state, "doc_status": doc_status, "allow_edit": role}
					for state, doc_status, role in WORKFLOW_STATES
				],
				"transitions": [
					{
						"state": state,
						"action": action,
						"next_state": next_state,
						"allowed": role,
						"allow_self_approval": self_approval,
					}
					for state, action, next_state, role, self_approval in WORKFLOW_TRANSITIONS
				],
			}
		).insert(ignore_permissions=True)


def setup_employee_insurance_tab():
	"""Adds an Insurance tab to Employee listing members from approved Insurance Card Requests
	(rendered by public/js/employee.js)."""
	own_fields = ("insurance_tab", "insurance_details_section", "insurance_details_html")
	last_field = [f.fieldname for f in frappe.get_meta("Employee").fields if f.fieldname not in own_fields][-1]

	create_custom_fields(
		{
			"Employee": [
				{
					"fieldname": "insurance_tab",
					"fieldtype": "Tab Break",
					"label": "Insurance",
					"insert_after": last_field,
				},
				{
					"fieldname": "insurance_details_section",
					"fieldtype": "Section Break",
					"label": "Insurance Details",
					"insert_after": "insurance_tab",
				},
				{
					"fieldname": "insurance_details_html",
					"fieldtype": "HTML",
					"insert_after": "insurance_details_section",
				},
			]
		}
	)
