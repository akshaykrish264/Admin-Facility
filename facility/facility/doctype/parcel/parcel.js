// Copyright (c) 2026, facility and contributors
// For license information, please see license.txt

frappe.ui.form.on("Parcel", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status === "Pending For Receival") {
			frm.add_custom_button(__("Received"), () => {
				frm.call("mark_received").then(() => frm.reload_doc());
			}, __("Mark As"));
			frm.add_custom_button(__("Rejected"), () => {
				frm.call("mark_rejected").then(() => frm.reload_doc());
			}, __("Mark As"));
		}
	},
});
