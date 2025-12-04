from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, Admin, User, Patient, Doctor, Department, PasswordResetOTP, VerificationOTP
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import random
from email_utils import send_welcome_email, send_otp_email, send_verification_email
import dns.resolver
import re
import pyotp
import qrcode
import io
import base64

app_bp = Blueprint("mediconnect", __name__)

@app_bp.route('/')
def home():
    search_term = request.args.get('search', '').strip()
    search_by = request.args.get('search_by', 'name')
    show_all = request.args.get('show_all')

    doctors_query = Doctor.query.join(User).outerjoin(Department).filter(User.status == "active")

    if show_all:
        doctors = doctors_query.all()
    elif search_term:
        if search_by == "name":
            doctors_query = doctors_query.filter(User.full_name.ilike(f"%{search_term}%"))
        elif search_by == "department":
            doctors_query = doctors_query.filter(Department.name.ilike(f"%{search_term}%"))
        doctors = doctors_query.all()
    else:
        doctors = []

    return render_template(
        "home.html",
        doctors=doctors,
        search_term=search_term,
        search_by=search_by,
        show_all=show_all
    )

def is_mx_record_valid(email):
    """
    Checks if the email address has the correct format and its domain has valid MX records.
    """
    # 1. Basic Syntax Check
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return False

    try:
        domain = email.split('@')[1]
        
        # 2. MX Record Lookup
        answers = dns.resolver.resolve(domain, 'MX')
        return len(answers) > 0
        
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, Exception):
        # Domain exists but has no MX records, or domain doesn't exist
        return False

@app_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        dob = request.form['dob']

        try:
            dob_date = datetime.strptime(dob, "%Y-%m-%d").date()
            today = datetime.now().date()
            # Calculate 125 years ago correctly handling leap years
            min_date = today.replace(year=today.year - 125)
            
            if dob_date > today:
                flash("Date of Birth cannot be in the future.", "error")
                return redirect(url_for("mediconnect.register"))
            if dob_date < min_date:
                flash("Date of Birth is invalid (over 125 years ago).", "error")
                return redirect(url_for("mediconnect.register"))
        except ValueError:
            flash("Invalid Date format.", "error")
            return redirect(url_for("mediconnect.register"))

        # --- MX Record Validation ---
        if not is_mx_record_valid(email):
            flash("The email address provided is invalid or cannot receive mail.", "error")
            return redirect(url_for("mediconnect.register"))

        if User.query.filter_by(email=email).first():
            flash("Email already exists.", "error")
            return redirect(url_for("mediconnect.register"))

        # Store ALL form data (full_name, password, etc.) in session temporarily
        session['reg_data'] = request.form.to_dict()
        
        # Generate OTP
        otp = str(random.randint(100000, 999999))
        expiry = datetime.now() + timedelta(minutes=10)
        
        # Clean old OTPs for this email if any
        VerificationOTP.query.filter_by(email=email, purpose='register').delete()
        
        new_otp = VerificationOTP(email=email, otp=otp, purpose='register', expires_at=expiry)
        db.session.add(new_otp)
        db.session.commit()
        
        send_verification_email(email, otp, "Patient Registration")
        return redirect(url_for('mediconnect.verify_registration'))

    return render_template('register.html')


@app_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # 1. Check Admin Login
        admin = Admin.query.filter_by(email=email).first()
        if admin and check_password_hash(admin.password, password):
            session['temp_admin_id'] = admin.admin_id
            
            # CASE A: Admin has TOTP enabled
            if admin.totp_secret:
                return redirect(url_for('mediconnect.verify_totp_login'))
            
            # CASE B: Admin uses default Email OTP
            otp = str(random.randint(100000, 999999))
            expiry = datetime.now() + timedelta(minutes=10)
            VerificationOTP.query.filter_by(email=email, purpose='admin_login').delete()
            
            new_otp = VerificationOTP(email=email, otp=otp, purpose='admin_login', expires_at=expiry)
            db.session.add(new_otp)
            db.session.commit()
            
            send_verification_email(email, otp, "Admin Login")
            flash("Admin credentials verified. Please enter OTP.", "info")
            return redirect(url_for('mediconnect.verify_admin_login'))

        # 2. Check User Login
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            flash("Invalid email or password", "danger")
            return render_template('login.html')

        if user.status.lower() != "active":
            flash("Your account has been deactivated. Please contact admin.", "danger")
            return render_template("login.html")

        # CASE C: User has TOTP enabled
        if user.totp_secret:
            session['temp_user_id'] = user.user_id
            return redirect(url_for('mediconnect.verify_totp_login'))

        # CASE D: User Standard Login
        session["user_id"] = user.user_id
        session["role"] = user.role

        if user.role == "doctor":
            return redirect(url_for("mediconnect_doctor.dashboard"))
        else:
            return redirect(url_for("mediconnect_patient.dashboard"))
    
    return render_template('login.html')


