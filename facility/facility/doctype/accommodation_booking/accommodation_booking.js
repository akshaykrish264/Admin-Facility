frappe.ui.form.on('Accommodation Booking', {

    setup: function(frm) {
        // Only submitted requests can be booked
        frm.set_query('accommodation_request', function() {
            return { filters: { docstatus: 1 } };
        });
    },

    refresh: function(frm) {
        toggle_tables(frm);
        rebuild_room_no_options(frm);
    },

    accommodation_request: function(frm) {
        if (!frm.doc.accommodation_request) return;

        // Server fills header + one row per passenger (same code path as the
        // "Create > Accommodation Booking" button on the request)
        frm.call('set_details_from_request').then(function() {
            frm.refresh_fields();
            toggle_tables(frm);
            rebuild_room_no_options(frm);
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
        var rooms = r.message || [];
        var room_nos = rooms.map(function(room) { return room.room_no; });

        // Keep rooms already picked on this booking selectable
        (frm.doc[table_fieldname] || []).forEach(function(row) {
            if (row.room_no && !room_nos.includes(row.room_no)) room_nos.push(row.room_no);
        });

        // Render rows first so update_docfield_property reaches every row,
        // then apply the options and re-render
        frm.refresh_field(table_fieldname);
        frm.fields_dict[table_fieldname].grid.update_docfield_property(
            'room_no', 'options', [''].concat(room_nos).join('\n')
        );
        frm.refresh_field(table_fieldname);

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
    if (frm.doc.docstatus !== 0) return;
    var type = frm.doc.accommodation_type;

    if (type === 'Camp' && frm.doc.camp_name && frm.doc.check_in && frm.doc.check_out) {
        return set_available_room_options(frm, 'camp_details', type, frm.doc.camp_name, frm.doc.check_in, frm.doc.check_out);
    } else if (type === 'Hotel' && frm.doc.hotel_name && frm.doc.check_in && frm.doc.check_out) {
        return set_available_room_options(frm, 'hotel_details', type, frm.doc.hotel_name, frm.doc.check_in, frm.doc.check_out);
    }
}

// Sets the rate from the master's room row and warns on a room type
// mismatch (the server rejects the mismatch on save)
function on_room_no_change(frm, cdt, cdn, master_doctype, master_link_field, table_fieldname) {
    var row = locals[cdt][cdn];
    if (!row.room_no || !row[master_link_field]) {
        frappe.model.set_value(cdt, cdn, 'rate', 0);
        return;
    }

    frappe.db.get_doc(master_doctype, row[master_link_field]).then(function(master) {
        var matched_room = (master.rooms || []).find(function(r) {
            return r.room_no === row.room_no;
        });
        var rate = matched_room ? (matched_room.rate || 0) : 0;

        frappe.model.set_value(cdt, cdn, 'rate', rate);
        frm.refresh_field(table_fieldname);

        if (matched_room && matched_room.room_type !== row.room_type) {
            frappe.msgprint({
                title: __('Room Type Mismatch'),
                message: __('Room {0} is type "{1}", this row expects "{2}". Pick a "{2}" room.',
                    [row.room_no, matched_room.room_type, row.room_type]),
                indicator: 'orange'
            });
        } else {
            frappe.show_alert({
                message: __('Room {0} selected - Rate: {1}', [row.room_no, rate]),
                indicator: 'green'
            }, 3);
        }
    });
}

// ── Camp Booking Detail - Room No change ────────────
frappe.ui.form.on('Camp Booking Detail', {
    room_no: function(frm, cdt, cdn) {
        on_room_no_change(frm, cdt, cdn, 'Camp Master', 'camp', 'camp_details');
    }
});

// ── Hotel Booking Detail - Room No change ───────────
frappe.ui.form.on('Hotel Booking Detail', {
    room_no: function(frm, cdt, cdn) {
        on_room_no_change(frm, cdt, cdn, 'Hotel Master', 'hotel', 'hotel_details');
    }
});

// ── Toggle Camp/Hotel tables ─────────────────────────
function toggle_tables(frm) {
    var type = frm.doc.accommodation_type;
    frm.set_df_property('camp_details',  'hidden', type === 'Camp'  ? 0 : 1);
    frm.set_df_property('hotel_details', 'hidden', type === 'Hotel' ? 0 : 1);
    frm.refresh_fields(['camp_details', 'hotel_details']);
}
