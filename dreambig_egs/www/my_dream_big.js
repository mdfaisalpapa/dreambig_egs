// Copyright (c) 2026, Dream Big and contributors
// For license information, please see license.txt

(function init_dashboard_tabs_and_modals() {
    const rootEl = document.querySelector('.dream-big-dashboard');
    const studentId = rootEl ? rootEl.getAttribute('data-student-id') : (window.studentId || "");
    const token = rootEl ? rootEl.getAttribute('data-access-key') : (window.accessKey || "");

    // Tab Switching Support (Bootstrap 4, Bootstrap 5, and vanilla fallback)
    const tabButtons = document.querySelectorAll('#pills-tab button, #pills-tab a');
    tabButtons.forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const targetSelector = btn.getAttribute('data-target') || btn.getAttribute('data-bs-target') || btn.getAttribute('href');
            if (!targetSelector) return;

            tabButtons.forEach(function(b) {
                b.classList.remove('active', 'bg-primary', 'text-white', 'shadow-sm', 'font-weight-bold');
                b.classList.add('bg-light');
                b.setAttribute('aria-selected', 'false');
            });
            btn.classList.add('active', 'bg-primary', 'text-white', 'shadow-sm', 'font-weight-bold');
            btn.classList.remove('bg-light');
            btn.setAttribute('aria-selected', 'true');

            const tabPanes = document.querySelectorAll('#pills-tabContent .tab-pane');
            tabPanes.forEach(function(pane) {
                pane.classList.remove('show', 'active');
            });
            const activePane = document.querySelector(targetSelector);
            if (activePane) {
                activePane.classList.add('show', 'active');
            }
        });
    });

    // Modal Helpers
    function openModal(el) {
        if (!el) return;
        if (typeof $ !== 'undefined' && typeof $(el).modal === 'function') {
            $(el).modal('show');
        } else if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            bootstrap.Modal.getOrCreateInstance(el).show();
        } else {
            el.classList.add('show');
            el.style.display = 'block';
            el.removeAttribute('aria-hidden');
            el.setAttribute('aria-modal', 'true');
            if (!document.querySelector('.modal-backdrop')) {
                const backdrop = document.createElement('div');
                backdrop.className = 'modal-backdrop fade show';
                document.body.appendChild(backdrop);
            }
        }
    }

    function closeModal(el) {
        if (!el) return;
        if (typeof $ !== 'undefined' && typeof $(el).modal === 'function') {
            $(el).modal('hide');
        } else if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            const inst = bootstrap.Modal.getInstance(el);
            if (inst) inst.hide();
        } else {
            el.classList.remove('show');
            el.style.display = 'none';
            el.setAttribute('aria-hidden', 'true');
            el.removeAttribute('aria-modal');
            const backdrop = document.querySelector('.modal-backdrop');
            if (backdrop) backdrop.remove();
        }
    }

    // Modal dismiss helper
    document.querySelectorAll('.modal').forEach(function(modalEl) {
        modalEl.querySelectorAll('[data-dismiss="modal"], [data-bs-dismiss="modal"]').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                closeModal(modalEl);
            });
        });
    });

    // 0. Open DECIDE Modal Logic
    const openDecideBtns = document.querySelectorAll('#btn-open-decide-modal, #btn-update-decide-modal');
    const decideModalEl = document.getElementById('decideModal');
    if (openDecideBtns.length && decideModalEl) {
        openDecideBtns.forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                openModal(decideModalEl);
            });
        });
    }

    // 1. Advance to Stage 4: DEVELOP
    const advanceBtn = document.getElementById('btn-advance-develop');
    if (advanceBtn) {
        advanceBtn.addEventListener('click', function(e) {
            e.preventDefault();
            advanceBtn.disabled = true;
            advanceBtn.innerText = "Advancing...";

            frappe.call({
                method: "dreambig_egs.api.advance_to_develop",
                args: {
                    student_id: studentId,
                    token: token
                },
                callback: function(r) {
                    advanceBtn.disabled = false;
                    advanceBtn.innerText = "🚀 Proceed to Stage 4: DEVELOP";

                    if (r.message && r.message.status === 'success') {
                        frappe.show_alert({
                            message: r.message.message,
                            indicator: 'green'
                        }, 4);
                        setTimeout(function() {
                            window.location.reload();
                        }, 800);
                    } else {
                        frappe.show_alert({
                            message: r.message ? r.message.message : "Failed to advance to DEVELOP stage.",
                            indicator: 'red'
                        }, 4);
                    }
                },
                error: function(err) {
                    advanceBtn.disabled = false;
                    advanceBtn.innerText = "🚀 Proceed to Stage 4: DEVELOP";
                    frappe.show_alert({
                        message: "An error occurred. Please try again.",
                        indicator: 'red'
                    }, 4);
                }
            });
        });
    }

    // 2. Add Commitment Modal Logic
    const openCommitmentBtn = document.getElementById('btn-open-commitment-modal');
    const commitmentModalEl = document.getElementById('addCommitmentModal');
    const saveCommitmentBtn = document.getElementById('btn-save-commitment');
    const commitmentAlertBox = document.getElementById('commitment-modal-alert');
    const actionRequiredInput = document.getElementById('commitment_action_required');
    const dueDateInput = document.getElementById('commitment_due_date');
    const statusInput = document.getElementById('commitment_status');
    const barrierInput = document.getElementById('commitment_reported_barrier');

    if (openCommitmentBtn && commitmentModalEl) {
        openCommitmentBtn.addEventListener('click', function(e) {
            e.preventDefault();
            openModal(commitmentModalEl);
        });
    }

    if (saveCommitmentBtn && actionRequiredInput && dueDateInput) {
        saveCommitmentBtn.addEventListener('click', function() {
            const action = actionRequiredInput.value.trim();
            const dueDate = dueDateInput.value;
            const status = statusInput ? statusInput.value : 'Pending';
            const barrier = barrierInput ? barrierInput.value.trim() : '';

            if (!action) {
                commitmentAlertBox.className = 'alert alert-danger mb-3 py-2';
                commitmentAlertBox.innerText = "Please enter the Action Required.";
                commitmentAlertBox.classList.remove('d-none');
                return;
            }

            if (!dueDate) {
                commitmentAlertBox.className = 'alert alert-danger mb-3 py-2';
                commitmentAlertBox.innerText = "Please specify a Due Date.";
                commitmentAlertBox.classList.remove('d-none');
                return;
            }

            saveCommitmentBtn.disabled = true;
            saveCommitmentBtn.innerText = "Saving...";
            commitmentAlertBox.className = 'alert d-none mb-3 py-2';

            frappe.call({
                method: "dreambig_egs.api.add_egs_commitment",
                args: {
                    student_id: studentId,
                    token: token,
                    data: {
                        action_required: action,
                        due_date: dueDate,
                        status: status,
                        reported_barrier: barrier
                    }
                },
                callback: function(r) {
                    saveCommitmentBtn.disabled = false;
                    saveCommitmentBtn.innerText = "Save Commitment";

                    if (r.message && r.message.status === 'success') {
                        commitmentAlertBox.className = 'alert alert-success mb-3 py-2';
                        commitmentAlertBox.innerText = r.message.message;
                        commitmentAlertBox.classList.remove('d-none');

                        frappe.show_alert({
                            message: r.message.message,
                            indicator: 'green'
                        }, 4);

                        setTimeout(function() {
                            window.location.reload();
                        }, 800);
                    } else {
                        commitmentAlertBox.className = 'alert alert-danger mb-3 py-2';
                        commitmentAlertBox.innerText = r.message ? r.message.message : "Failed to add commitment.";
                        commitmentAlertBox.classList.remove('d-none');
                    }
                },
                error: function(err) {
                    saveCommitmentBtn.disabled = false;
                    saveCommitmentBtn.innerText = "Save Commitment";
                    commitmentAlertBox.className = 'alert alert-danger mb-3 py-2';
                    commitmentAlertBox.innerText = "An error occurred. Please try again.";
                    commitmentAlertBox.classList.remove('d-none');
                }
            });
        });
    }

    function showConfirm(msg, onYes, onNo) {
        if (typeof frappe !== 'undefined' && typeof frappe.confirm === 'function') {
            frappe.confirm(msg, onYes, onNo);
        } else {
            if (window.confirm(msg)) {
                onYes();
            } else if (onNo) {
                onNo();
            }
        }
    }

    // 3. Return from DEVELOP to DECIDE
    const revertToDecideBtn = document.getElementById('btn-revert-to-decide');
    if (revertToDecideBtn) {
        revertToDecideBtn.addEventListener('click', function(e) {
            e.preventDefault();
            revertToDecideBtn.disabled = true;
            showConfirm(
                "Are you sure you want to step back? This will clear your current stage data.",
                function() {
                    revertToDecideBtn.disabled = true;
                    revertToDecideBtn.innerText = "Returning to DECIDE...";

                    frappe.call({
                        method: "dreambig_egs.api.step_back_stage",
                        args: {
                            student_id: studentId,
                            token: token,
                            target_stage: "DECIDE"
                        },
                        callback: function(r) {
                            revertToDecideBtn.disabled = false;
                            revertToDecideBtn.innerText = "🔄 Return to Stage 3: DECIDE";

                            if (r.message && r.message.status === 'success') {
                                frappe.show_alert({
                                    message: r.message.message,
                                    indicator: 'green'
                                }, 4);
                                setTimeout(function() {
                                    window.location.reload();
                                }, 800);
                            } else {
                                frappe.show_alert({
                                    message: r.message ? r.message.message : "Failed to return to DECIDE stage.",
                                    indicator: 'red'
                                }, 4);
                            }
                        },
                        error: function() {
                            revertToDecideBtn.disabled = false;
                            revertToDecideBtn.innerText = "🔄 Return to Stage 3: DECIDE";
                            frappe.show_alert({
                                message: "An error occurred. Please try again.",
                                indicator: 'red'
                            }, 4);
                        }
                    });
                },
                function() {
                    revertToDecideBtn.disabled = false;
                }
            );
        });
    }

    // 4. Advance to Stage 5: DELIVER
    const advanceDeliverBtn = document.getElementById('btn-advance-deliver');
    if (advanceDeliverBtn) {
        advanceDeliverBtn.addEventListener('click', function(e) {
            e.preventDefault();
            advanceDeliverBtn.disabled = true;
            advanceDeliverBtn.innerText = "Advancing...";

            frappe.call({
                method: "dreambig_egs.api.advance_to_deliver",
                args: {
                    student_id: studentId,
                    token: token
                },
                callback: function(r) {
                    advanceDeliverBtn.disabled = false;
                    advanceDeliverBtn.innerText = "🚀 Proceed to Stage 5: DELIVER";

                    if (r.message && r.message.status === 'success') {
                        frappe.show_alert({
                            message: r.message.message,
                            indicator: 'green'
                        }, 4);
                        setTimeout(function() {
                            window.location.reload();
                        }, 800);
                    } else {
                        frappe.show_alert({
                            message: r.message ? r.message.message : "Failed to advance to DELIVER stage.",
                            indicator: 'red'
                        }, 4);
                    }
                },
                error: function() {
                    advanceDeliverBtn.disabled = false;
                    advanceDeliverBtn.innerText = "🚀 Proceed to Stage 5: DELIVER";
                    frappe.show_alert({
                        message: "An error occurred. Please try again.",
                        indicator: 'red'
                    }, 4);
                }
            });
        });
    }

    // 5. Return from DELIVER to DEVELOP
    const revertToDevelopBtn = document.getElementById('btn-revert-to-develop');
    if (revertToDevelopBtn) {
        revertToDevelopBtn.addEventListener('click', function(e) {
            e.preventDefault();
            revertToDevelopBtn.disabled = true;
            showConfirm(
                "Are you sure you want to step back? This will clear your current stage data.",
                function() {
                    revertToDevelopBtn.disabled = true;
                    revertToDevelopBtn.innerText = "Returning to DEVELOP...";

                    frappe.call({
                        method: "dreambig_egs.api.step_back_stage",
                        args: {
                            student_id: studentId,
                            token: token,
                            target_stage: "DEVELOP/PREPARE"
                        },
                        callback: function(r) {
                            revertToDevelopBtn.disabled = false;
                            revertToDevelopBtn.innerText = "🔄 Return to Stage 4: DEVELOP";

                            if (r.message && r.message.status === 'success') {
                                frappe.show_alert({
                                    message: r.message.message,
                                    indicator: 'green'
                                }, 4);
                                setTimeout(function() {
                                    window.location.reload();
                                }, 800);
                            } else {
                                frappe.show_alert({
                                    message: r.message ? r.message.message : "Failed to return to DEVELOP stage.",
                                    indicator: 'red'
                                }, 4);
                            }
                        },
                        error: function() {
                            revertToDevelopBtn.disabled = false;
                            revertToDevelopBtn.innerText = "🔄 Return to Stage 4: DEVELOP";
                            frappe.show_alert({
                                message: "An error occurred. Please try again.",
                                indicator: 'red'
                            }, 4);
                        }
                    });
                },
                function() {
                    revertToDevelopBtn.disabled = false;
                }
            );
        });
    }
})();
