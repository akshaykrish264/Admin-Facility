import frappe
import re


def normalize_gsm(value):
    """Strip whitespace and non-digit noise so '75757896 ', '757-57896',
    and '75757896' all match the same key."""
    if not value:
        return ""
    return re.sub(r"\D", "", str(value)).strip()


def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {
            "label": "Employee",
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
            "width": 130
        },
        {
            "label": "Employee Name",
            "fieldname": "employee_name",
            "fieldtype": "Data",
            "width": 160
        },
        {
            "label": "GSM No",
            "fieldname": "gsm_no",
            "fieldtype": "Data",
            "width": 130
        },
        {
            "label": "Month",
            "fieldname": "month",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": "Year",
            "fieldname": "year",
            "fieldtype": "Data",
            "width": 80
        },
        {
            "label": "Allowed Credit",
            "fieldname": "credit_limit",
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "label": "Credit Used",
            "fieldname": "credit_used",
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "label": "Credit Balance",
            "fieldname": "credit_balance",
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "label": "Allowed Data (GB)",
            "fieldname": "data_limit",
            "fieldtype": "Float",
            "width": 140
        },
        {
            "label": "Data Used (GB)",
            "fieldname": "data_used",
            "fieldtype": "Float",
            "width": 130
        },
        {
            "label": "Data Balance (GB)",
            "fieldname": "data_balance",
            "fieldtype": "Float",
            "width": 140
        },
        {
            "label": "Name Bundle",
            "fieldname": "name_bundle",
            "fieldtype": "Data",
            "width": 110
        },
        {
            "label": "Status",
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": "GSM Bill",
            "fieldname": "gsm_bill",
            "fieldtype": "Link",
            "options": "GSM Bill Upload",
            "width": 130
        },
    ]


def get_data(filters):
    # ── Build filters for GSM Bill Upload ──
    bill_filters = {}
    if filters.get("month"):
        bill_filters["month"] = filters["month"]
    if filters.get("year"):
        bill_filters["year"] = filters["year"]

    bills = frappe.get_all(
        "GSM Bill Upload",
        filters=bill_filters,
        fields=["name", "month", "year"]
    )

    if not bills:
        return []

    bill_names = [b.name for b in bills]
    bill_meta = {b.name: b for b in bills}

    # ── Pull all child rows for the matched bills in one query ──
    bill_details = frappe.get_all(
        "GSM Bill Detail",
        filters={"parent": ["in", bill_names]},
        fields=["parent", "gsm_no", "credit_used", "data_used", "month", "year"]
    )

    if not bill_details:
        return []

    # ── Pull all GSM Number masters in one query (avoid N+1 lookups) ──
    # Fetching all records rather than filtering by exact gsm_no match,
    # since bill uploads (often via Excel) can have whitespace/format
    # differences that would break an exact DB-level "in" filter.
    gsm_masters = frappe.get_all(
        "GSM Number",
        fields=["name", "gsm_number", "employee", "employee_name",
                "credit_limit", "data_limit", "name_bundle"]
    )
    gsm_master_map = {normalize_gsm(g.gsm_number): g for g in gsm_masters}

    data = []

    for detail in bill_details:
        bill = bill_meta.get(detail.parent)
        gsm_data = gsm_master_map.get(normalize_gsm(detail.gsm_no))

        if gsm_data:
            employee = gsm_data.employee or ""
            employee_name = gsm_data.employee_name or "Unknown"
            credit_limit = gsm_data.credit_limit or 0
            data_limit = gsm_data.data_limit or 0
            name_bundle = gsm_data.name_bundle or ""
        else:
            employee = ""
            employee_name = "Unknown"
            credit_limit = 0
            data_limit = 0
            name_bundle = ""

        # ── Apply employee filter ──
        if filters.get("employee") and employee != filters["employee"]:
            continue

        data_used = detail.data_used or 0
        credit_used = detail.credit_used or 0
        data_balance = data_limit - data_used
        credit_balance = credit_limit - credit_used

        if data_balance < 0 or credit_balance < 0:
            status = "Exceeded"
        elif data_balance == 0 or credit_balance == 0:
            status = "Limit Reached"
        elif data_limit and data_used >= data_limit * 0.8:
            status = "Near Limit"
        elif credit_limit and credit_used >= credit_limit * 0.8:
            status = "Near Limit"
        else:
            status = "Normal"

        data.append({
            "gsm_bill": detail.parent,
            "month": detail.month or (bill.month if bill else ""),
            "year": detail.year or (bill.year if bill else ""),
            "gsm_no": detail.gsm_no or "",
            "employee": employee,
            "employee_name": employee_name,
            "data_used": data_used,
            "data_limit": data_limit,
            "data_balance": data_balance,
            "credit_used": credit_used,
            "credit_limit": credit_limit,
            "credit_balance": credit_balance,
            "name_bundle": name_bundle,
            "status": status
        })

    # Sort: Exceeded first, then Limit Reached, Near Limit, Normal
    status_order = {"Exceeded": 0, "Limit Reached": 1, "Near Limit": 2, "Normal": 3}
    data.sort(key=lambda x: status_order.get(x["status"], 4))

    return data