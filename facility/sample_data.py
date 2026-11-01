"""Sample data for every Facility doctype, including the full
request -> approval (submit) -> booking flow.

    bench --site facility.local execute facility.sample_data.create

Safe to re-run: masters are matched by name and transactions are only
created when no Accommodation Request exists yet."""

import frappe
from frappe.utils import add_days, getdate, today

from facility.facility.doctype.accommodation_request.accommodation_request import (
	make_accommodation_booking,
)


def create():
	company = frappe.defaults.get_global_default("company") or frappe.get_all("Company", pluck="name")[0]
	cost_center = frappe.db.get_value("Company", company, "cost_center")

	employees = make_employees(company)
	masters = make_masters(cost_center)

	if frappe.db.count("Accommodation Request"):
		print("Transactions already exist, only masters were checked.")
	else:
		make_transactions(employees, masters, cost_center)

	frappe.db.commit()
	print("Sample data ready.")


# ---------------------------------------------------------------- helpers

def get_or_create(doctype, filters, values=None):
	name = frappe.db.get_value(doctype, filters)
	if name:
		return frappe.get_doc(doctype, name)
	doc = frappe.get_doc({"doctype": doctype, **filters, **(values or {})})
	doc.insert(ignore_permissions=True)
	return doc


def submit(doc):
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc


def sample_file(name):
	return get_or_create(
		"File", {"file_name": name}, {"content": "Sample attachment for demo data", "is_private": 0}
	).file_url


def first_existing(doctype, names):
	return next((n for n in names if frappe.db.exists(doctype, n)), None)


# ---------------------------------------------------------------- employees

def make_employees(company):
	designations = {
		"Ahmed Al Balushi": "Manager",
		"Rahul Nair": "Engineer",
		"Maria Santos": "Accountant",
		"Imran Khan": "Technician",
		"Fatima Al Harthy": "Administrative Officer",
		"Suresh Kumar": "Engineer",
	}
	genders = {"Maria Santos": "Female", "Fatima Al Harthy": "Female"}
	employees = []
	for i, (full_name, designation) in enumerate(designations.items()):
		first, last = full_name.split(" ", 1)
		emp = get_or_create(
			"Employee",
			{"first_name": first, "last_name": last, "company": company},
			{
				"gender": genders.get(full_name, "Male"),
				"date_of_birth": f"198{i}-0{i + 1}-15",
				"date_of_joining": "2022-01-01",
				"status": "Active",
				"designation": first_existing("Designation", [designation, "Manager"]),
				"cell_number": f"+968 9{i}12 34{i}6",
				"passport_number": f"P{4810230 + i}",
				"valid_upto": "2030-12-31",
			},
		)
		employees.append(emp.name)
	return employees


# ---------------------------------------------------------------- masters