@app_bp.route('/verify-totp', methods=['GET', 'POST'])
def verify_totp_login():
    # Determine who is trying to login
    if 'temp_admin_id' in session:
        user_obj = Admin.query.get(session['temp_admin_id'])
        is_admin = True
    elif 'temp_user_id' in session:
        user_obj = User.query.get(session['temp_user_id'])
        is_admin = False
    else:
        return redirect(url_for('mediconnect.login'))

    if request.method == 'POST':
        otp = request.form.get('otp')
        totp = pyotp.TOTP(user_obj.totp_secret)
        
        if totp.verify(otp):
            # Success!
            if is_admin:
                session.pop('temp_admin_id', None)
                session["admin_id"] = user_obj.admin_id
                return redirect(url_for('mediconnect_admin.dashboard'))
            else:
                session.pop('temp_user_id', None)
                session["user_id"] = user_obj.user_id
                session["role"] = user_obj.role
                if user_obj.role == "doctor":
                    return redirect(url_for("mediconnect_doctor.dashboard"))
                return redirect(url_for("mediconnect_patient.dashboard"))
        else:
            flash("Invalid 2FA Code.", "error")

    # Pass flags to template to control fallback link visibility
    return render_template('verify_totp.html', 
                           is_admin=is_admin, 
                           has_totp_secret=bool(user_obj.totp_secret))


@app_bp.route('/switch-to-email-otp')
def switch_to_email_otp():
    if 'temp_admin_id' not in session:
        return redirect(url_for('mediconnect.login'))
        
    admin = Admin.query.get(session['temp_admin_id'])
    
    # Generate Email OTP logic (same as standard admin login)
    otp = str(random.randint(100000, 999999))
    expiry = datetime.now() + timedelta(minutes=10)
    VerificationOTP.query.filter_by(email=admin.email, purpose='admin_login').delete()
    
    new_otp = VerificationOTP(email=admin.email, purpose='admin_login', otp=otp, expires_at=expiry)
    db.session.add(new_otp)
    db.session.commit()
    
    send_verification_email(admin.email, otp, "Admin Login (Fallback)")
    flash("OTP sent to email. Please verify.", "info")
    return redirect(url_for('mediconnect.verify_admin_login'))


@app_bp.route('/switch-to-user-email-otp')
def switch_to_user_email_otp():
    # User (Patient/Doctor) Fallback
    user_id = session.get('temp_user_id')
    if not user_id:
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for('mediconnect.login'))
        
    user = User.query.get(user_id)
    if not user or not user.totp_secret:
        return redirect(url_for('mediconnect.login'))
    
    # Generate Email OTP for User Fallback
    otp = str(random.randint(100000, 999999))
    expiry = datetime.now() + timedelta(minutes=10)
    purpose = 'user_totp_fallback'
    
    VerificationOTP.query.filter_by(email=user.email, purpose=purpose).delete()
    
    new_otp = VerificationOTP(email=user.email, purpose=purpose, otp=otp, expires_at=expiry)
    db.session.add(new_otp)
    db.session.commit()
    
    send_verification_email(user.email, otp, "2FA Fallback Verification")
    flash("OTP sent to your registered email. Please verify.", "info")
    
    return redirect(url_for('mediconnect.verify_user_fallback_otp'))


@app_bp.route('/verify-user-fallback-otp', methods=['GET', 'POST'])
def verify_user_fallback_otp():
    user_id = session.get('temp_user_id')
    if not user_id:
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for('mediconnect.login'))
    
    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('mediconnect.login'))

    if request.method == 'POST':
        otp_input = request.form.get('otp')
        purpose = 'user_totp_fallback'
        
        record = VerificationOTP.query.filter_by(email=user.email, purpose=purpose).order_by(VerificationOTP.id.desc()).first()
        
        if record and record.otp == otp_input and record.expires_at > datetime.now():
            # Success! Finalize Login
            VerificationOTP.query.filter_by(email=user.email, purpose=purpose).delete()
            db.session.commit()
            
            session.pop('temp_user_id', None)
            session["user_id"] = user.user_id
            session["role"] = user.role

            flash("Login successful via Email Fallback.", "success")
            
            if user.role == "doctor":
                return redirect(url_for("mediconnect_doctor.dashboard"))
            return redirect(url_for("mediconnect_patient.dashboard"))
        else:
            flash("Invalid or expired OTP.", "error")

    # Reuse generic verify template
    return render_template('verify_action.html', 
                           title="2FA Email Fallback", 
                           action_url=url_for('mediconnect.verify_user_fallback_otp'))


