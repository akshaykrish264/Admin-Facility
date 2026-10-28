frappe.ui.form.on('Accommodation Booking', {

    refresh: function(frm) {
        toggle_tables(frm);
        //rebuild_room_no_options(frm);
    },

    onload: function(frm) {
        toggle_tables(frm);
        //rebuild_room_no_options(frm);
    },

    accommodation_request: function(frm) {
        console.log('Fetching details from Accommodation Request:', frm.doc.accommodation_request);
        if (!frm.doc.accommodation_request) return;

        frappe.db.get_doc('Accommodation Request', frm.doc.accommodation_request)
        .then(function(req) {
            frm.set_value('from_location',      req.from_location);
            frm.set_value('to_location',        req.to_location);
            frm.set_value('accommodation_type', req.accommodation_type);
            frm.set_value('check_in',           req.check_in);
            frm.set_value('check_out',          req.check_out);
            frm.set_value('hotel_name',         req.hotel_name || '');
            frm.set_value('camp_name',          req.camp_name  || '');

            // Clear child tables before rebuilding
            frm.set_value('camp_details',  []);
            frm.set_value('hotel_details', []);

            if (req.accommodation_type === 'Camp' && req.camp_name) {
                (req.passengers || []).forEach(function(p) {
                    frm.add_child('camp_details', {
                        'employee_id': p.employee_id   || '',
                        'is_emp':      p.is_emp         || 0,
                        'camp':        req.camp_name    || '',
                        'from_date':   req.check_in     || '',
                        'to_date':     req.check_out    || '',
                        'guest_name':  p.guest_name      || '',
                        'designation': p.designation     || '',
                        'room_type':   p.room_type       || '',
                        'remarks':     p.justification   || '',
                        'room_no':     '',
                        'rate':        0
                    });
                });

                set_available_room_options(frm, 'camp_details', req.accommodation_type, req.camp_name, req.check_in, req.check_out)
                .then(function() {
                    frm.refresh_field('camp_details');
                    toggle_tables(frm);
                });

            } else if (req.accommodation_type === 'Hotel' && req.hotel_name) {
                (req.passengers || []).forEach(function(p) {
                    frm.add_child('hotel_details', {
                        'employee_id': p.employee_id   || '',
                        'is_emp':      p.is_emp         || 0,
                        'hotel':       req.hotel_name    || '',
                        'from_date':   req.check_in      || '',
                        'to_date':     req.check_out     || '',
                        'guest_name':  p.guest_name       || '',
                        'designation': p.designation      || '',
                        'room_type':   p.room_type         || '',
                        'remarks':     p.justification      || '',
                        'room_no':     '',
                        'rate':        0
                    });
                });

                set_available_room_options(frm, 'hotel_details', req.accommodation_type, req.hotel_name, req.check_in, req.check_out)
                .then(function() {
                    frm.refresh_field('hotel_details');
                    toggle_tables(frm);
                });
            }

            frappe.show_alert({
                message: __('Details fetched from {0}', [frm.doc.accommodation_request]),
                indicator: 'green'
            });
        });
    },

    accommodation_type: function(frm) {
        toggle_tables(frm);
    }

});

// Fetches only rooms that are NOT already booked for an overlapping date
// range (via get_available_rooms), then sets the Room No dropdown options
// at the GRID level. Select fields share one options list across the whole
// table — they can't differ per row — so this lists every currently
// AVAILABLE room in the property; the Room Type column tells the user
// which type each row expects, and a mismatch warning fires on selection.
function set_available_room_options(frm, table_fieldname, accommodation_type, master_name, check_in, check_out) {
    console.log('Setting available room options for', accommodation_type, master_name, check_in, check_out);
    return frappe.call({
        method: 'facility.facility.doctype.accommodation_booking.accommodation_booking.get_available_rooms',
        args: {
            accommodation_type: accommodation_type,
            master_name: master_name,
            check_in: check_in,
            check_out: check_out,
            exclude_name: frm.doc.name
        }
    }).then(function(r) {
        console.log('Available rooms response:', r.message);
        var rooms = r.message || [];
        var room_nos = rooms.map(function(room) { return room.room_no; });
        var options = [""].concat(room_nos).join("\n");
        console.log('Setting Room No options for', table_fieldname, 'to:', options);
        //frm.fields_dict[table_fieldname].grid.update_docfield_property('room_no', 'options', options);
        //cur_frm.fields_dict[table_fieldname].grid.docfields.find(d => d.fieldname === 'room_no').options = options;
        //cur_frm.fields_dict[table_fieldname].grid.update_docfield_property('room_no', 'options', options);
        //cur_frm.refresh_field(table_fieldname);
        var options = ['Option A', 'Option B', 'Option C']; // build this dynamically however you need

        //let grid = frm.fields_dict["hotel_details"].grid;

        // Update the child table field definition
        let grid = frm.fields_dict.hotel_details.grid;

        grid.update_docfield_property(
            "room_no",
            "options",
            options.join("\n")
        );

        grid.grid_rows.forEach(row => {
            if (row.on_grid_fields_dict.room_no) {
                row.on_grid_fields_dict.room_no.df.options = options.join("\n");
                row.on_grid_fields_dict.room_no.refresh();
            }
        });

frm.refresh_field("hotel_details");
        frm.refresh_field("hotel_details");
        if (!rooms.length) {
            frappe.show_alert({
                message: __('No available rooms found for the selected dates in this property.'),
                indicator: 'orange'
            }, 5);
        }
    });
}

