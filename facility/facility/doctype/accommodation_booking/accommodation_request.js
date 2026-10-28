// ============================================================
// PARENT DOCTYPE: Accommodation Request
// Handles: restricting Room Type options to what's configured
// in the selected Hotel/Camp master, and showing a live
// availability warning as dates/room types change.
// ============================================================
frappe.ui.form.on('Accommodation Request', {
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
        method: 'your_app.your_module.doctype.accommodation_request.accommodation_request.get_room_types_for_master',
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

            // Restrict the Room Type Select field in the child grid to only
            // the room types that actually exist in the chosen master
            let grid = frm.fields_dict['passengers'].grid;
            grid.update_docfield_property('room_type', 'options', room_types.join('\n'));

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
        method: 'your_app.your_module.doctype.accommodation_request.accommodation_request.get_room_availability',
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
        <table class="table table-bordered" style="margin-top:8px;">
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
        frm.availability_wrapper = $(`<div></div>`).insertAfter(
            frm.fields_dict['check_out'].$wrapper
        );
    }
    frm.availability_wrapper.html(html);
}


// ============================================================
// CHILD TABLE: Accommodation Request Passenger
// (your existing logic — unchanged, plus a room_type check)
// ============================================================
frappe.ui.form.on('Accommodation Request Passenger', {
    is_emp: function(frm, cdt, cdn) {
        toggle_employee_fields(frm, cdt, cdn);
    },
    passengers_add: function(frm, cdt, cdn) {
        toggle_employee_fields(frm, cdt, cdn);
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

function toggle_employee_fields(frm, cdt, cdn) {
    var row = locals[cdt][cdn];
    if (row.is_emp) {
        frm.fields_dict['passengers'].grid.update_docfield_property('employee_id', 'read_only', 0);
        frm.fields_dict['passengers'].grid.update_docfield_property('guest_name', 'read_only', 1);
        frm.fields_dict['passengers'].grid.update_docfield_property('designation', 'read_only', 1);
        frm.fields_dict['passengers'].grid.update_docfield_property('employee_id', 'reqd', 1);
    } else {
        frappe.model.set_value(cdt, cdn, 'employee_id', '');
        frappe.model.set_value(cdt, cdn, 'guest_name', '');
        frappe.model.set_value(cdt, cdn, 'designation', '');
        frm.fields_dict['passengers'].grid.update_docfield_property('employee_id', 'read_only', 1);
        frm.fields_dict['passengers'].grid.update_docfield_property('employee_id', 'reqd', 0);
        frm.fields_dict['passengers'].grid.update_docfield_property('guest_name', 'read_only', 0);
        frm.fields_dict['passengers'].grid.update_docfield_property('designation', 'read_only', 0);
    }
    frm.refresh_field('passengers');
}