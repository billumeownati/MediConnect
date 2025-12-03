from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, Admin, User, Doctor, Patient, Appointment, Department, Slot, Treatment
from datetime import datetime
from sqlalchemy import or_
from werkzeug.security import generate_password_hash
from email_utils import send_doctor_credentials_email

admin_bp = Blueprint("mediconnect_admin", __name__, url_prefix="/admin")

@admin_bp.route("/dashboard")
def dashboard():
    admin_id = session.get("admin_id")
    if not admin_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))
    
    total_departments = Department.query.count()
    total_doctors = Doctor.query.count()
    total_patients = Patient.query.count()
    total_appointments = Appointment.query.count()

    #system overview
    chart_active_patients = Patient.query.join(User).filter(User.status == 'active').count()
    chart_active_doctors = Doctor.query.join(User).filter(User.status == 'active').count()
    
    #doctors per department
    chart_dept_labels = []
    chart_dept_counts = []
    
    departments = Department.query.order_by(Department.name).all()
    
    for dept in departments:
        count = Doctor.query.join(User).filter(Doctor.department_id == dept.department_id,User.status == 'active').count()
        chart_dept_labels.append(dept.name)
        chart_dept_counts.append(count)

    #appointment status pie chart
    chart_booked = Appointment.query.filter_by(status='Booked').count()
    chart_completed = Appointment.query.filter_by(status='Completed').count()
    chart_cancelled = Appointment.query.filter_by(status='Cancelled').count()

    return render_template(
        "admin/dashboard.html",
        total_departments=total_departments,
        total_doctors=total_doctors,
        total_patients=total_patients,
        total_appointments=total_appointments,   
        chart_active_patients=chart_active_patients,
        chart_active_doctors=chart_active_doctors,
        chart_dept_labels=chart_dept_labels,
        chart_dept_counts=chart_dept_counts,
        chart_booked=chart_booked,
        chart_completed=chart_completed,
        chart_cancelled=chart_cancelled
    )


