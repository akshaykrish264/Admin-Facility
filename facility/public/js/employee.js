// Insurance tab: members of the employee's approved Insurance Card Requests

frappe.ui.form.on("Employee", {
	refresh(frm) {
		const field = frm.get_field("insurance_details_html");
		if (!field) return;

		if (frm.is_new()) {
			field.$wrapper.html("");
			return;
		}

		frappe
			.call({
				method: "facility.facility.doctype.insurance_card_request.insurance_card_request.get_employee_insurance",
				args: { employee: frm.doc.name },
			})
			.then((r) => field.$wrapper.html(render_insurance_table(r.message || [])));
	},
});

function render_insurance_table(rows) {
	if (!rows.length) {
		return `<p class="text-muted">${__("No approved insurance requests.")}</p>`;
	}

	const esc = (v) => frappe.utils.escape_html(v || "");
	const date = (v) => (v ? frappe.datetime.str_to_user(v) : "");
	const cost = (v) => (v ? format_currency(v) : "");

	const body = rows
		.map(
			(row) => `<tr>
				<td>${esc(row.relation)}</td>
				<td><a href="${frappe.utils.get_form_link("Insurance Card Request", row.request)}">${esc(row.member_name)}</a></td>
				<td>${esc(row.category)}</td>
				<td>${date(row.dob)}</td>
				<td>${esc(row.nationality)}</td>
				<td>${date(row.issue_date)}</td>
				<td class="text-right">${cost(row.cost)}</td>
			</tr>`
		)
		.join("");

	return `<table class="table table-bordered table-sm">
		<thead>
			<tr>
				<th>${__("Relation")}</th>
				<th>${__("Name")}</th>
				<th>${__("Category")}</th>
				<th>${__("DOB")}</th>
				<th>${__("Nationality")}</th>
				<th>${__("Issue Date")}</th>
				<th class="text-right">${__("Cost")}</th>
			</tr>
		</thead>
		<tbody>${body}</tbody>
	</table>`;
}
