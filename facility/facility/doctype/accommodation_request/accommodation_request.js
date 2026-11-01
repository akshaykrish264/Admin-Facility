// ============================================================
// PARENT DOCTYPE: Accommodation Request
// Handles: restricting Room Type options to what's configured
// in the selected Hotel/Camp master, and showing a live
// availability warning as dates/room types change.
// ============================================================
frappe.ui.form.on('Accommodation Request', {
    setup: function(frm) {
        // Only offer hotels/camps at the destination location
        ['hotel_name', 'camp_name'].forEach(function(field) {
            frm.set_query(field, function() {
                return frm.doc.to_location ? { filters: { location: frm.doc.to_location } } : {};
            });
        });
    },

    refresh: function(frm) {
        // Ensures the banner and room-type filtering are already in place
        // when an existing record loads — not only after a field change
        refresh_room_type_options(frm);
        check_availability(frm);
        add_create_booking_button(frm);
    },

    to_location: function(frm) {
        frm.set_value('hotel_name', '');
        frm.set_value('camp_name', '');
    },

    accommodation_type: function(frm) {
        // Type changed — clear the other location link and refresh room types
        if (frm.doc.accommodation_type === 'Hotel') {
            frm.set_value('camp_name', '');
        } else if (frm.doc.accommodation_type === 'Camp') {
            frm.set_value('hotel_name', '');
        }
        refresh_room_type_options(frm);
    },

    hotel_name: function(frm) {
        refresh_room_type_options(frm);
        check_availability(frm);
    },

    camp_name: function(frm) {
        refresh_room_type_options(frm);
        check_availability(frm);
    },

    check_in: function(frm) {
        check_availability(frm);
    },

    check_out: function(frm) {
        check_availability(frm);
    }
});

// Submitted request -> Accommodation Booking, offered only while no
// active (draft or submitted) booking exists for this request
function add_create_booking_button(frm) {
    if (frm.doc.docstatus !== 1) return;

    frappe.db.count('Accommodation Booking', {
        filters: { accommodation_request: frm.doc.name, docstatus: ['<', 2] }
    }).then(function(count) {
        if (count) return;
        frm.add_custom_button(__('Accommodation Booking'), function() {
            frappe.model.open_mapped_doc({
                method: 'facility.facility.doctype.accommodation_request.accommodation_request.make_accommodation_booking',
                frm: frm
            });
        }, __('Create'));
    });
}

function get_master_name(frm) {
    if (frm.doc.accommodation_type === 'Hotel') {
        return frm.doc.hotel_name;
    } else if (frm.doc.accommodation_type === 'Camp') {
        return frm.doc.camp_name;
    }
    return null;
}

function refresh_room_type_options(frm) {
    let master_name = get_master_name(frm);

    if (!frm.doc.accommodation_type || !master_name) {
        return;
    }

    frappe.call({
        method: 'facility.facility.doctype.accommodation_request.accommodation_request.get_room_types_for_master',
        args: {
            accommodation_type: frm.doc.accommodation_type,
            master_name: master_name
        },
        callback: function(r) {
            if (!r.message) return;
            let room_types = r.message;

            if (!room_types.length) {
                frappe.msgprint({
                    title: __('No Rooms Configured'),
                    message: __('No rooms are set up in {0}. Add rooms before booking.', [master_name]),
                    indicator: 'orange'
                });
                return;
            }

            // room_type is a Link field — filter its dropdown query rather
            // than overwrite 'options' (that property is the Link's TARGET
            // DOCTYPE, not a list of allowed values; overwriting it caused
            // Frappe to search for a doctype literally named after the
            // room type list, e.g. "Single Double Triple")
            frm.set_query('room_type', 'passengers', function() {
                return {
                    filters: {
                        'name': ['in', room_types]
                    }
                };
            });

            // Clear any already-picked room_type values that are no longer valid
            (frm.doc.passengers || []).forEach(function(row) {
                if (row.room_type && !room_types.includes(row.room_type)) {
                    frappe.model.set_value(row.doctype, row.name, 'room_type', '');
                }
            });

            frm.refresh_field('passengers');
        }
    });
}

