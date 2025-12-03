from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, Admin, User, Patient, Doctor, Department, PasswordResetOTP
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import random
from email_utils import send_welcome_email, send_otp_email

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
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        phone_no = request.form['phone_no']
        dob = request.form['dob']
        gender = request.form['gender']
        address = request.form['address']
        blood_group = request.form['blood_group']
        emergency_contact = request.form['emergency_contact']
        
        if User.query.filter_by(email=email).first():
            flash("Email already exists.", "error")
            return redirect(url_for("mediconnect.register"))

        new_user = User(
            full_name=full_name,
            email=email,
            password=generate_password_hash(password),
            role='patient',
            phone_no=phone_no,
            status='active'
        )
        db.session.add(new_user)
        db.session.commit()

        patient = Patient(
            user_id=new_user.user_id,
            dob=datetime.strptime(dob, "%Y-%m-%d").date(),
            gender=gender,
            address=address,
            blood_group=blood_group,
            emergency_contact=emergency_contact
        )
        db.session.add(patient)
        db.session.commit()
        send_welcome_email(full_name, email)

        return redirect(url_for('mediconnect.login'))

    return render_template('register.html')


@app_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        admin = Admin.query.filter_by(email=email).first()
        if admin and check_password_hash(admin.password, password):
            session["admin_id"] = admin.admin_id
            return redirect(url_for('mediconnect_admin.dashboard'))

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