def make_masters(cost_center):
	m = frappe._dict()

	# Locations
	m.loc = {}
	for name, code, ltype, city in [
		("Muscat Head Office", "MCT-HO", "Building", "Muscat"),
		("Sohar Project Site", "SOH-PS", "Outdoor", "Sohar"),
		("Duqm Project Site", "DQM-PS", "Outdoor", "Duqm"),
		("Muscat Central Warehouse", "MCT-WH", "Warehouse", "Muscat"),
	]:
		m.loc[code] = get_or_create(
			"Facility Location", {"location_name": name},
			{"location_code": code, "location_type": ltype, "city": city, "country": "Oman"},
		).name

	# Room types (occupancy drives capacity checks)
	for room_type, occupancy in [("Single", 1), ("Double", 2), ("Suite", 2), ("Dormitory", 4)]:
		get_or_create("Accommodation Room Types", {"room_type": room_type}, {"occupancy": occupancy})

	for room_no in ["101", "102", "103", "201", "202", "301", "A-01", "A-02", "A-03", "B-01", "B-02"]:
		get_or_create("Room Master", {"room_no": room_no})

	# Hotels
	m.hotel = get_or_create(
		"Hotel Master", {"hotel_name": "Sohar Beach Hotel"},
		{
			"location": m.loc["SOH-PS"], "cost_center": cost_center, "hotel_email": "reservations@soharbeach.example",
			"room_types": [
				{"room_type": "Single", "max_occupancy": 1, "room_rate": 35},
				{"room_type": "Double", "max_occupancy": 2, "room_rate": 50},
				{"room_type": "Suite", "max_occupancy": 2, "room_rate": 90},
			],
			"rooms": [
				{"room_no": "101", "room_type": "Single", "rate": 35},
				{"room_no": "102", "room_type": "Single", "rate": 35},
				{"room_no": "103", "room_type": "Single", "rate": 35},
				{"room_no": "201", "room_type": "Double", "rate": 50},
				{"room_no": "202", "room_type": "Double", "rate": 50},
				{"room_no": "301", "room_type": "Suite", "rate": 90},
			],
		},
	).name
	get_or_create(
		"Hotel Master", {"hotel_name": "Muscat City Inn"},
		{
			"location": m.loc["MCT-HO"], "cost_center": cost_center,
			"rooms": [
				{"room_no": "101", "room_type": "Single", "rate": 40},
				{"room_no": "201", "room_type": "Double", "rate": 60},
			],
		},
	)

	# Camps
	m.camp = get_or_create(
		"Camp Master", {"camp_name": "Duqm Labour Camp"},
		{
			"location": m.loc["DQM-PS"], "cost_center": cost_center, "camp_email": "camp.duqm@example.com",
			"rooms": [
				{"room_no": "A-01", "room_type": "Dormitory", "rate": 8},
				{"room_no": "A-02", "room_type": "Dormitory", "rate": 8},
				{"room_no": "A-03", "room_type": "Double", "rate": 12},
				{"room_no": "B-01", "room_type": "Single", "rate": 15},
				{"room_no": "B-02", "room_type": "Single", "rate": 15},
			],
		},
	).name

	# Halls
	for hall, floor in [("Board Room", "5th Floor"), ("Training Hall", "Ground Floor"), ("Meeting Room 1", "2nd Floor")]:
		get_or_create("Hall Master", {"hall_name": hall}, {"floor": floor})

	# Clinics bill through a Supplier
	supplier_group = first_existing("Supplier Group", ["Services", "All Supplier Groups"])
	m.supplier = get_or_create(
		"Supplier", {"supplier_name": "Al Raffah Medical Centre"},
		{"supplier_group": supplier_group, "supplier_type": "Company"},
	).name
	m.clinic = get_or_create(
		"Clinic Master", {"clinic_name": "Al Raffah Clinic Sohar"},
		{"supplier": m.supplier, "contact_person": "Dr. Salim", "email": "billing@alraffah.example"},
	).name
	get_or_create(
		"Clinic Master", {"clinic_name": "Badr Al Samaa Duqm"},
		{"supplier": m.supplier, "contact_person": "Dr. Anitha"},
	)
	m.item = get_or_create(
		"Item", {"item_code": "MED-TREATMENT"},
		{
			"item_name": "Medical Treatment Charges",
			"item_group": first_existing("Item Group", ["Services", "All Item Groups"]),
			"stock_uom": first_existing("UOM", ["Nos", "Unit"]),
			"is_stock_item": 0,
		},
	).name

	# Contracts
	for category in ["Cleaning", "Security", "Catering", "Maintenance"]:
		get_or_create("Contract Category", {"contract_category": category})
	for category in ["Furniture", "IT Equipment", "Stationery", "Safety Gear"]:
		get_or_create("Item Category", {"category_name": category})

	get_or_create(
		"Contract Detail Registration", {"contract_no": "CNT-2026-001"},
		{
			"contract_title": "Head Office Cleaning Services", "contract_category": "Cleaning",
			"scope_of_work": "Daily cleaning of all floors and washrooms", "contract_value": 18000,
			"contract_period_from": "2026-01-01 00:00:00", "contract_period_to": "2026-12-31 23:59:00",
		},
	)
	get_or_create(
		"Contract Detail Registration", {"contract_no": "CNT-2026-002"},
		{
			"contract_title": "Duqm Camp Catering", "contract_category": "Catering",
			"sub_contractor_name_if_applicable": "Gulf Catering LLC", "contract_value": 42000,
			"contract_period_from": "2026-04-01 00:00:00", "contract_period_to": "2027-03-31 23:59:00",
		},
	)

	# Flights
	m.agency = get_or_create(
		"Flight Agency", {"agency_name": "Oman Travel Bureau"},
		{"contact_person": "Khalid", "email": "tickets@otb.example"},
	).name
	get_or_create("Flight Agency", {"agency_name": "Bahwan Travel"}, {"contact_person": "Priya"})
	m.flt = {}
	for name, code, country, city in [
		("Muscat International Airport", "MCT", "Oman", "Muscat"),
		("Sohar Airport", "OHS", "Oman", "Sohar"),
		("Cochin International Airport", "COK", "India", "Kochi"),
		("Manila Ninoy Aquino Airport", "MNL", "Philippines", "Manila"),
	]:
		m.flt[code] = get_or_create(
			"Flight Location", {"location_code": code},
			{"location_name": name, "iata_code": code, "location_type": "Airport", "country": country, "city": city},
		).name

	# Transportation
	m.trans = {}
	for name, code, ltype in [
		("Head Office Muscat", "T-HO", "Office"),
		("Muscat Airport", "T-MCT", "Airport"),
		("Sohar Site Office", "T-SOH", "Office"),
		("Staff Accommodation Ghala", "T-GHL", "Residential"),
	]:
		m.trans[code] = get_or_create(
			"Transportation Location", {"location_name": name}, {"location_code": code, "location_type": ltype}
		).name

	return m


