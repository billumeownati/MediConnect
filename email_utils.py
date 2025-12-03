from flask_mail import Message
from models import mail
from flask import url_for
from datetime import datetime

def send_email(subject, recipients, html_body):
    """Generic helper to send emails with error handling."""
    try:
        msg = Message(subject, recipients=recipients, html=html_body)
        mail.send(msg)
    except Exception as e:
        print(f"Error sending email: {e}")

def get_common_style():
    """Returns the CSS style block used in all emails."""
    return """
        <style>
            body { font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 0; }
            .container { max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
            .header { color: #ffffff; padding: 20px; text-align: center; }
            .content { padding: 30px; color: #333333; line-height: 1.6; }
            .info-box { background-color: #f8f9fa; border-left: 4px solid; padding: 15px; margin: 20px 0; }
            .footer { background-color: #eeeeee; padding: 15px; text-align: center; font-size: 12px; color: #777777; }
            .btn { display: inline-block; padding: 10px 20px; color: #ffffff; text-decoration: none; border-radius: 5px; margin-top: 20px; }
        </style>
    """

def send_admin_creation_email(email, password):
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>{get_common_style()}</head>
    <body>
        <div class="container">
            <div class="header" style="background-color: #007bff;">
                <h1>MediConnect Admin</h1>
            </div>
            <div class="content">
                <p>Hello Admin,</p>
                <p>Your administrator account has been successfully initialized.</p>
                <div class="info-box" style="border-color: #007bff;">
                    <p><strong>Email:</strong> {email}</p>
                    <p><strong>Password:</strong> {password}</p>
                </div>
                <p><strong>Security Warning:</strong> Please login and change your password immediately.</p>
            </div>
            <div class="footer">&copy; {datetime.now().year} MediConnect.</div>
        </div>
    </body>
    </html>
    """
    send_email("Action Required: Admin Account Created", [email], html_body)

def send_doctor_credentials_email(full_name, email, password):
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>{get_common_style()}</head>
    <body>
        <div class="container">
            <div class="header" style="background-color: #007bff;">
                <h1>MediConnect Doctor</h1>
            </div>
            <div class="content">
                <p>Hello Dr. {full_name},</p>
                <p>Welcome to the team! Your doctor account has been created.</p>
                <div class="info-box" style="border-color: #007bff;">
                    <p><strong>Login Email:</strong> {email}</p>
                    <p><strong>Temporary Password:</strong> {password}</p>
                </div>
                <p>Please login to your dashboard and change your password immediately.</p>
            </div>
            <div class="footer">&copy; {datetime.now().year} MediConnect.</div>
        </div>
    </body>
    </html>
    """
    send_email("MediConnect - Doctor Account Credentials", [email], html_body)

def send_welcome_email(full_name, email):
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>{get_common_style()}</head>
    <body>
        <div class="container">
            <div class="header" style="background-color: #007bff;">
                <h1>Welcome to MediConnect!</h1>
            </div>
            <div class="content">
                <p>Hello {full_name},</p>
                <p>Thank you for registering. Your account has been created successfully.</p>
                <p style="text-align: center;">
                    <a href="{url_for('mediconnect.login', _external=True)}" class="btn" style="background-color: #007bff;">Login Now</a>
                </p>
            </div>
            <div class="footer">&copy; {datetime.now().year} MediConnect.</div>
        </div>
    </body>
    </html>
    """
    send_email("Welcome to MediConnect", [email], html_body)

def send_otp_email(email, otp):
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>{get_common_style()}</head>
    <body>
        <div class="container">
            <div class="header" style="background-color: #007bff;">
                <h1>Password Reset</h1>
            </div>
            <div class="content">
                <p>Hello,</p>
                <p>Use the OTP below to reset your password. Valid for 10 minutes.</p>
                <div class="info-box" style="text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 5px; color: #007bff; border-color: #007bff;">
                    {otp}
                </div>
            </div>
            <div class="footer">&copy; {datetime.now().year} MediConnect.</div>
        </div>
    </body>
    </html>
    """
    send_email("MediConnect: Password Reset Verification", [email], html_body)

