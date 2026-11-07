frappe.ready(function() {
    const urlParams = new URLSearchParams(window.location.search);
    const studentId = urlParams.get('id');
    const token = urlParams.get('key');

    if (!studentId || !token) {
        $('.web-form-wrapper, .web-form-container').hide(); 
        
        const login_ui = `
            <div class="card shadow-sm" style="max-width: 450px; margin: 50px auto; border-radius: 12px;">
                <div class="card-body text-center p-5" id="step_email">
                    <h4 class="mb-3">Access Your Dashboard</h4>
                    <p class="text-muted mb-4">Enter your registered email to receive your Magic Link and OTP.</p>
                    <input type="email" id="login_email" class="form-control form-control-lg mb-3" placeholder="Student Email">
                    <button id="send_creds_btn" class="btn btn-primary btn-lg w-100">Send Login Details</button>
                    <div id="email_msg" class="mt-3 font-weight-bold" style="display:none;"></div>
                </div>
                
                <div class="card-body text-center p-5" id="step_otp" style="display:none;">
                    <h4 class="mb-3">Enter OTP</h4>
                    <p class="text-muted mb-4">We sent a 6-digit code and a Magic Link to your email.</p>
                    <input type="text" id="login_otp" class="form-control form-control-lg mb-3 text-center" placeholder="123456" maxlength="6">
                    <button id="verify_otp_btn" class="btn btn-success btn-lg w-100">Verify & Login</button>
                    <div id="otp_msg" class="mt-3 font-weight-bold" style="display:none;"></div>
                    <button id="back_to_email_btn" class="btn btn-link mt-3 w-100">Back</button>
                </div>
            </div>
        `;
        $('.page-content, .page_content').prepend(login_ui);

        let user_email = "";

        $('#send_creds_btn').on('click', function() {
            user_email = $('#login_email').val().trim();
            if (!user_email) {
                $('#email_msg').removeClass('text-success').addClass('text-danger').text('Please enter your email.').show();
                return;
            }
            $(this).prop('disabled', true).text('Sending...');
            
            frappe.call({
                method: 'dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant.send_login_credentials',
                args: { email: user_email },
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        $('#step_email').hide();
                        $('#step_otp').show();
                    } else {
                        $('#email_msg').removeClass('text-success').addClass('text-danger').text(r.message ? r.message.message : 'Error finding email.').show();
                        $('#send_creds_btn').prop('disabled', false).text('Send Login Details');
                    }
                }
            });
        });

        $('#verify_otp_btn').on('click', function() {
            let otp_val = $('#login_otp').val().trim();
            if (!otp_val) return;
            
            $(this).prop('disabled', true).text('Verifying...');
            
            frappe.call({
                method: 'dreambig_egs.dreambig_egs.doctype.egs_student_participant.egs_student_participant.verify_login_otp',
                args: { email: user_email, otp: otp_val },
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        $('#otp_msg').removeClass('text-danger').addClass('text-success').text('Success! Logging you in...').show();
                        // Automatically reload page with credentials
                        window.location.href = window.location.pathname + "?id=" + r.message.id + "&key=" + r.message.key;
                    } else {
                        $('#otp_msg').removeClass('text-success').addClass('text-danger').text(r.message ? r.message.message : 'Invalid OTP.').show();
                        $('#verify_otp_btn').prop('disabled', false).text('Verify & Login');
                    }
                }
            });
        });

        $('#back_to_email_btn').on('click', function() {
            $('#step_otp').hide();
            $('#step_email').show();
            $('#send_creds_btn').prop('disabled', false).text('Send Login Details');
            $('#login_otp').val('');
        });

        return; 
    }

    // Client-side events for EGS Check-in Log Web Form
});
