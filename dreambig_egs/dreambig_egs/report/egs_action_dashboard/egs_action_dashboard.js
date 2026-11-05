// Copyright (c) 2026, Mohammed Faisal and contributors
// For license information, please see license.txt

frappe.query_reports["EGS Action Dashboard"] = {
	filters: [
		{
			fieldname: "university_college",
			label: __("University/College"),
			fieldtype: "Link",
			options: "EGS Institution",
			width: "80",
		},
		{
			fieldname: "escalation_route",
			label: __("Escalation Route"),
			fieldtype: "Select",
			options: "\nStuck\nSilent",
			width: "80",
		},
	],
};