# ---------------------------------------------------------------- transactions

def make_transactions(emp, m, cost_center):
	d = getdate(today())

	# ---- Accommodation: request -> submit (approve) -> booking -> submit
	camp_req = submit(frappe.get_doc({
		"doctype": "Accommodation Request",
		"accommodation_type": "Camp",
		"from_location": m.loc["MCT-HO"], "to_location": m.loc["DQM-PS"],
		"check_in": f"{add_days(d, 2)} 14:00:00", "check_out": f"{add_days(d, 16)} 11:00:00",
		"camp_name": m.camp,
		"remarks": "Site mobilisation crew",
		"passengers": [
			{"is_emp": 1, "employee_id": emp[3], "room_type": "Dormitory", "justification": "Shutdown works"},
			{"is_emp": 1, "employee_id": emp[5], "room_type": "Dormitory"},
			{"is_emp": 0, "guest_name": "Vendor Technician", "designation": "Siemens Engineer", "room_type": "Single"},
		],
	}))
	booking = frappe.get_doc(make_accommodation_booking(camp_req.name))
	for row, room in zip(booking.camp_details, ["A-01", "A-01", "B-01"]):
		row.room_no = room  # rate is filled from the Camp Master on save
	submit(booking)

	hotel_req = submit(frappe.get_doc({
		"doctype": "Accommodation Request",
		"accommodation_type": "Hotel",
		"from_location": m.loc["MCT-HO"], "to_location": m.loc["SOH-PS"],
		"check_in": f"{add_days(d, 5)} 14:00:00", "check_out": f"{add_days(d, 8)} 12:00:00",
		"hotel_name": m.hotel,
		"passengers": [
			{"is_emp": 1, "employee_id": emp[0], "room_type": "Suite", "justification": "Client meeting"},
			{"is_emp": 1, "employee_id": emp[1], "room_type": "Single"},
		],
	}))
	booking = frappe.get_doc(make_accommodation_booking(hotel_req.name))
	booking.hotel_details[0].room_no = "301"
	booking.hotel_details[1].room_no = "101"
	booking.insert(ignore_permissions=True)  # left as draft: room allocated, awaiting submit

	# Approved request with no booking yet: shows the "Create > Accommodation Booking" button
	submit(frappe.get_doc({
		"doctype": "Accommodation Request",
		"accommodation_type": "Hotel",
		"from_location": m.loc["MCT-HO"], "to_location": m.loc["SOH-PS"],
		"check_in": f"{add_days(d, 10)} 14:00:00", "check_out": f"{add_days(d, 12)} 12:00:00",
		"hotel_name": m.hotel,
		"passengers": [{"is_emp": 1, "employee_id": emp[2], "room_type": "Double"},
					   {"is_emp": 0, "guest_name": "External Auditor", "room_type": "Double"}],
	}))
	# Draft request
	frappe.get_doc({
		"doctype": "Accommodation Request",
		"accommodation_type": "Camp",
		"from_location": m.loc["SOH-PS"], "to_location": m.loc["DQM-PS"],
		"check_in": f"{add_days(d, 20)} 14:00:00", "check_out": f"{add_days(d, 27)} 11:00:00",
		"camp_name": m.camp,
		"passengers": [{"is_emp": 1, "employee_id": emp[4], "room_type": "Single"}],
	}).insert(ignore_permissions=True)

	# ---- Hall bookings
	submit(frappe.get_doc({
		"doctype": "Hall Booking Request", "hall_name": "Board Room",
		"from": f"{add_days(d, 1)} 10:00:00", "to": f"{add_days(d, 1)} 12:00:00",
		"no_of_people": 12, "specific_remarks": "Projector and coffee",
	}))
	frappe.get_doc({
		"doctype": "Hall Booking Request", "hall_name": "Training Hall",
		"from": f"{add_days(d, 3)} 09:00:00", "to": f"{add_days(d, 3)} 17:00:00",
		"no_of_people": 30, "specific_remarks": "HSE induction",
	}).insert(ignore_permissions=True)

	# ---- Flights
	submit(frappe.get_doc({
		"doctype": "Flight Ticket Booking",
		"request_type": "Employee", "purpose": "Annual Leave", "way": "Return",
		"departure_date": add_days(d, 14), "return_date": add_days(d, 44),
		"from_location": m.flt["MCT"], "to_location": m.flt["COK"],
		"passport_id_upload": sample_file("sample_passport.txt"),
		"agency": [{"agency": m.agency}],
		"passengers": [{"is_emp": 1, "employee_id": emp[1], "passenger_name": "Rahul Nair", "travel_class": "Economy"}],
	}))
	frappe.get_doc({
		"doctype": "Flight Ticket Booking",
		"request_type": "Guest", "purpose": "Business Trip", "way": "One Way",
		"departure_date": add_days(d, 6),
		"from_location": m.flt["MNL"], "to_location": m.flt["MCT"],
		"passport_id_upload": sample_file("sample_passport.txt"),
		"passengers": [{"is_emp": 0, "passenger_name": "Jose Reyes", "gender": "Male",
						"nationality": "Philippines", "passport_no": "PH7731902", "travel_class": "Business"}],
	}).insert(ignore_permissions=True)

	# ---- Transportation
	submit(frappe.get_doc({
		"doctype": "Transportation Request", "purpose": "Work",
		"from_location": m.trans["T-HO"], "to_location": m.trans["T-SOH"], "date": add_days(d, 1),
		"passengers": [{"is_emp": 1, "emp_no": emp[0]}, {"is_emp": 1, "emp_no": emp[1]}],
	}))
	frappe.get_doc({
		"doctype": "Transportation Request", "purpose": "Vacation",
		"from_location": m.trans["T-GHL"], "to_location": m.trans["T-MCT"], "date": add_days(d, 14),
		"passengers": [{"is_emp": 1, "emp_no": emp[1]}],
	}).insert(ignore_permissions=True)

	# ---- Parcels
	submit(frappe.get_doc({
		"doctype": "Parcel", "parcel_no": "PCL-0001", "transport_provider": "Aramex",
		"sender_employee": emp[2], "receiver_employee": emp[3],
		"from_location": m.trans["T-HO"], "to_location": m.trans["T-SOH"], "date": d,
	}))
	received = submit(frappe.get_doc({
		"doctype": "Parcel", "parcel_no": "PCL-0002", "transport_provider": "Company Driver",
		"sender_employee": emp[0], "receiver_employee": emp[5],
		"from_location": m.trans["T-HO"], "to_location": m.trans["T-SOH"], "date": add_days(d, -3),
	}))
	received.mark_received()

	# ---- GSM: numbers -> requests (approved limit change is applied) -> bill -> report
	gsm = []
	for i, (bundle, credit, data) in enumerate([("Gold", 20, 10), ("Green", 10, 5), ("Blue", 8, 3), ("Orange", 5, 0)]):
		gsm.append(get_or_create(
			"GSM Number", {"gsm_number": f"9{i}11223{i}"},
			{"employee": emp[i], "name_bundle": bundle, "credit_limit": credit, "data_limit": data},
		).name)
	submit(frappe.get_doc({
		"doctype": "GSM Request", "employee": emp[1], "gsm_no": gsm[1], "location": m.loc["MCT-HO"],
		"request_type": "Increase Data limit", "new_data_limit": 10, "remarks": "Site hotspot use",
	}))
	frappe.get_doc({
		"doctype": "GSM Request", "employee": emp[4], "location": m.loc["MCT-HO"],
		"request_type": "Request for SIM card", "credit_limit": 10, "hand_set": "Android",
	}).insert(ignore_permissions=True)

	month = d.strftime("%B")
	frappe.get_doc({
		"doctype": "GSM Bill Upload", "month": month, "year": str(d.year),
		"bill_details": [
			{"gsm_no": "90112230", "credit_used": 12.5, "data_used": 6.2},
			{"gsm_no": "91112231", "credit_used": 10, "data_used": 8.1},
			{"gsm_no": "92112232", "credit_used": 9.75, "data_used": 2.9},
			{"gsm_no": "93112233", "credit_used": 2, "data_used": 1.4},
			{"gsm_no": "99999999", "credit_used": 4, "data_used": 0.5},
		],
	}).insert(ignore_permissions=True)

	# ---- Insurance
	submit(frappe.get_doc({
		"doctype": "Insurance Card Request", "employee": emp[1],
		"members": [
			{"relation": "Employee", "member_name": "Rahul Nair", "dob": "1981-02-15", "nationality": "Indian", "gender": "Male"},
			{"relation": "Wife", "member_name": "Anjali Nair", "dob": "1985-07-02", "nationality": "Indian", "gender": "Female"},
			{"relation": "Son", "member_name": "Arjun Nair", "dob": "2016-11-20", "nationality": "Indian", "gender": "Male"},
		],
	}))
	frappe.get_doc({
		"doctype": "Insurance Card Request", "employee": emp[4],
		"members": [{"relation": "Employee", "member_name": "Fatima Al Harthy", "nationality": "Omani", "gender": "Female"}],
	}).insert(ignore_permissions=True)

	# ---- Medical: requests -> invoice pulls submitted requests for the clinic's supplier
	for i, (e, test) in enumerate([(emp[3], "ftw"), (emp[5], "xray"), (emp[4], "tmt")]):
		doc = frappe.get_doc({
			"doctype": "Medical Treatment Request", "employee": e, "location": m.loc["SOH-PS"],
			"nationality": "India", "cost_center": cost_center, "clinic": m.clinic,
			"medical_date": add_days(d, -10 + i), test: 1,
		})
		submit(doc) if i < 2 else doc.insert(ignore_permissions=True)

	inv = frappe.get_doc({
		"doctype": "Medical Treatment Invoice Entry", "supplier": m.supplier, "item_code": m.item,
		"date": d, "ref_no": "ARC/INV/7781", "ref_date": d,
		"from_date": add_days(d, -30), "to_date": d,
		"upload_document": sample_file("sample_clinic_invoice.txt"),
	})
	inv.get_medical_requests()
	for row, amount in zip(inv.medical_requests, [25, 40]):
		row.bill_amount = amount
	inv.insert(ignore_permissions=True)

	# ---- Utility bills
	for utype, account, amount in [("Electricity", "EL-778812", 412.5), ("Water", "WT-55120", 96.0), ("Internet", "NET-90021", 120.0)]:
		frappe.get_doc({
			"doctype": "Utility Bill", "utility_type": utype, "location": m.loc["MCT-HO"],
			"account_no": account, "amount": amount, "date": d, "cost_center": cost_center,
			"choose_bill": sample_file("sample_utility_bill.txt"),
		}).insert(ignore_permissions=True)
