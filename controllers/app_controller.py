from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, Admin, User, Patient, Doctor, Department
from datetime import datetime

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
            #preventing duplicate user email
            flash("Email already exists.", "error")
            return redirect(url_for("mediconnect.register"))

        new_user = User(
            full_name=full_name,
            email=email,
            password=password,
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

        return redirect(url_for('mediconnect.login'))

    return render_template('register.html')


@app_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        admin = Admin.query.filter_by(email=email, password=password).first()
        if admin:
            session["admin_id"] = admin.admin_id
            return redirect(url_for('mediconnect_admin.dashboard'))

        user = User.query.filter_by(email=email, password=password).first()

        if not user:
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

@app_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("mediconnect.login"))