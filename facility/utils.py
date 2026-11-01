import frappe

# Status a document takes on each docstatus: 0 = saved, 1 = submitted, 2 = cancelled
SUBMIT_STATUS = {"Parcel": "Pending For Receival"}


def set_status(doc, method=None):
    """Keeps the read-only `status` field in step with docstatus.
    Skipped when an active Workflow drives the doctype, so a workflow that
    uses `status` as its state field is not overwritten."""
    if frappe.get_cached_value("Workflow", {"document_type": doc.doctype, "is_active": 1}, "name"):
        return

    if doc.docstatus == 0:
        status = "Draft"
    elif doc.docstatus == 1:
        status = SUBMIT_STATUS.get(doc.doctype, "Approved")
    else:
        status = "Cancelled"

    if doc.status == status:
        return
    if doc.docstatus == 0:
        doc.status = status
    else:
        doc.db_set("status", status)


# Workflow state -> field recording the user who moved the document into it
WORKFLOW_USER_FIELDS = {
    "Pending Approval": "sent_for_approval_by",
    "Approved": "approved_by",
    "Rejected": "rejected_by",
}


def set_workflow_users(doc, method=None):
    """Fills the Workflow Approval Details section with the user who
    performed each step. Runs on validate, before_submit and before_cancel."""
    if not doc.meta.has_field("drafted_by"):
        return

    user = frappe.session.user
    if not doc.drafted_by:
        doc.drafted_by = doc.owner or user

    if method == "before_cancel":
        doc.cancelled_by = user
    elif method == "before_submit":
        # Covers submit without an active workflow, where status is set after submit
        doc.approved_by = user
    elif doc.has_value_changed("status"):
        fieldname = WORKFLOW_USER_FIELDS.get(doc.status)
        if fieldname:
            doc.set(fieldname, user)