@admin_bp.route("/profile", methods=["GET", "POST"])
def profile():
    admin_id = session.get("admin_id")
    if not admin_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    admin = Admin.query.get(admin_id)
    if not admin:
        flash("Admin profile not found.", "error")
        return redirect(url_for("mediconnect_admin.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if Admin.query.filter(Admin.email == email, Admin.admin_id != admin_id).first():
            flash("Email already exists for another Admin.", "error")
            return redirect(url_for("mediconnect_admin.profile"))
        
        if email:
            admin.email = email
        if password:
            admin.password = generate_password_hash(password)

        db.session.commit()
        flash("Admin profile updated successfully.", "success")
        return redirect(url_for("mediconnect_admin.dashboard"))
    return render_template("admin/profile.html", admin=admin)


@admin_bp.route("/add-doctor", methods=["GET", "POST"])
def add_doctor():
    admin_id = session.get("admin_id")
    if not admin_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    if request.method == "POST":

        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        phone_no = request.form.get("phone_no", "").strip()
        department_id = request.form.get("department_id")
        qualification = request.form.get("qualification", "").strip()
        experience_years = request.form.get("experience_years", "0").strip()

        if not (full_name and email and password and phone_no and qualification):
            flash("All fields are required.", "error")
            return redirect(url_for("mediconnect_admin.add_doctor"))

        if User.query.filter_by(email=email).first():
            #preventing duplicate user email
            flash("Email already exists.", "error")
            return redirect(url_for("mediconnect_admin.add_doctor"))

        try:
            new_user = User(
                full_name=full_name,
                email=email,
                password=generate_password_hash(password),
                role="doctor",
                phone_no=phone_no,
                status="active"
            )
            db.session.add(new_user)
            db.session.commit()

            new_doctor = Doctor(
                user_id=new_user.user_id,
                department_id=department_id,
                qualification=qualification,
                experience_years=experience_years
            )
            db.session.add(new_doctor)
            db.session.commit()

            send_doctor_credentials_email(full_name, email, password)
            flash("Doctor added successfully.", "success")
            return redirect(url_for("mediconnect_admin.view_doctors"))

        except Exception as e:
            db.session.rollback()
            flash(f"Error adding doctor: {e}", "error")
            return redirect(url_for("mediconnect_admin.add_doctor"))

    departments = Department.query.order_by(Department.name).all()
    return render_template("admin/add_doctor.html", departments=departments)


@admin_bp.route("/doctors")
def view_doctors():
    admin_id = session.get("admin_id")
    if not admin_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    query = request.args.get("q", "").strip()
    search_by = request.args.get("search_by", "name")

    doctors_query = Doctor.query.join(User).outerjoin(Department)

    if query:
        if search_by == "name":
            doctors_query = doctors_query.filter(User.full_name.ilike(f"%{query}%"))
        elif search_by == "email":
            doctors_query = doctors_query.filter(User.email.ilike(f"%{query}%"))
        elif search_by == "department":
            doctors_query = doctors_query.filter(Department.name.ilike(f"%{query}%"))
        elif search_by == "status":
            doctors_query = doctors_query.filter(User.status.ilike(f"%{query}%"))

    doctors = doctors_query.all()

    return render_template("admin/view_doctors.html", doctors=doctors, query=query)


@admin_bp.route("/edit-doctor/<int:doctor_id>", methods=["GET", "POST"])
def edit_doctor(doctor_id):
    admin_id = session.get("admin_id")
    if not admin_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))
    
    doctor = Doctor.query.get_or_404(doctor_id)
    departments = Department.query.order_by(Department.name).all()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        phone_no = request.form.get("phone_no", "").strip()
        qualification = request.form.get("qualification", "").strip()
        experience = request.form.get("experience", "0").strip()
        department_id = request.form.get("department_id")

        if User.query.filter(User.email == email, User.user_id != doctor.user_id).first():
            #preventing duplicate user email
            flash("Email already exists.", "error")
            return redirect(url_for("mediconnect_admin.edit_doctor", doctor_id=doctor_id))

        if not (full_name and email and phone_no and qualification):
            return redirect(url_for("mediconnect_admin.edit_doctor", doctor_id=doctor_id))

        try:
            doctor.user.full_name = full_name
            doctor.user.email = email
            if password:
                doctor.user.password = generate_password_hash(password)
            doctor.user.phone_no = phone_no
            doctor.qualification = qualification
            doctor.experience_years = int(experience) if experience.isdigit() else 0
            doctor.department_id = int(department_id) if department_id else None

            db.session.commit()
            flash("Doctor details updated successfully.", "success")
            return redirect(url_for("mediconnect_admin.view_doctors"))

        except Exception as e:
            db.session.rollback()
            flash(f"Error updating doctor: {e}", "error")
            return redirect(url_for("mediconnect_admin.edit_doctor", doctor_id=doctor_id))

    return render_template("admin/edit_doctor.html", doctor=doctor, departments=departments)


@admin_bp.route("/remove-doctor/<int:doctor_id>", methods=["POST"])
def remove_doctor(doctor_id):
    admin_id = session.get("admin_id")
    if not admin_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    doctor = Doctor.query.get_or_404(doctor_id)
    user = doctor.user

    try:
        if user:
            db.session.delete(user)
            db.session.commit()
            flash("Doctor removed successfully.", "success")
        return redirect(url_for("mediconnect_admin.view_doctors"))
    except Exception as e:
        db.session.rollback()
        flash(f"Error removing doctor: {e}", "error")
        return redirect(url_for("mediconnect_admin.view_doctors"))


@admin_bp.route("/patients")
def view_patients():
    admin_id = session.get("admin_id")
    if not admin_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    query = request.args.get("q", "").strip()
    search_by = request.args.get("search_by", "name")

    patients_query = Patient.query.join(User)

    if query:
        if search_by == "name":
            patients_query = patients_query.filter(User.full_name.ilike(f"%{query}%"))
        elif search_by == "id":
            patients_query = patients_query.filter(Patient.patient_id.cast(db.String).ilike(f"%{query}%"))
        elif search_by == "email":
            patients_query = patients_query.filter(User.email.ilike(f"%{query}%"))
        elif search_by == "phone":
            patients_query = patients_query.filter(User.phone_no.ilike(f"%{query}%"))
        elif search_by == "gender":
            patients_query = patients_query.filter(Patient.gender.ilike(f"%{query}%"))
        elif search_by == "emergency":
            patients_query = patients_query.filter(Patient.emergency_contact.ilike(f"%{query}%"))
        elif search_by == "status":
            patients_query = patients_query.filter(User.status.ilike(f"%{query}%"))

    patients = patients_query.all()


    return render_template("admin/view_patients.html", patients=patients, query=query)


