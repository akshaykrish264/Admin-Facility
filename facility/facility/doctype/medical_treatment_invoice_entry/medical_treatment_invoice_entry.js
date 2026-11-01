// Copyright (c) 2026, facility and contributors
// For license information, please see license.txt

frappe.ui.form.on("Medical Treatment Invoice Entry", {
	setup(frm) {
		// Item: group = Services, item_category = Medical
		frm.set_query("item_code", () => ({
			filters: { item_group: "Services", item_category: "Medical" },
		}));
		// Supplier: clinics only
		frm.set_query("supplier", () => ({ filters: { is_clinic: 1 } }));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Get Items"), () => get_medical_requests(frm), __("Actions"));
		}
	},
});

frappe.ui.form.on("Medical Invoice Detail", {
	bill_amount(frm) {
		calculate_total(frm);
	},
	// Add / remove events fire on the child doctype, not the parent
	medical_requests_add(frm) {
		calculate_total(frm);
	},
	medical_requests_remove(frm) {
		calculate_total(frm);
	},
});

function calculate_total(frm) {
	let total = (frm.doc.medical_requests || []).reduce((sum, row) => sum + flt(row.bill_amount), 0);
	frm.set_value("total", total);
}

// Fetching runs on the server (get_medical_requests in the .py): reading the
// Medical Invoice Detail child table directly from the browser is not permitted
function get_medical_requests(frm) {
	if (!frm.doc.from_date || !frm.doc.to_date) {
		frappe.msgprint({
			title: __("Required"),
			message: __("Please enter From Date and To Date to fetch Medical Requests."),
			indicator: "red",
		});
		return;
	}
	if (!frm.doc.item_code) {
		frappe.msgprint({
			title: __("Required"),
			message: __("Please select an Item Code first."),
			indicator: "red",
		});
		return;
	}

	frm.call("get_medical_requests").then((r) => {
		let counts = r.message;
		frm.refresh_field("medical_requests");
		if (!counts || (!counts.added && !counts.skipped_existing && !counts.skipped_invoiced)) return;

		let msg = __("Fetched {0} records.", [counts.added]);
		if (counts.skipped_existing) {
			msg += " " + __("{0} already in table (skipped).", [counts.skipped_existing]);
		}
		if (counts.skipped_invoiced) {
			msg += " " + __("{0} already invoiced (skipped).", [counts.skipped_invoiced]);
		}
		frappe.show_alert({ message: msg, indicator: counts.added ? "green" : "orange" }, 5);
	});
}
