import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import formatdate


class AccommodationBooking(Document):
    def validate(self):
        self.validate_room_no_conflicts()

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