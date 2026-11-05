frappe.ready(function () {
	// Dynamically filter university_college Link field to only show institutions in the selected city
	frappe.web_form.set_query("university_college", function () {
		const selectedCity = frappe.web_form.get_value("city");
		return {
			filters: selectedCity ? { city: selectedCity } : {}
		};
	});

	// Reset university_college if city changes
	frappe.web_form.on("city", (field, value) => {
		frappe.web_form.set_value("university_college", "");
	});

	// Form submission validation
	frappe.web_form.validate = () => {
		const phone = frappe.web_form.get_value("phone_number");
		const guardianPhone = frappe.web_form.get_value("guardian_phone_number");

		const cleanPhone = phone ? String(phone).trim() : "";
		const cleanGuardian = guardianPhone ? String(guardianPhone).trim() : "";

		const tenDigitRegex = /^\d{10}$/;

		// 1. Check Student Phone Number is exactly 10 digits
		if (!cleanPhone || !tenDigitRegex.test(cleanPhone)) {
			frappe.msgprint({
				title: __("Validation Error"),
				message: __("Student Phone Number must be exactly 10 digits."),
				indicator: "red"
			});
			return false;
		}

		// 2. Check Guardian Phone Number is exactly 10 digits
		if (!cleanGuardian || !tenDigitRegex.test(cleanGuardian)) {
			frappe.msgprint({
				title: __("Validation Error"),
				message: __("Guardian Phone Number must be exactly 10 digits."),
				indicator: "red"
			});
			return false;
		}

		// 3. Check they are not identical
		if (cleanPhone === cleanGuardian) {
			frappe.msgprint({
				title: __("Validation Error"),
				message: __("Student Phone Number and Guardian Phone Number cannot be identical."),
				indicator: "red"
			});
			return false;
		}

		return true;
	};
});
