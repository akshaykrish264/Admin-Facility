// Copyright (c) 2026, facility and contributors
// For license information, please see license.txt

frappe.ui.form.on("GSM Request", {
	setup(frm) {
		// Only the selected employee's numbers
		frm.set_query("gsm_no", () => ({
			filters: frm.doc.employee ? { employee: frm.doc.employee } : {},
		}));
	},
	employee(frm) {
		frm.set_value("gsm_no", "");
	},
});
