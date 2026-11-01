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