@app_bp.route('/setup-2fa', methods=['GET', 'POST'])
def setup_2fa():
    # Identify current logged in user
    if 'admin_id' in session:
        user = Admin.query.get(session['admin_id'])
    elif 'user_id' in session:
        user = User.query.get(session['user_id'])
    else:
        return redirect(url_for('mediconnect.login'))

    if request.method == 'POST':
        # Verify the code from the new secret
        secret = session.get('temp_totp_secret')
        otp = request.form.get('otp')
        
        totp = pyotp.TOTP(secret)
        if totp.verify(otp):
            user.totp_secret = secret
            db.session.commit()
            session.pop('temp_totp_secret', None)
            flash("Two-Factor Authentication enabled successfully!", "success")
            
            if 'admin_id' in session:
                return redirect(url_for('mediconnect_admin.profile'))
            elif user.role == 'doctor':
                return redirect(url_for('mediconnect_doctor.profile'))
            else:
                return redirect(url_for('mediconnect_patient.profile'))
        else:
            flash("Invalid code. Please try again.", "error")

    # Generate Secret & QR
    if 'temp_totp_secret' not in session:
        session['temp_totp_secret'] = pyotp.random_base32()
    
    secret = session['temp_totp_secret']
    totp = pyotp.TOTP(secret)
    # Create QR Link (using Google Auth format)
    uri = totp.provisioning_uri(name=user.email, issuer_name="MediConnect")
    
    # Generate QR Code Image
    img = qrcode.make(uri)
    buffered = io.BytesIO()
    img.save(buffered)
    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')

    return render_template('setup_2fa.html', qr_code=img_str, secret=secret)


@app_bp.route('/disable-2fa', methods=['POST'])
def disable_2fa():
    if 'admin_id' in session:
        user = Admin.query.get(session['admin_id'])
        back_url = url_for('mediconnect_admin.profile')
    elif 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user.role == 'doctor':
            back_url = url_for('mediconnect_doctor.profile')
        else:
            back_url = url_for('mediconnect_patient.profile')
    else:
        return redirect(url_for('mediconnect.login'))

    user.totp_secret = None
    db.session.commit()
    flash("Two-Factor Authentication disabled.", "success")
    return redirect(back_url)


@app_bp.route('/verify-admin', methods=['GET', 'POST'])
def verify_admin_login():
    if 'temp_admin_id' not in session:
        return redirect(url_for('mediconnect.login'))
        
    if request.method == 'POST':
        otp_input = request.form.get('otp')
        
        # Add safety check if admin ID in session is invalid
        admin = Admin.query.get(session['temp_admin_id'])
        if not admin:
            session.pop('temp_admin_id', None)
            flash("Session Error. Please login again.", "error")
            return redirect(url_for('mediconnect.login'))

        record = VerificationOTP.query.filter_by(email=admin.email, purpose='admin_login').order_by(VerificationOTP.id.desc()).first()
        
        if record and record.otp == otp_input and record.expires_at > datetime.now():
            # Success
            session.pop('temp_admin_id', None)
            session["admin_id"] = admin.admin_id
            
            # Cleanup
            VerificationOTP.query.filter_by(email=admin.email, purpose='admin_login').delete()
            db.session.commit()
            
            return redirect(url_for('mediconnect_admin.dashboard'))
        else:
            flash("Invalid or expired OTP", "error")
            
    return render_template('verify_action.html', title="Admin 2FA", action_url=url_for('mediconnect.verify_admin_login'))