@admin_bp.route("/edit-patient/<int:patient_id>", methods=["GET", "POST"])
def edit_patient(patient_id):
    admin_id = session.get("admin_id")
    if not admin_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    patient = Patient.query.get_or_404(patient_id)
    user = patient.user

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        phone_no = request.form.get("phone_no", "").strip()
        dob = request.form.get("dob")
        gender = request.form.get("gender")
        address = request.form.get("address", "").strip()
        blood_group = request.form.get("blood_group", "").strip()
        emergency_contact = request.form.get("emergency_contact", "").strip()

        if not (full_name and email and phone_no and dob):
            return redirect(url_for("mediconnect_admin.edit_patient", patient_id=patient_id))

        #checks if email is taken by another user
        if User.query.filter(User.email == email, User.user_id != user.user_id).first():
            flash("Email already exists.", "error")
            return redirect(url_for("mediconnect_admin.edit_patient", patient_id=patient_id))

        try:
            user.full_name = full_name
            user.email = email
            if password:
                user.password = generate_password_hash(password)
            user.phone_no = phone_no

            patient.dob = datetime.strptime(dob, "%Y-%m-%d").date()
            patient.gender = gender
            patient.address = address
            patient.blood_group = blood_group
            patient.emergency_contact = emergency_contact

            db.session.commit()
            flash("Patient details updated successfully.", "success")
            return redirect(url_for("mediconnect_admin.view_patients"))

        except Exception as e:
            db.session.rollback()
            flash(f"Error updating patient: {e}", "error")
            return redirect(url_for("mediconnect_admin.edit_patient", patient_id=patient_id))

    return render_template("admin/edit_patient.html", patient=patient)


@admin_bp.route("/remove-patient/<int:patient_id>", methods=["POST"])
def remove_patient(patient_id):
    admin_id = session.get("admin_id")
    if not admin_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    patient = Patient.query.get_or_404(patient_id)
    user = patient.user

    try:
        if user:
            db.session.delete(user)
            db.session.commit()
            flash("Patient removed successfully.", "success")
        return redirect(url_for("mediconnect_admin.view_patients"))
    except Exception as e:
        db.session.rollback()
        flash(f"Error removing patient: {e}", "error")
        return redirect(url_for("mediconnect_admin.view_patients"))


@admin_bp.route("/patient-history/<int:patient_id>")
def view_patient_history(patient_id):
    admin_id = session.get("admin_id")
    if not admin_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    patient = Patient.query.get_or_404(patient_id)

    appointments = (
        Appointment.query
        .filter_by(patient_id=patient.patient_id)
        .outerjoin(Slot)
        .outerjoin(Doctor)
        .outerjoin(User, Doctor.user_id == User.user_id)
        .outerjoin(Treatment)
        .order_by(Appointment.created_at.desc())
        .all()
    )

    return render_template(
        "admin/patient_history.html",
        patient=patient,
        appointments=appointments
    )


