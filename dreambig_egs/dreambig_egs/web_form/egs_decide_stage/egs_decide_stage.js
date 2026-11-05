frappe.ready(function () {
	// Default date_of_decision to today if empty
	frappe.web_form.after_load = () => {
		if (!frappe.web_form.get_value("date_of_decision")) {
			frappe.web_form.set_value("date_of_decision", frappe.datetime.now_date());
		}
	};

	// Form validation on submit
	frappe.web_form.validate = () => {
		const careerGoal = frappe.web_form.get_value("final_chosen_career_goal");
		const vision = frappe.web_form.get_value("personal_vision_statement");
		const dateDecision = frappe.web_form.get_value("date_of_decision");

		if (!careerGoal) {
			frappe.msgprint({
				title: __("Validation Error"),
				message: __("Please select your Final Chosen Career Goal."),
				indicator: "red"
			});
			return false;
		}

		if (!vision || !vision.trim()) {
			frappe.msgprint({
				title: __("Validation Error"),
				message: __("Please enter your Personal Vision Statement."),
				indicator: "red"
			});
			return false;
		}

		if (!dateDecision) {
			frappe.msgprint({
				title: __("Validation Error"),
				message: __("Please enter the Date of Decision."),
				indicator: "red"
			});
			return false;
		}

		return true;
	};
});
