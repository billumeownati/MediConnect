from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, Admin, User, Patient, Doctor, Department, PasswordResetOTP, VerificationOTP
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import random
from email_utils import send_welcome_email, send_otp_email, send_verification_email

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

        admin = Admin.query.filter_by(email=email).first()
        if admin and check_password_hash(admin.password, password):
            # 2FA Logic for Admin
            otp = str(random.randint(100000, 999999))
            expiry = datetime.now() + timedelta(minutes=10)

            # Clear old OTPs
            VerificationOTP.query.filter_by(email=email, purpose='admin_login').delete()

            new_otp = VerificationOTP(email=email, otp=otp, purpose='admin_login', expires_at=expiry)
            db.session.add(new_otp)
            db.session.commit()
            
            send_verification_email(email, otp, "Admin Login")
            session['temp_admin_id'] = admin.admin_id # Temporary session
            flash("Admin credentials verified. Please enter OTP.", "info")
            return redirect(url_for('mediconnect.verify_admin_login'))

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            flash("Invalid email or password", "danger")
            return render_template('login.html')

        if user.status.lower() != "active":
            flash("Your account has been deactivated. Please contact admin.", "danger")
            return render_template("login.html")

        session["user_id"] = user.user_id
        session["role"] = user.role

        if user.role == "doctor":
            return redirect(url_for("mediconnect_doctor.dashboard"))
        else:
            return redirect(url_for("mediconnect_patient.dashboard"))
    
    return render_template('login.html')


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