@app_bp.route('/verify-registration', methods=['GET', 'POST'])
def verify_registration():
    if 'reg_data' not in session:
        return redirect(url_for('mediconnect.register'))
    
    email = session['reg_data']['email']
    
    if request.method == 'POST':
        otp_input = request.form.get('otp')
        record = VerificationOTP.query.filter_by(email=email, purpose='register').order_by(VerificationOTP.id.desc()).first()
        
        if record and record.otp == otp_input and record.expires_at > datetime.now():
            # Success - Create User Now
            data = session['reg_data']
            
            try:
                new_user = User(
                    full_name=data['full_name'],
                    email=data['email'],
                    password=generate_password_hash(data['password']),
                    role='patient',
                    phone_no=data['phone_no'],
                    status='active'
                )
                db.session.add(new_user)
                db.session.commit()

                patient = Patient(
                    user_id=new_user.user_id,
                    dob=datetime.strptime(data['dob'], "%Y-%m-%d").date(),
                    gender=data['gender'],
                    address=data['address'],
                    blood_group=data['blood_group'],
                    emergency_contact=data['emergency_contact']
                )
                db.session.add(patient)
                
                # Cleanup
                VerificationOTP.query.filter_by(email=email, purpose='register').delete()
                db.session.commit()
                
                session.pop('reg_data', None)
                send_welcome_email(data['full_name'], data['email'])
                flash("Registration successful! Please login.", "success")
                return redirect(url_for('mediconnect.login'))
                
            except Exception as e:
                db.session.rollback()
                flash("An error occurred during account creation.", "error")
                return redirect(url_for('mediconnect.register'))
        else:
            flash("Invalid or expired OTP", "error")

    return render_template('verify_action.html', title="Verify Registration", action_url=url_for('mediconnect.verify_registration'))


@app_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        email = request.form.get("email").strip()
        user = User.query.filter_by(email=email).first()

        if not user:
            flash("No account found with this email.", "error")
            return redirect(url_for("mediconnect.reset_password"))

        # Generate OTP
        otp = str(random.randint(100000, 999999))
        expiry = datetime.now() + timedelta(minutes=10)

        # Remove previous OTPs
        PasswordResetOTP.query.filter_by(user_id=user.user_id).delete()

        # Save new OTP
        new_otp = PasswordResetOTP(user_id=user.user_id, otp=otp, expires_at=expiry)
        db.session.add(new_otp)
        db.session.commit()
        send_otp_email(email, otp)

        session['reset_user_id'] = user.user_id
        session.pop('reset_verified', None)

        flash("OTP has been sent to your email.", "success")
        return redirect(url_for("mediconnect.verify_otp"))

    return render_template("reset_password/reset_password_email.html")


@app_bp.route("/reset-password/verify", methods=["GET", "POST"])
def verify_otp():
    # 1. Check if user_id is in session
    user_id = session.get('reset_user_id')
    if not user_id:
        flash("Session expired. Please start over.", "error")
        return redirect(url_for("mediconnect.reset_password"))

    if request.method == "POST":
        otp_input = request.form.get("otp")
        saved = PasswordResetOTP.query.filter_by(user_id=user_id).first()

        if not saved or saved.expires_at < datetime.now():
            flash("OTP expired or invalid.", "error")
            return redirect(url_for("mediconnect.reset_password"))

        if saved.otp != otp_input:
            flash("Incorrect OTP.", "error")
            return redirect(url_for("mediconnect.verify_otp"))
    
        # 2. OTP is correct -> Set verified flag in session
        session['reset_verified'] = True
        
        return redirect(url_for("mediconnect.reset_password_new"))

    return render_template("reset_password/verify_otp.html")


@app_bp.route("/reset-password/new", methods=["GET", "POST"])
def reset_password_new():
    # 1. Security Check: Ensure User ID exists AND OTP was verified
    user_id = session.get('reset_user_id')
    is_verified = session.get('reset_verified')

    if not user_id or not is_verified:
        flash("Unauthorized access. Please verify OTP first.", "error")
        return redirect(url_for("mediconnect.reset_password"))

    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        password = request.form.get("password")
        confirm = request.form.get("confirm_password") 

        if password != confirm:
            flash("Passwords do not match.", "error")
            return redirect(url_for("mediconnect.reset_password_new"))

        user.password = generate_password_hash(password)
        
        # Clear OTPs from DB
        PasswordResetOTP.query.filter_by(user_id=user_id).delete()
        db.session.commit()

        # 2. CLEAN UP SESSION (Critical)
        session.pop('reset_user_id', None)
        session.pop('reset_verified', None)

        flash("Password reset successful! Please login.", "success")
        return redirect(url_for("mediconnect.login"))

    return render_template("reset_password/new_password.html")


@app_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("mediconnect.login"))