import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, formatdate


class AccommodationBooking(Document):
    def validate(self):
        self.validate_request()
        if not (self.camp_details or self.hotel_details):
            self.set_details_from_request()
        self.validate_room_no_conflicts()
        self.validate_room_occupancy()
        self.set_rates()

    def set_rates(self):
        """Rate comes from the master's room row, so it is right even when
        rows are filled by API/import rather than the form."""
        is_camp = self.accommodation_type == "Camp"
        master_doctype = "Camp Master" if is_camp else "Hotel Master"
        master_name = self.camp_name if is_camp else self.hotel_name
        if not master_name:
            return
        rates = {
            r.room_no: r.rate
            for r in frappe.get_doc(master_doctype, master_name).get("rooms") or []
        }
        for row in (self.camp_details if is_camp else self.hotel_details) or []:
            row.rate = rates.get(row.room_no) if row.room_no else 0

    def before_submit(self):
        rows = self.camp_details if self.accommodation_type == "Camp" else self.hotel_details
        if not rows:
            frappe.throw(_("No guests to book. Re-select the Accommodation Request."))

    def validate_request(self):
        req = frappe.db.get_value(
            "Accommodation Request", self.accommodation_request, ["docstatus"], as_dict=True
        )
        if not req or req.docstatus != 1:
            frappe.throw(_("Accommodation Request {0} must be submitted before booking").format(
                self.accommodation_request
            ))

        existing = frappe.db.get_value(
            "Accommodation Booking",
            {
                "accommodation_request": self.accommodation_request,
                "docstatus": ["<", 2],
                "name": ["!=", self.name or ""],
            },
        )
        if existing:
            frappe.throw(_("Accommodation Request {0} is already booked in {1}").format(
                self.accommodation_request, existing
            ))

    @frappe.whitelist()
    def set_details_from_request(self):
        """Copies header fields and one booking row per passenger from the
        linked request. Room No is left for the facility team to allocate."""
        req = frappe.get_doc("Accommodation Request", self.accommodation_request)

        for field in ("from_location", "to_location", "accommodation_type",
                      "check_in", "check_out", "hotel_name", "camp_name"):
            self.set(field, req.get(field))

        is_camp = req.accommodation_type == "Camp"
        master_doctype = "Camp Master" if is_camp else "Hotel Master"
        master_name = req.camp_name if is_camp else req.hotel_name
        self.cost_center = frappe.db.get_value(master_doctype, master_name, "cost_center")

        self.set("camp_details", [])
        self.set("hotel_details", [])
        for p in req.passengers:
            self.append("camp_details" if is_camp else "hotel_details", {
                "employee_id": p.employee_id,
                "is_emp": p.is_emp,
                "camp" if is_camp else "hotel": master_name,
                "from_date": req.check_in,
                "to_date": req.check_out,
                "guest_name": p.guest_name,
                "designation": p.designation,
                "room_type": p.room_type,
                "remarks": p.justification,
            })

    def validate_room_occupancy(self):
        """A room can be shared (e.g. a Double) but not beyond the
        occupancy of its room type."""
        rows = self.camp_details if self.accommodation_type == "Camp" else self.hotel_details
        guests_per_room = {}
        for row in rows or []:
            if row.room_no:
                guests_per_room.setdefault((row.room_no, row.room_type), []).append(row.idx)

        for (room_no, room_type), idxs in guests_per_room.items():
            occupancy = cint(frappe.db.get_value("Accommodation Room Types", room_type, "occupancy")) or 1
            if len(idxs) > occupancy:
                frappe.throw(_("Room {0} ({1}) holds {2} guest(s) but is assigned to rows {3}").format(
                    room_no, room_type, occupancy, ", ".join(str(i) for i in idxs)
                ))

    def validate_room_no_conflicts(self):
        if not self.accommodation_type or not self.check_in or not self.check_out:
            return

        if self.accommodation_type == 'Camp':
            self._validate_rooms_exist_in_master(
                master_doctype='Camp Master',
                master_name=self.camp_name,
                child_table_field='camp_details'
            )
            self._validate_room_conflicts(
                child_table_field='camp_details',
                master_link_field='camp',
                master_value=self.camp_name,
                child_doctype='Camp Booking Detail'
            )
        elif self.accommodation_type == 'Hotel':
            self._validate_rooms_exist_in_master(
                master_doctype='Hotel Master',
                master_name=self.hotel_name,
                child_table_field='hotel_details'
            )
            self._validate_room_conflicts(
                child_table_field='hotel_details',
                master_link_field='hotel',
                master_value=self.hotel_name,
                child_doctype='Hotel Booking Detail'
            )

    def _validate_rooms_exist_in_master(self, master_doctype, master_name, child_table_field):
        """Confirms every room_no + room_type picked in the booking actually
        exists in the selected Hotel/Camp master's Rooms child table. The
        client-side dropdown already restricts this, but that's a UI
        convenience only — this is the real enforcement."""
        rows = self.get(child_table_field) or []
        if not rows or not master_name:
            return

        master = frappe.get_doc(master_doctype, master_name)
        master_rooms = master.get("rooms") or []
        valid_room_pairs = {(r.room_no, r.room_type) for r in master_rooms}

        for row in rows:
            if not row.room_no:
                frappe.throw(_("Row #{0}: Room No is required").format(row.idx))

            if (row.room_no, row.room_type) not in valid_room_pairs:
                frappe.throw(_(
                    "Row #{0}: Room '{1}' with Room Type '{2}' does not exist "
                    "in {3} '{4}'. Check the Rooms list on the master record."
                ).format(row.idx, row.room_no, row.room_type, master_doctype, master_name))

    def _validate_room_conflicts(self, child_table_field, master_link_field, master_value, child_doctype):
        rows = self.get(child_table_field) or []
        room_nos = list({r.room_no for r in rows if r.room_no})

        if not room_nos or not master_value:
            return

        # Other submitted bookings for the same property whose date range
        # overlaps this one: standard interval-overlap test
        overlapping_parents = frappe.get_all(
            'Accommodation Booking',
            filters={
                'accommodation_type': self.accommodation_type,
                'docstatus': 1,
                'name': ['!=', self.name or ''],
                'check_in': ['<', self.check_out],
                'check_out': ['>', self.check_in],
            },
            pluck='name'
        )

        if not overlapping_parents:
            return

        conflicting_rows = frappe.get_all(
            child_doctype,
            filters={
                'parent': ['in', overlapping_parents],
                master_link_field: master_value,
                'room_no': ['in', room_nos]
            },
            fields=['room_no', 'parent']
        )

        if conflicting_rows:
            conflicts = ", ".join(
                "{0} (already booked in {1})".format(c.room_no, c.parent)
                for c in conflicting_rows
            )
            frappe.throw(_(
                "Room booking conflict for {0} to {1}: {2}"
            ).format(
                formatdate(self.check_in), formatdate(self.check_out), conflicts
            ))


