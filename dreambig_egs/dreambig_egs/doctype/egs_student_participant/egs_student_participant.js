// Copyright (c) 2026, Dream Big and contributors
// For license information, please see license.txt

frappe.ui.form.on("EGS Student Participant", {
	refresh: function (frm) {
		frm.set_query("university_college", function () {
			return {
				filters: frm.doc.city ? { "city": frm.doc.city } : {}
			};
		});

		frm.set_query("event", function () {
			let filters = {
				status: "Open for Registration"
			};
			if (frm.doc.city) {
				filters.city = frm.doc.city;
			}
			return {
				query: "dreambig_egs.dreambig_egs.doctype.egs_event.egs_event.get_events_query",
				filters: filters
			};
		});

		frm.set_query("course", function () {
			return {
				filters: frm.doc.faculty_department ? { "faculty": frm.doc.faculty_department } : {}
			};
		});
	},
	city: function (frm) {
		frm.set_value("university_college", "");
		frm.set_value("event", "");
	},
	course: function (frm) {
		if (frm.doc.course && !frm.doc.faculty_department) {
			frappe.db.get_value("EGS Course", frm.doc.course, "faculty", function (r) {
				if (r && r.faculty) {
					frm.set_value("faculty_department", r.faculty);
				}
			});
		}
	},
	faculty_department: function (frm) {
		if (frm.doc.course && frm.doc.faculty_department) {
			frappe.db.get_value("EGS Course", frm.doc.course, "faculty", function (r) {
				if (r && r.faculty && r.faculty !== frm.doc.faculty_department) {
					frm.set_value("course", "");
				}
			});
		}
	}
});
