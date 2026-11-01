// Copyright (c) 2026, facility and contributors
// For license information, please see license.txt

frappe.ui.form.on("Medical Treatment Invoice Entry", {
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Get Treatment Requests"), () => {
				frm.call("get_medical_requests").then(() => frm.refresh_field("medical_requests"));
			});
		}
	},
});

frappe.ui.form.on("Medical Invoice Detail", {
	bill_amount(frm) {
		let total = (frm.doc.medical_requests || []).reduce((sum, row) => sum + flt(row.bill_amount), 0);
		frm.set_value("total", total);
	},
	medical_requests_remove(frm) {
		let total = (frm.doc.medical_requests || []).reduce((sum, row) => sum + flt(row.bill_amount), 0);
		frm.set_value("total", total);
	},
});