@admin_bp.route("/appointments")
def view_appointments():
    admin_id = session.get("admin_id")
    if not admin_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    query = request.args.get("q", "").strip()
    search_by = request.args.get("search_by", "patient") 
    base_query = (
        Appointment.query
        .outerjoin(Patient)
        .outerjoin(Doctor)
        .outerjoin(User, Doctor.user_id == User.user_id)
        .outerjoin(Treatment)
    )

    if query:
        try:
            patient_id_int = int(query)
        except ValueError:
            patient_id_int = None

        if search_by == "patient":
            appointments = base_query.filter(
                or_(
                    Patient.user.has(User.full_name.ilike(f"%{query}%")),
                    Patient.patient_id == patient_id_int
                )
            ).order_by(Appointment.created_at.desc()).all()

        elif search_by == "doctor":
            appointments = base_query.filter(
                or_(
                    User.full_name.ilike(f"%{query}%"),
                    Treatment.diagnosed_by.ilike(f"%{query}%")
                )
            ).order_by(Appointment.created_at.desc()).all()

        elif search_by == "date":
            appointments = base_query.filter(Slot.date.cast(db.String).ilike(f"%{query}%")).order_by(Appointment.created_at.desc()).all()

        elif search_by == "time":
            appointments = base_query.filter(Slot.time.cast(db.String).ilike(f"%{query}%")).order_by(Appointment.created_at.desc()).all()

        elif search_by == "status":
            appointments = base_query.filter(Appointment.status.ilike(f"%{query}%")).order_by(Appointment.created_at.desc()).all()
    else:
        appointments = base_query.order_by(Appointment.created_at.desc()).all()

    return render_template("admin/view_appointments.html", appointments=appointments, query=query)


@admin_bp.route("/blacklist/<int:user_id>")
def blacklist_user(user_id):
    admin_id = session.get("admin_id")
    if not admin_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    user = User.query.get(user_id)
    if user:
        user.status = "inactive"
        db.session.commit()
        flash(f"{user.full_name} has been blacklisted.", "success")
    else:
        flash("User not found.", "error")
    return redirect(request.referrer or url_for("mediconnect_admin.dashboard"))

@admin_bp.route("/unblacklist/<int:user_id>")
def unblacklist_user(user_id):
    admin_id = session.get("admin_id")
    if not admin_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    user = User.query.get(user_id)
    if user:
        user.status = "active"
        db.session.commit()
        flash(f"{user.full_name} has been unblacklisted.", "success")
    else:
        flash("User not found.", "error")
    return redirect(request.referrer or url_for("mediconnect_admin.dashboard"))


@admin_bp.route("/add-department", methods=["GET", "POST"])
def add_department():
    admin_id = session.get("admin_id")
    if not admin_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        if not name:
            flash("Department name is required.", "error")
            return redirect(url_for("mediconnect_admin.add_department"))

        # prevent duplicates
        if Department.query.filter_by(name=name).first():
            flash("Department already exists.", "error")
            return redirect(url_for("mediconnect_admin.add_department"))

        try:
            new_department = Department(name=name, description=description)
            db.session.add(new_department)
            db.session.commit()
            flash("Department added successfully.", "success")
            return redirect(url_for("mediconnect_admin.view_departments"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error adding department: {e}", "error")
            return redirect(url_for("mediconnect_admin.add_department"))

    return render_template("admin/add_department.html")


@admin_bp.route("/view-departments")
def view_departments():
    admin_id = session.get("admin_id")
    if not admin_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    query = request.args.get("q", "").strip()

    if query:
        departments = Department.query.filter(
            Department.name.ilike(f"%{query}%")
        ).all()
    else:
        departments = Department.query.all()

    return render_template("admin/view_departments.html", departments=departments, query=query)


@admin_bp.route("/delete-department/<int:department_id>", methods=["POST"])
def delete_department(department_id):
    admin_id = session.get("admin_id")
    if not admin_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    dept = Department.query.get_or_404(department_id)

    try:
        db.session.delete(dept)
        db.session.commit()
        flash("Department removed successfully.", "success")
        return redirect(url_for("mediconnect_admin.view_departments"))
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting department: {e}", "error")
        return redirect(url_for("mediconnect_admin.view_departments"))


@admin_bp.route("/edit-department/<int:department_id>", methods=["GET", "POST"])
def edit_department(department_id):
    admin_id = session.get("admin_id")
    if not admin_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    department = Department.query.get_or_404(department_id)
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        if not name:
            return redirect(url_for("mediconnect_admin.edit_department", department_id=department_id))

        try:
            department.name = name
            department.description = description
            db.session.commit()
            flash("Department details updated successfully.", "success")
            return redirect(url_for("mediconnect_admin.view_departments"))

        except Exception as e:
            db.session.rollback()
            flash(f"Error updating department: {e}", "error")
            return redirect(url_for("mediconnect_admin.edit_department", department_id=department_id))

    return render_template("admin/edit_department.html", department=department)

@admin_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("mediconnect.login"))

