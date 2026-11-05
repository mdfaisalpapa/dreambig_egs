frappe.ready(function () {
	// Populate student_reference Link field from URL query parameter ?student_id=
	frappe.web_form.after_load = () => {
		const queryParams = frappe.utils.get_query_params();
		const studentId = queryParams.student_id;
		if (studentId) {
			frappe.web_form.set_value("student_reference", studentId);
		}
	};
});