def send_appointment_booking_email(patient_email, patient_name, doctor_name, date, time, department):
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>{get_common_style()}</head>
    <body>
        <div class="container">
            <div class="header" style="background-color: #28a745;">
                <h1>Appointment Confirmed</h1>
            </div>
            <div class="content">
                <p>Hello {patient_name},</p>
                <p>Your appointment has been successfully booked.</p>
                <div class="info-box" style="border-color: #28a745; background-color: #f8f9fa;">
                    <p><strong>Doctor:</strong> Dr. {doctor_name}</p>
                    <p><strong>Department:</strong> {department}</p>
                    <p><strong>Date:</strong> {date}</p>
                    <p><strong>Time:</strong> {time}</p>
                </div>
                <p>Please arrive 15 minutes early.</p>
            </div>
            <div class="footer">&copy; {datetime.now().year} MediConnect.</div>
        </div>
    </body>
    </html>
    """
    send_email("Appointment Confirmed - MediConnect", [patient_email], html_body)

def send_appointment_reschedule_email(patient_email, patient_name, doctor_name, date, time):
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>{get_common_style()}</head>
    <body>
        <div class="container">
            <div class="header" style="background-color: #ffc107; color: #000;">
                <h1>Appointment Rescheduled</h1>
            </div>
            <div class="content">
                <p>Hello {patient_name},</p>
                <p>Your appointment has been rescheduled.</p>
                <div class="info-box" style="border-color: #ffc107; background-color: #fff3cd;">
                    <p><strong>Doctor:</strong> Dr. {doctor_name}</p>
                    <p><strong>New Date:</strong> {date}</p>
                    <p><strong>New Time:</strong> {time}</p>
                </div>
            </div>
            <div class="footer">&copy; {datetime.now().year} MediConnect.</div>
        </div>
    </body>
    </html>
    """
    send_email("Appointment Rescheduled - MediConnect", [patient_email], html_body)

def send_appointment_cancellation_email(patient_email, patient_name, date, time):
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>{get_common_style()}</head>
    <body>
        <div class="container">
            <div class="header" style="background-color: #dc3545;">
                <h1>Appointment Cancelled</h1>
            </div>
            <div class="content">
                <p>Hello {patient_name},</p>
                <p>Your appointment has been cancelled as requested.</p>
                <div class="info-box" style="border-color: #dc3545; background-color: #f8d7da;">
                    <p><strong>Scheduled Date:</strong> {date}</p>
                    <p><strong>Scheduled Time:</strong> {time}</p>
                </div>
            </div>
            <div class="footer">&copy; {datetime.now().year} MediConnect.</div>
        </div>
    </body>
    </html>
    """
    send_email("Appointment Cancelled - MediConnect", [patient_email], html_body)

def send_appointment_status_email(patient_email, patient_name, doctor_name, date, time, status):
    """Handles both Completed and Cancelled (by doctor) statuses."""
    if status == "Completed":
        header_text = "Appointment Completed"
        header_color = "#28a745" # Green
        box_bg = "#d4edda"
        msg_text = f"Your appointment with Dr. {doctor_name} is marked as completed."
    else:
        header_text = "Appointment Cancelled"
        header_color = "#dc3545" # Red
        box_bg = "#f8d7da"
        msg_text = f"Your appointment scheduled for {date} has been cancelled by the doctor."

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>{get_common_style()}</head>
    <body>
        <div class="container">
            <div class="header" style="background-color: {header_color};">
                <h1>{header_text}</h1>
            </div>
            <div class="content">
                <p>Hello {patient_name},</p>
                <p>{msg_text}</p>
                <div class="info-box" style="border-color: {header_color}; background-color: {box_bg};">
                    <p><strong>Doctor:</strong> Dr. {doctor_name}</p>
                    <p><strong>Date:</strong> {date}</p>
                    <p><strong>Time:</strong> {time}</p>
                </div>
            </div>
            <div class="footer">&copy; {datetime.now().year} MediConnect.</div>
        </div>
    </body>
    </html>
    """
    send_email(f"Appointment {status} - MediConnect", [patient_email], html_body)