function check_availability(frm) {
    let master_name = get_master_name(frm);

    if (!frm.doc.accommodation_type || !master_name || !frm.doc.check_in || !frm.doc.check_out) {
        return;
    }

    frappe.call({
        method: 'facility.facility.doctype.accommodation_request.accommodation_request.get_room_availability',
        args: {
            accommodation_type: frm.doc.accommodation_type,
            master_name: master_name,
            check_in: frm.doc.check_in,
            check_out: frm.doc.check_out,
            exclude_name: frm.doc.name
        },
        callback: function(r) {
            if (!r.message) return;
            render_availability_banner(frm, r.message);
        }
    });
}

function render_availability_banner(frm, availability) {
    // Count current unsaved passengers per room type so the banner reflects
    // what the user is about to book, not just what's already confirmed
    let current_counts = {};
    (frm.doc.passengers || []).forEach(function(row) {
        if (row.room_type) {
            current_counts[row.room_type] = (current_counts[row.room_type] || 0) + 1;
        }
    });

    let rows = Object.keys(availability).map(function(rt) {
        let a = availability[rt];
        let requested = current_counts[rt] || 0;
        let remaining = a.available - requested;
        let color = remaining < 0 ? 'red' : (remaining === 0 ? 'orange' : 'green');
        return `<tr>
            <td>${rt}</td>
            <td>${a.capacity}</td>
            <td>${a.booked}</td>
            <td>${requested}</td>
            <td style="color:${color}; font-weight:600">${remaining}</td>
        </tr>`;
    }).join('');

    let html = `
        <table class="table table-bordered" style="margin-top:8px; width:100%;">
            <thead>
                <tr>
                    <th>${__('Room Type')}</th>
                    <th>${__('Capacity')}</th>
                    <th>${__('Already Booked')}</th>
                    <th>${__('This Request')}</th>
                    <th>${__('Remaining After')}</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>`;

    if (!frm.availability_wrapper) {
        // Break out of the two-column field layout: insert as a new
        // full-width row (col-sm-12) after the row containing Check In /
        // Check Out, rather than nesting inside check_out's half-width column
        let $checkout_row = frm.fields_dict['check_out'].$wrapper.closest('.row');
        let $anchor = $checkout_row.length ? $checkout_row : frm.fields_dict['check_out'].$wrapper;

        frm.availability_wrapper = $(
            '<div class="row"><div class="form-column col-sm-12"><div class="availability-banner"></div></div></div>'
        ).insertAfter($anchor);
    }

    frm.availability_wrapper.find('.availability-banner').html(html);
}


// ============================================================
// CHILD TABLE: Accommodation Request Passenger
// Read-only / mandatory state of employee_id and guest_name is set per
// row in the doctype (read_only_depends_on / mandatory_depends_on);
// toggling it grid-wide here changed every row, not just this one.
// ============================================================
frappe.ui.form.on('Accommodation Request Passenger', {
    is_emp: function(frm, cdt, cdn) {
        frappe.model.set_value(cdt, cdn, 'employee_id', '');
        frappe.model.set_value(cdt, cdn, 'guest_name', '');
        frappe.model.set_value(cdt, cdn, 'designation', '');
    },
    passengers_add: function(frm, cdt, cdn) {
        check_availability(frm);
    },
    // The _remove event is triggered on the child doctype, so it has to
    // live here; on the parent it never fired and the banner went stale
    passengers_remove: function(frm) {
        check_availability(frm);
    },
    employee_id: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.employee_id) {
            frappe.db.get_doc('Employee', row.employee_id)
            .then(function(emp) {
                frappe.model.set_value(cdt, cdn, 'guest_name',  emp.employee_name || '');
                frappe.model.set_value(cdt, cdn, 'designation', emp.designation   || '');
                frm.refresh_field('passengers');
            });
        } else {
            frappe.model.set_value(cdt, cdn, 'guest_name',  '');
            frappe.model.set_value(cdt, cdn, 'designation', '');
            frm.refresh_field('passengers');
        }
    },
    room_type: function(frm, cdt, cdn) {
        // Re-render the availability banner whenever a passenger's room
        // type changes, so the "Remaining After" column stays accurate
        check_availability(frm);
    }
});