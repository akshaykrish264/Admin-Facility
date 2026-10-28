frappe.query_reports["GSM Bill Comparison Report"] = {
    "filters": [
        {
            "fieldname": "month",
            "label": __("Month"),
            "fieldtype": "Select",
            "options": [
                "",
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December"
            ],
            "default": ""
        },
        {
            "fieldname": "year",
            "label": __("Year"),
            "fieldtype": "Select",
            "options": get_year_options(),
            "default": String(new Date().getFullYear())
        },
        {
            "fieldname": "employee",
            "label": __("Employee"),
            "fieldtype": "Link",
            "options": "Employee"
        }
    ]
};

function get_year_options() {
    let current_year = new Date().getFullYear();
    let years = [""];
    // 5 years back, 2 years forward — adjust range as needed
    for (let y = current_year - 5; y <= current_year + 2; y++) {
        years.push(String(y));
    }
    return years;
}