// Rebuilds Room No dropdown options on form load — without this, reopening
// a saved booking shows an empty Room No dropdown, since grid docfield
// property overrides only live in the browser's in-memory session.
function rebuild_room_no_options(frm) {
    var type = frm.doc.accommodation_type;

    if (type === 'Camp' && frm.doc.camp_name && frm.doc.check_in && frm.doc.check_out) {
        set_available_room_options(frm, 'camp_details', type, frm.doc.camp_name, frm.doc.check_in, frm.doc.check_out)
            .then(function() { frm.refresh_field('camp_details'); });
    } else if (type === 'Hotel' && frm.doc.hotel_name && frm.doc.check_in && frm.doc.check_out) {
        set_available_room_options(frm, 'hotel_details', type, frm.doc.hotel_name, frm.doc.check_in, frm.doc.check_out)
            .then(function() { frm.refresh_field('hotel_details'); });
    }
}

function check_room_conflict(frm, cdt, cdn, master_link_field) {
    console.log('Checking room conflict for row:', cdt, cdn);
    var row = locals[cdt][cdn];
    if (!row.room_no || !frm.doc.check_in || !frm.doc.check_out) return;

    var master_value = row[master_link_field];
    if (!master_value) return;

    frappe.call({
        method: 'facility.facility.doctype.accommodation_booking.accommodation_booking.get_conflicting_bookings',
        args: {
            accommodation_type: frm.doc.accommodation_type,
            master_value: master_value,
            room_no: row.room_no,
            check_in: frm.doc.check_in,
            check_out: frm.doc.check_out,
            exclude_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message && r.message.length) {
                console.log('Conflicting bookings found:', r.message);
                frappe.msgprint({
                    title: __('Room Conflict'),
                    message: __('Room {0} is already booked in {1} for an overlapping date range.',
                        [row.room_no, r.message.join(', ')]),
                    indicator: 'red'
                });
            }
        }
    });
}

// ── Camp Booking Detail - Room No change ────────────
frappe.ui.form.on('Camp Booking Detail', {
    room_no: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.room_no && row.camp) {
            frappe.db.get_doc('Camp Master', row.camp)
            .then(function(camp) {
                var matched_room = (camp.rooms || []).find(function(r) {
                    return r.room_no === row.room_no;
                });
                var rate = matched_room ? (matched_room.rate || 0) : 0;

                frappe.model.set_value(cdt, cdn, 'rate', rate);
                frm.refresh_field('camp_details');

                if (matched_room && matched_room.room_type !== row.room_type) {
                    frappe.show_alert({
                        message: __('Note: Room {0} is type "{1}", this row expects "{2}"',
                            [row.room_no, matched_room.room_type, row.room_type]),
                        indicator: 'orange'
                    }, 5);
                } else {
                    frappe.show_alert({
                        message: __('Room {0} selected - Rate: {1}', [row.room_no, rate]),
                        indicator: 'green'
                    }, 3);
                }
            });
        } else {
            frappe.model.set_value(cdt, cdn, 'rate', 0);
        }
        //check_room_conflict(frm, cdt, cdn, 'camp');
    }
});

// ── Hotel Booking Detail - Room No change ───────────
frappe.ui.form.on('Hotel Booking Detail', {
    room_no: function(frm, cdt, cdn) {
        var row = locals[cdt][cdn];
        if (row.room_no && row.hotel) {
            frappe.db.get_doc('Hotel Master', row.hotel)
            .then(function(hotel) {
                var matched_room = (hotel.rooms || []).find(function(r) {
                    return r.room_no === row.room_no;
                });
                var rate = matched_room ? (matched_room.rate || 0) : 0;

                frappe.model.set_value(cdt, cdn, 'rate', rate);
                frm.refresh_field('hotel_details');

                if (matched_room && matched_room.room_type !== row.room_type) {
                    frappe.show_alert({
                        message: __('Note: Room {0} is type "{1}", this row expects "{2}"',
                            [row.room_no, matched_room.room_type, row.room_type]),
                        indicator: 'orange'
                    }, 5);
                } else {
                    frappe.show_alert({
                        message: __('Room {0} selected - Rate: {1}', [row.room_no, rate]),
                        indicator: 'green'
                    }, 3);
                }
            });
        } else {
            frappe.model.set_value(cdt, cdn, 'rate', 0);
        }
        //check_room_conflict(frm, cdt, cdn, 'hotel');
    }
});

// ── Toggle Camp/Hotel tables ─────────────────────────
function toggle_tables(frm) {
    var type = frm.doc.accommodation_type;
    frm.set_df_property('camp_details',  'hidden', type === 'Camp'  ? 0 : 1);
    frm.set_df_property('hotel_details', 'hidden', type === 'Hotel' ? 0 : 1);
    frm.refresh_fields(['camp_details', 'hotel_details']);
}