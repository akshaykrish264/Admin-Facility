import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, formatdate


class AccommodationRequest(Document):
    def validate(self):
        self.validate_room_type_availability()

    def validate_room_type_availability(self):
        if not self.accommodation_type or not self.check_in or not self.check_out:
            return

        if not self.passengers:
            return

        master_doctype, master_name = self._get_master_ref()
        if not master_name:
            return

        capacity_map = self._get_capacity_map(master_doctype, master_name)

        if not capacity_map:
            frappe.throw(_("No rooms configured in {0} '{1}'").format(master_doctype, master_name))

        # Count passengers per room type in THIS request
        current_counts = {}
        for p in self.passengers:
            if not p.room_type:
                frappe.throw(_("Row #{0}: Room Type is required").format(p.idx))
            if p.room_type not in capacity_map:
                frappe.throw(_(
                    "Row #{0}: Room Type '{1}' is not available in {2} '{3}'. "
                    "Available types: {4}"
                ).format(
                    p.idx, p.room_type, master_doctype, master_name,
                    ", ".join(capacity_map.keys())
                ))
            current_counts[p.room_type] = current_counts.get(p.room_type, 0) + 1

        existing_counts = self._get_existing_booked_counts(master_doctype, master_name)

        # Validate against total capacity per room type
        for rt, count in current_counts.items():
            total_needed = count + existing_counts.get(rt, 0)
            available = capacity_map[rt]["total_capacity"]
            if total_needed > available:
                frappe.throw(_(
                    "Room Type '{0}' in {1} '{2}' is overbooked for {3} to {4}. "
                    "Capacity: {5} guest(s), Requested (including other bookings "
                    "in this period): {6} guest(s)"
                ).format(
                    rt, master_doctype, master_name,
                    formatdate(self.check_in), formatdate(self.check_out),
                    available, total_needed
                ))

    def _get_master_ref(self):
        if self.accommodation_type == "Hotel":
            return "Hotel Master", self.get("hotel_name")
        elif self.accommodation_type == "Camp":
            return "Camp Master", self.get("camp_name")
        return None, None

    def _get_capacity_map(self, master_doctype, master_name):
        """Returns {room_type: {room_count, max_occupancy_default, total_capacity}}"""
        master = frappe.get_doc(master_doctype, master_name)
        rooms = master.get("rooms") or []

        capacity_map = {}
        for r in rooms:
            rt = r.room_type
            if not rt:
                continue
            # Camp Room may not have max_occupancy — default to 1 per room if absent
            max_occ = cint(getattr(r, "max_occupancy", None)) or 1
            if rt not in capacity_map:
                capacity_map[rt] = {"room_count": 0, "total_capacity": 0}
            capacity_map[rt]["room_count"] += 1
            capacity_map[rt]["total_capacity"] += max_occ

        return capacity_map

    def _get_existing_booked_counts(self, master_doctype, master_name):
        """Counts guests from OTHER submitted requests whose date range overlaps this one."""
        filters = {
            "accommodation_type": self.accommodation_type,
            "docstatus": 1,
            "name": ["!=", self.name or ""],
            "check_in": ["<", self.check_out],
            "check_out": [">", self.check_in],
        }
        if self.accommodation_type == "Hotel":
            filters["hotel_name"] = master_name
        else:
            filters["camp_name"] = master_name

        overlapping = frappe.get_all("Accommodation Request", filters=filters, pluck="name")

        existing_counts = {}
        if overlapping:
            existing_passengers = frappe.get_all(
                "Accommodation Request Passenger",
                filters={"parent": ["in", overlapping]},
                fields=["room_type"]
            )
            for ep in existing_passengers:
                if ep.room_type:
                    existing_counts[ep.room_type] = existing_counts.get(ep.room_type, 0) + 1

        return existing_counts


@frappe.whitelist()
def get_room_availability(accommodation_type, master_name, check_in, check_out, exclude_name=None):
    """Whitelisted method for client-side real-time availability check.
    Returns {room_type: {capacity, booked, available}}
    """
    if not (accommodation_type and master_name and check_in and check_out):
        return {}

    master_doctype = "Hotel Master" if accommodation_type == "Hotel" else "Camp Master"

    if not frappe.db.exists(master_doctype, master_name):
        return {}

    master = frappe.get_doc(master_doctype, master_name)
    rooms = master.get("rooms") or []

    capacity_map = {}
    for r in rooms:
        rt = r.room_type
        if not rt:
            continue
        max_occ = cint(getattr(r, "max_occupancy", None)) or 1
        capacity_map.setdefault(rt, 0)
        capacity_map[rt] += max_occ

    filters = {
        "accommodation_type": accommodation_type,
        "docstatus": 1,
        "check_in": ["<", check_out],
        "check_out": [">", check_in],
    }
    if exclude_name:
        filters["name"] = ["!=", exclude_name]
    if accommodation_type == "Hotel":
        filters["hotel_name"] = master_name
    else:
        filters["camp_name"] = master_name

    overlapping = frappe.get_all("Accommodation Request", filters=filters, pluck="name")

    booked_counts = {}
    if overlapping:
        existing_passengers = frappe.get_all(
            "Accommodation Request Passenger",
            filters={"parent": ["in", overlapping]},
            fields=["room_type"]
        )
        for ep in existing_passengers:
            if ep.room_type:
                booked_counts[ep.room_type] = booked_counts.get(ep.room_type, 0) + 1

    result = {}
    for rt, capacity in capacity_map.items():
        booked = booked_counts.get(rt, 0)
        result[rt] = {
            "capacity": capacity,
            "booked": booked,
            "available": capacity - booked
        }

    return result


@frappe.whitelist()
def get_room_types_for_master(accommodation_type, master_name):
    """Returns distinct room types configured in the selected Hotel/Camp master,
    used to restrict the Room Type dropdown in the passengers grid."""
    if not (accommodation_type and master_name):
        return []

    master_doctype = "Hotel Master" if accommodation_type == "Hotel" else "Camp Master"

    if not frappe.db.exists(master_doctype, master_name):
        return []

    master = frappe.get_doc(master_doctype, master_name)
    rooms = master.get("rooms") or []

    room_types = []
    for r in rooms:
        if r.room_type and r.room_type not in room_types:
            room_types.append(r.room_type)

    return room_types