@frappe.whitelist()
def get_available_rooms(accommodation_type, master_name, check_in, check_out, exclude_name=None):
    """Returns rooms from the selected Hotel/Camp master that are NOT already
    booked by another submitted Accommodation Booking with an overlapping
    date range. Used to populate the Room No dropdown with only available
    rooms, instead of every room that physically exists."""
    if not (accommodation_type and master_name and check_in and check_out):
        return []

    master_doctype = 'Hotel Master' if accommodation_type == 'Hotel' else 'Camp Master'
    child_doctype = 'Hotel Booking Detail' if accommodation_type == 'Hotel' else 'Camp Booking Detail'
    master_link_field = 'hotel' if accommodation_type == 'Hotel' else 'camp'

    if not frappe.db.exists(master_doctype, master_name):
        return []

    master = frappe.get_doc(master_doctype, master_name)
    all_rooms = master.get('rooms') or []

    filters = {
        'accommodation_type': accommodation_type,
        'docstatus': 1,
        'check_in': ['<', check_out],
        'check_out': ['>', check_in],
    }
    if exclude_name:
        filters['name'] = ['!=', exclude_name]

    overlapping_parents = frappe.get_all('Accommodation Booking', filters=filters, pluck='name')

    booked_room_nos = set()
    if overlapping_parents:
        booked_rows = frappe.get_all(
            child_doctype,
            filters={
                'parent': ['in', overlapping_parents],
                master_link_field: master_name
            },
            fields=['room_no']
        )
        booked_room_nos = {b.room_no for b in booked_rows if b.room_no}

    available = [
        {'room_no': r.room_no, 'room_type': r.room_type, 'rate': r.rate}
        for r in all_rooms
        if r.room_no and r.room_no not in booked_room_nos
    ]

    return available


@frappe.whitelist()
def get_conflicting_bookings(accommodation_type, master_value, room_no, check_in, check_out, exclude_name=None):
    """Whitelisted lookup for client-side early warning when a room_no is
    picked — mirrors the server-side validate() logic so the user sees the
    conflict before trying to save."""
    if not (accommodation_type and master_value and room_no and check_in and check_out):
        return []

    child_doctype = 'Camp Booking Detail' if accommodation_type == 'Camp' else 'Hotel Booking Detail'
    master_link_field = 'camp' if accommodation_type == 'Camp' else 'hotel'

    filters = {
        'accommodation_type': accommodation_type,
        'docstatus': 1,
        'check_in': ['<', check_out],
        'check_out': ['>', check_in],
    }
    if exclude_name:
        filters['name'] = ['!=', exclude_name]

    overlapping_parents = frappe.get_all('Accommodation Booking', filters=filters, pluck='name')

    if not overlapping_parents:
        return []

    conflicts = frappe.get_all(
        child_doctype,
        filters={
            'parent': ['in', overlapping_parents],
            master_link_field: master_value,
            'room_no': room_no
        },
        fields=['parent']
    )

    return [c.parent for c in conflicts]