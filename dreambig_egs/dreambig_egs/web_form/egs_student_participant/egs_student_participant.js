frappe.ready(function() {
    var city_institution_cache = {};

    // 1. City-to-Institution Dynamic Autocomplete Filter
    function init_city_filter() {
        if (!window.frappe || !frappe.web_form || !frappe.web_form.fields_dict) {
            setTimeout(init_city_filter, 100);
            return;
        }

        var city_ctrl = frappe.web_form.get_field('city');
        var inst_ctrl = frappe.web_form.get_field('university_college');

        if (!city_ctrl || !inst_ctrl || !city_ctrl.$input || !inst_ctrl.$input) {
            setTimeout(init_city_filter, 100);
            return;
        }

        var query_config = function() {
            var selected_city = frappe.web_form.get_value('city');
            return {
                query: 'dreambig_egs.dreambig_egs.doctype.egs_institution.egs_institution.get_institutions_by_city',
                params: {
                    city: selected_city || ''
                }
            };
        };

        inst_ctrl.get_query = query_config;
        if (inst_ctrl.df) {
            inst_ctrl.df.get_query = query_config;
        }

        function apply_institutions(city, list) {
            inst_ctrl.set_data(list || []);
            if (!list || list.length === 0) {
                inst_ctrl.set_description(__('No registered institutions found for ') + city + '.');
                frappe.msgprint({
                    title: __('Institution Notice'),
                    message: __('No registered institutions found for "{0}". Please contact your coordinator if your institution is not listed.', [city]),
                    indicator: 'orange'
                });
            } else {
                inst_ctrl.set_description(__('Found {0} institution(s) for {1}.', [list.length, city]));
            }
        }

        function update_institutions(selected_city, keep_value) {
            if (!keep_value) {
                frappe.web_form.set_value('university_college', '');
            }

            if (!selected_city) {
                inst_ctrl.set_data([]);
                inst_ctrl.set_description(__('Please select a City first.'));
                return;
            }

            if (city_institution_cache[selected_city]) {
                var cached_list = city_institution_cache[selected_city];
                apply_institutions(selected_city, cached_list);
                return;
            }

            frappe.call({
                method: 'dreambig_egs.dreambig_egs.doctype.egs_institution.egs_institution.get_institutions_by_city',
                args: {
                    city: selected_city
                },
                callback: function(r) {
                    var institutions = r.message || [];
                    city_institution_cache[selected_city] = institutions;
                    if (frappe.web_form.get_value('city') === selected_city) {
                        apply_institutions(selected_city, institutions);
                    }
                },
                error: function() {
                    inst_ctrl.set_data([]);
                    inst_ctrl.set_description(__('Error loading institutions. Please try again.'));
                }
            });
        }

        city_ctrl.$input.off('change.city_filter').on('change.city_filter', function() {
            var new_city = $(this).val();
            update_institutions(new_city, false);
        });

        if (frappe.web_form.on) {
            frappe.web_form.on('city', function(field, val) {
                update_institutions(val, false);
            });
        }

        inst_ctrl.$input.off('focus.city_check').on('focus.city_check', function() {
            var city = frappe.web_form.get_value('city');
            if (!city) {
                inst_ctrl.set_data([]);
                inst_ctrl.set_description(__('Please select a City first.'));
                frappe.msgprint({
                    title: __('Notice'),
                    message: __('Please select a City before choosing an Institution.'),
                    indicator: 'blue'
                });
            }
        });

        var initial_city = frappe.web_form.get_value('city');
        if (initial_city) {
            update_institutions(initial_city, true);
        } else {
            inst_ctrl.set_data([]);
            inst_ctrl.set_description(__('Please select a City first.'));
        }
    }

    init_city_filter();

    // 2. City-to-Event Dynamic Filter & Auto-assignment
    function init_event_filter() {
        if (!window.frappe || !frappe.web_form || !frappe.web_form.fields_dict) {
            setTimeout(init_event_filter, 100);
            return;
        }

        var city_ctrl = frappe.web_form.get_field('city');
        var event_ctrl = frappe.web_form.get_field('event');
        if (!event_ctrl || !event_ctrl.$input) {
            setTimeout(init_event_filter, 100);
            return;
        }

        var city_event_cache = {};

        var event_query_config = function() {
            var selected_city = frappe.web_form.get_value('city');
            return {
                query: 'dreambig_egs.dreambig_egs.doctype.egs_event.egs_event.get_events_query',
                params: {
                    city: selected_city || ''
                }
            };
        };

        event_ctrl.get_query = event_query_config;
        if (event_ctrl.df) {
            event_ctrl.df.get_query = event_query_config;
        }

        var original_set_data = event_ctrl.set_data ? event_ctrl.set_data.bind(event_ctrl) : null;
        if (original_set_data) {
            event_ctrl.set_data = function(data) {
                original_set_data(data);
                if (this.awesomplete && this.$input && this.$input.is(':focus')) {
                    this.awesomplete.evaluate();
                    this.awesomplete.open();
                }
            };
        }

        if (event_ctrl.awesomplete) {
            event_ctrl.awesomplete.item = function(item) {
                var d = this.get_item(item.value) || item;
                var eventName = d.label || d.event_name || d.value;
                var eventDate = d.formatted_date || d.event_date || '';
                var venue = d.venue || '';

                var meta_parts = [];
                if (eventDate) {
                    meta_parts.push('<span style="color: #4b5563;"><i class="fa fa-calendar text-primary" style="margin-right: 4px;"></i>' + frappe.utils.escape_html(eventDate) + '</span>');
                }
                if (venue) {
                    meta_parts.push('<span style="color: #4b5563;"><i class="fa fa-map-marker text-danger" style="margin-right: 4px;"></i>' + frappe.utils.escape_html(venue) + '</span>');
                }
                var meta_html = meta_parts.join(' <span style="color: #9ca3af; margin: 0 4px;">&bull;</span> ');

                var html = '<div class="py-1" style="line-height: 1.3;">'
                    + '<div class="fw-bold text-dark" style="font-size: 0.95rem;">' + frappe.utils.escape_html(eventName) + '</div>';
                if (meta_html) {
                    html += '<div class="mt-1" style="font-size: 0.82rem;">' + meta_html + '</div>';
                }
                html += '</div>';

                return $('<li></li>')
                    .data('item.autocomplete', d)
                    .prop('aria-selected', 'false')
                    .html('<a>' + html + '</a>')
                    .get(0);
            };

            event_ctrl.awesomplete.filter = function(item, input) {
                var d = this.get_item(item.value) || item;
                var haystack = [
                    d.label || '',
                    d.value || '',
                    d.event_name || '',
                    d.formatted_date || '',
                    d.event_date || '',
                    d.venue || '',
                    d.description || ''
                ].join(' ').toLowerCase();
                return haystack.indexOf((input || '').toLowerCase()) !== -1;
            };
        }

        function update_selected_event_description() {
            var selected_val = frappe.web_form.get_value('event');
            var selected_city = frappe.web_form.get_value('city');
            if (!selected_val) return;
            var cached = city_event_cache[selected_city] || [];
            var found = cached.find(function(e) { return (e.value === selected_val || e.name === selected_val); });
            if (found) {
                var details = [];
                var d_date = found.formatted_date || found.event_date;
                var d_venue = found.venue;
                if (d_date) details.push('📅 ' + d_date);
                if (d_venue) details.push('📍 ' + d_venue);
                var detail_str = details.length ? ' (' + details.join(' | ') + ')' : '';
                event_ctrl.set_description(__('Selected Event: {0}{1}', [found.label || found.event_name || found.name, detail_str]));
            }
        }

        event_ctrl.$input.off('awesomplete-selectcomplete.show_details change.show_details').on('awesomplete-selectcomplete.show_details change.show_details', function() {
            update_selected_event_description();
        });

        function apply_events(selected_city, events, auto_select, open_dropdown) {
            if (event_ctrl.set_data) {
                event_ctrl.set_data(events);
            }
            if (!events || events.length === 0) {
                event_ctrl.set_description(__('No open events currently found for ') + selected_city + '.');
                if (auto_select) {
                    frappe.web_form.set_value('event', '');
                }
            } else if (events.length === 1) {
                var single_event = events[0];
                var event_val = single_event.value || single_event.name;
                var event_lbl = single_event.label || single_event.event_name || event_val;
                var event_date = single_event.formatted_date || single_event.event_date || '';
                var event_venue = single_event.venue || '';

                var details = [];
                if (event_date) details.push('📅 ' + event_date);
                if (event_venue) details.push('📍 ' + event_venue);
                var detail_str = details.length ? ' (' + details.join(' | ') + ')' : '';

                if (auto_select) {
                    frappe.web_form.set_value('event', event_val);
                    event_ctrl.set_description(__('Assigned to: {0}{1}', [event_lbl, detail_str]));
                } else {
                    event_ctrl.set_description(__('1 open event available in {0}{1}.', [selected_city, detail_str]));
                }
            } else {
                event_ctrl.set_description(__('Found {0} open event(s) in {1}. Please select one from the dropdown.', [events.length, selected_city]));
                if (auto_select) {
                    frappe.web_form.set_value('event', '');
                }
            }

            if (open_dropdown && event_ctrl.awesomplete) {
                event_ctrl.awesomplete.evaluate();
                event_ctrl.awesomplete.open();
            }
        }

        function update_events(selected_city, auto_select, open_dropdown) {
            if (!selected_city) {
                if (event_ctrl.set_data) event_ctrl.set_data([]);
                event_ctrl.set_description(__('Please select a City first.'));
                frappe.web_form.set_value('event', '');
                return;
            }

            if (city_event_cache[selected_city]) {
                apply_events(selected_city, city_event_cache[selected_city], auto_select, open_dropdown);
                return;
            }

            frappe.call({
                method: 'dreambig_egs.dreambig_egs.doctype.egs_event.egs_event.get_open_events_by_city',
                args: { city: selected_city },
                callback: function(r) {
                    var events = r.message || [];
                    city_event_cache[selected_city] = events;
                    if (frappe.web_form.get_value('city') === selected_city) {
                        apply_events(selected_city, events, auto_select, open_dropdown);
                    }
                },
                error: function() {
                    if (event_ctrl.set_data) event_ctrl.set_data([]);
                    event_ctrl.set_description(__('Error loading events for ') + selected_city + '.');
                }
            });
        }

        function trigger_open() {
            var selected_city = frappe.web_form.get_value('city');
            if (!selected_city) {
                event_ctrl.set_description(__('Please select a City first.'));
                frappe.msgprint({
                    title: __('Notice'),
                    message: __('Please select a City before choosing an Event.'),
                    indicator: 'blue'
                });
                return;
            }
            if (city_event_cache[selected_city]) {
                apply_events(selected_city, city_event_cache[selected_city], false, true);
            } else {
                update_events(selected_city, false, true);
            }
        }

        event_ctrl.$input.off('click.event_open focus.event_open').on('click.event_open focus.event_open', function() {
            trigger_open();
        });

        event_ctrl.$input.off('input.event_clear').on('input.event_clear', function() {
            if (!$(this).val()) {
                var selected_city = frappe.web_form.get_value('city');
                if (selected_city && city_event_cache[selected_city]) {
                    apply_events(selected_city, city_event_cache[selected_city], false, true);
                }
            }
        });

        city_ctrl.$input.off('change.event_filter').on('change.event_filter', function() {
            var new_city = $(this).val();
            update_events(new_city, true, false);
        });

        if (frappe.web_form.on) {
            frappe.web_form.on('city', function(field, val) {
                update_events(val, true, false);
            });
        }

        var initial_city = frappe.web_form.get_value('city');
        if (initial_city) {
            var current_event = frappe.web_form.get_value('event');
            update_events(initial_city, !current_event, false);
        } else {
            if (event_ctrl.set_data) event_ctrl.set_data([]);
            event_ctrl.set_description(__('Please select a City first.'));
        }
    }

    init_event_filter();

    // 3. NEW: Faculty-to-Course Dynamic Filter
    function init_course_filter() {
        if (!window.frappe || !frappe.web_form || !frappe.web_form.fields_dict) {
            setTimeout(init_course_filter, 100);
            return;
        }

        var faculty_ctrl = frappe.web_form.get_field('faculty_department');
        var course_ctrl = frappe.web_form.get_field('course');

        if (!faculty_ctrl || !course_ctrl || !course_ctrl.$input) return;

        function update_courses(faculty_val) {
             if (!faculty_val) {
                 frappe.web_form.set_df_property('course', 'hidden', 1);
                 if (course_ctrl.set_data) course_ctrl.set_data([]);
                 frappe.web_form.set_value('course', '');
                 return;
             }

             frappe.web_form.set_df_property('course', 'hidden', 0);
             
             // NEW: Always clear the old course selection when faculty changes
             frappe.web_form.set_value('course', ''); 
             
             frappe.call({
                 method: 'dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant.get_courses_by_faculty',
                 args: { faculty: faculty_val },
                 callback: function(r) {
                     var courses = r.message || [];
                     if (course_ctrl.set_data) {
                         course_ctrl.set_data(courses);
                     }
                     if (courses.length === 0) {
                         course_ctrl.set_description(__('No courses found for this faculty.'));
                     } else {
                         course_ctrl.set_description(__('Select a course.'));
                     }
                 }
             });
         }

        // Trigger when user changes the faculty dropdown
        if (faculty_ctrl.$input) {
            faculty_ctrl.$input.off('change.faculty_filter').on('change.faculty_filter', function() {
                update_courses($(this).val());
            });
        }
        if (frappe.web_form.on) {
            frappe.web_form.on('faculty_department', function(field, val) {
                update_courses(val);
            });
        }

        // Force dropdown open on click so they see the filtered list instantly
        course_ctrl.$input.off('click.course_open focus.course_open').on('click.course_open focus.course_open', function() {
            var fac = frappe.web_form.get_value('faculty_department');
            if (!fac) {
                frappe.msgprint({ title: __('Notice'), message: __('Please select a Faculty first.'), indicator: 'blue' });
            } else if (course_ctrl.awesomplete) {
                course_ctrl.awesomplete.evaluate();
                course_ctrl.awesomplete.open();
            }
        });

        // Initialize on page load
        var initial_faculty = frappe.web_form.get_value('faculty_department');
        update_courses(initial_faculty);
    }

    init_course_filter();

    // 4. Web Form Form Validation
    frappe.web_form.validate = function() {
        var phone = frappe.web_form.get_value('phone_number');
        var guardianPhone = frappe.web_form.get_value('guardian_phone_number');
        var cleanPhone = phone ? String(phone).trim() : '';
        var cleanGuardian = guardianPhone ? String(guardianPhone).trim() : '';
        var tenDigitRegex = /^\d{10}$/;

        if (!cleanPhone || !tenDigitRegex.test(cleanPhone)) {
            frappe.msgprint({
                title: __('Validation Error'),
                message: __('Student Phone Number must be exactly 10 digits.'),
                indicator: 'red'
            });
            return false;
        }

        if (!cleanGuardian || !tenDigitRegex.test(cleanGuardian)) {
            frappe.msgprint({
                title: __('Validation Error'),
                message: __('Guardian Phone Number must be exactly 10 digits.'),
                indicator: 'red'
            });
            return false;
        }

        if (cleanPhone === cleanGuardian) {
            frappe.msgprint({
                title: __('Validation Error'),
                message: __('Student Phone Number and Guardian Phone Number cannot be identical.'),
                indicator: 'red'
            });
            return false;
        }

        var city = frappe.web_form.get_value('city');
        var inst = frappe.web_form.get_value('university_college');
        var faculty = frappe.web_form.get_value('faculty_department');
        var course = frappe.web_form.get_value('course');

        if (!city) {
            frappe.msgprint({ title: __('Validation Error'), message: __('Please select a City.'), indicator: 'red' });
            return false;
        }
        if (!inst) {
            frappe.msgprint({ title: __('Validation Error'), message: __('Please select an Institution.'), indicator: 'red' });
            return false;
        }
        if (!faculty) {
            frappe.msgprint({ title: __('Validation Error'), message: __('Please select your Faculty / Department.'), indicator: 'red' });
            return false;
        }
        if (!course) {
            frappe.msgprint({ title: __('Validation Error'), message: __('Please select your Course.'), indicator: 'red' });
            return false;
        }

        return true;
    };
});
