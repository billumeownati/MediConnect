from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, Doctor, Patient, User, Appointment, Slot, Treatment
from datetime import datetime, timedelta
from sqlalchemy import or_

doctor_bp = Blueprint("mediconnect_doctor", __name__, url_prefix="/doctor")

@doctor_bp.route("/dashboard")
def dashboard():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    doctor = Doctor.query.filter_by(user_id=user_id).first()
    if not doctor:
        flash("Doctor profile not found.", "error")
        return redirect(url_for("mediconnect.login"))

    doctor_id = doctor.doctor_id

    search_term = request.args.get("search", "")
    search_by = request.args.get("search_by", "patient")

    appointments = Appointment.query.outerjoin(Slot).join(Patient).join(User).filter(Appointment.doctor_id == doctor_id).order_by(Slot.date, Slot.time).all()

    filtered_appointments = appointments
    if search_term:
        filtered_appointments = (
            Appointment.query.outerjoin(Slot)
            .outerjoin(Treatment)
            .outerjoin(Patient, Appointment.patient_id == Patient.patient_id)
            .outerjoin(User, Patient.user)
            .filter(
                Appointment.doctor_id == doctor_id,
                or_(
                    User.full_name.ilike(f"%{search_term}%") if search_by == "patient" else False,
                    Slot.date.cast(db.String).ilike(f"%{search_term}%") if search_by == "date" else False,
                    Slot.time.cast(db.String).ilike(f"%{search_term}%") if search_by == "time" else False,
                    Appointment.status.ilike(f"%{search_term}%") if search_by == "status" else False
                )
            )
            .order_by(Slot.date, Slot.time)
            .all()
        )

    total_appointments = len(appointments)
    booked_appointments = sum(1 for a in appointments if a.status == 'Booked')
    cancelled_appointments = sum(1 for a in appointments if a.status == 'Cancelled')
    completed_appointments = sum(1 for a in appointments if a.status == 'Completed')

    #line chart
    date_counts = {}
    for appt in appointments:
        if appt.slot and appt.slot.date:
            date_str = appt.slot.date.isoformat()
            date_counts[date_str] = date_counts.get(date_str, 0) + 1
    
    sorted_items = sorted(date_counts.items())
    chart_dates = [item[0] for item in sorted_items]
    chart_counts = [item[1] for item in sorted_items]

    department_name = doctor.department.name if doctor.department else "Not Assigned"

    return render_template(
        "doctor/dashboard.html",
        doctor=doctor,
        department_name=department_name,
        appointments=filtered_appointments,
        total_appointments=total_appointments,
        booked_appointments=booked_appointments,
        completed_appointments=completed_appointments,
        cancelled_appointments=cancelled_appointments,
        search_term=search_term,
        chart_dates=chart_dates,
        chart_counts=chart_counts
    )


@doctor_bp.route("/profile", methods=["GET", "POST"])
def profile():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    doctor = Doctor.query.filter_by(user_id=user_id).first()
    if not doctor:
        flash("Doctor record not found.", "error")
        return redirect(url_for("mediconnect_doctor.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        phone_no = request.form.get("phone_no", "").strip()
        password = request.form.get("password", "").strip()
        qualification = request.form.get("qualification", "").strip()
        experience_years = request.form.get("experience_years", "").strip()

        if User.query.filter(User.email == email, User.user_id != user_id).first():
            #preventing duplicate user email
            flash("Email already exists.", "error")
            return redirect(url_for("mediconnect_doctor.profile"))

        if email:
            doctor.user.email = email
        if phone_no:
            doctor.user.phone_no = phone_no
        if password:
            doctor.user.password = password

        if qualification:
            doctor.qualification = qualification
        if experience_years.isdigit():
            doctor.experience_years = int(experience_years)

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("mediconnect_doctor.dashboard"))

    return render_template("doctor/profile.html", doctor=doctor)


@doctor_bp.route("/update_appointment/<int:appointment_id>", methods=["POST"])
def update_appointment(appointment_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    appointment = Appointment.query.get_or_404(appointment_id)
    new_status = request.form.get("status")

    if appointment.patient.user.status != 'active':
        flash("This patient is not available.", "error")
        return redirect(url_for("mediconnect_doctor.dashboard"))


    if new_status not in ["Completed", "Cancelled"]:
        flash("Invalid status update.", "danger") #validation
        return redirect(url_for("mediconnect_doctor.dashboard"))

    appointment.status = new_status

    if new_status == "Cancelled" and appointment.slot:
        appointment.slot.status = "Available"
        appointment.slot_id = None

    if new_status == "Completed" and appointment.slot:
        appointment.slot.status = "Booked"

    db.session.commit()
    flash(f"Appointment marked as {new_status}.", "success")
    return redirect(url_for("mediconnect_doctor.dashboard"))


@doctor_bp.route("/treatment/<int:appointment_id>", methods=["GET", "POST"])
def treatment(appointment_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))
    
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.slot.doctor_id != doctor.doctor_id:
        flash("Not authorized", "error") #validation
        return redirect(url_for("mediconnect_doctor.dashboard"))

    if appointment.patient.user.status != 'active':
        flash("This patient is not available.", "error")
        return redirect(url_for("mediconnect_doctor.dashboard"))

    if request.method == "POST":
        diagnosis = request.form.get("diagnosis")
        prescription = request.form.get("prescription")
        notes = request.form.get("notes", "")

        treatment = appointment.treatment
        if not treatment:
            treatment = Treatment(appointment_id=appointment.appointment_id, diagnosed_by=doctor.user.full_name) #saving doctor's name in a variable incase of doctor deletion
            db.session.add(treatment)

        treatment.diagnosis = diagnosis
        treatment.prescription = prescription
        treatment.notes = notes
        appointment.status = "Completed"
        db.session.commit()
        flash("Treatment saved successfully", "success")
        return redirect(url_for("mediconnect_doctor.dashboard"))

    return render_template("doctor/treatment.html", appointment=appointment)


@doctor_bp.route("/patient-history/<int:patient_id>")
def patient_history(patient_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    patient = Patient.query.get_or_404(patient_id)
    appointments = Appointment.query.filter_by(patient_id=patient.patient_id).all()
    return render_template("doctor/patient_history.html",
                           patient=patient,
                           appointments=appointments)


@doctor_bp.route("/slots")
def slots():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))
    
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    slots = Slot.query.filter_by(doctor_id=doctor.doctor_id).order_by(Slot.date, Slot.time).all()
    for slot in slots:
        if slot.appointment:
            if slot.appointment.status in ["Completed", "Booked"]:
                slot.status = "Booked"
            elif slot.appointment.status == "Cancelled":
                slot.status = "Available"
        else:
            slot.status = "Available"
    db.session.commit()
    return render_template("doctor/slots.html", doctor=doctor, slots=slots)


@doctor_bp.route("/add-slot", methods=["GET", "POST"])
def add_slot():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))
    
    doctor = Doctor.query.filter_by(user_id=user_id).first()

    if request.method == "POST":
        date_str = request.form.get("date")
        time_str = request.form.get("time")

        if not date_str or not time_str:
            flash("Both date and time are required.", "error") #validation
            return redirect(url_for("mediconnect_doctor.add_slot"))

        slot_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        slot_time = datetime.strptime(time_str, "%H:%M").time()

        new_slot = Slot(
            doctor_id=doctor.doctor_id,
            date=slot_date,
            time=slot_time,
            status="Available"
        )
        db.session.add(new_slot)
        db.session.commit()
        flash("Slot added successfully.", "success")
        return redirect(url_for("mediconnect_doctor.slots"))

    return render_template("doctor/add_slots.html", doctor=doctor)


@doctor_bp.route("/edit-slot/<int:slot_id>", methods=["GET", "POST"])
def edit_slot(slot_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    slot = Slot.query.get_or_404(slot_id)
    
    if slot.appointment and slot.appointment.status != "Cancelled":
        flash("Cannot edit booked slot", "error") #validation
        return redirect(url_for("mediconnect_doctor.slots"))

    if request.method == "POST":
        date = request.form.get("date")
        time = request.form.get("time")
        slot.date = datetime.strptime(date, "%Y-%m-%d").date()
        slot.time = datetime.strptime(time, "%H:%M").time()
        db.session.commit()
        flash("Slot updated", "success")
        return redirect(url_for("mediconnect_doctor.slots"))

    return render_template("doctor/edit_slot.html", slot=slot)

@doctor_bp.route("/clone-slots", methods=["GET", "POST"])
def clone_slots():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))
    
    doctor = Doctor.query.filter_by(user_id=user_id).first()

    if request.method == "POST":
        source_date_str = request.form.get("source_date")
        start_date_str = request.form.get("start_date")
        end_date_str = request.form.get("end_date")

        source_date = datetime.strptime(source_date_str, "%Y-%m-%d").date()
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        if start_date > end_date:
            flash("Start date cannot be after end date.", "error")
            return redirect(url_for("mediconnect_doctor.clone_slots"))

        original_slots = Slot.query.filter_by(doctor_id=doctor.doctor_id, date=source_date).all()

        if not original_slots:
            flash(f"No slots found for {source_date}.", "error")
            return redirect(url_for("mediconnect_doctor.slots"))

        current_date = start_date
        while current_date <= end_date:
            for slot in original_slots:
                #skips if already present
                exists = Slot.query.filter_by(
                    doctor_id=doctor.doctor_id,
                    date=current_date,
                    time=slot.time
                ).first()
                if not exists:
                    new_slot = Slot(
                        doctor_id=doctor.doctor_id,
                        date=current_date,
                        time=slot.time,
                        status="Available"
                    )
                    db.session.add(new_slot)
            current_date += timedelta(days=1)

        db.session.commit()
        flash(f"Slots cloned successfully from {source_date} to the range {start_date} – {end_date}.", "success")
        return redirect(url_for("mediconnect_doctor.slots"))

    return render_template("doctor/clone_slots.html", doctor=doctor)

@doctor_bp.route("/delete-slot/<int:slot_id>", methods=["POST"])
def delete_slot(slot_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))
    
    slot = Slot.query.get_or_404(slot_id)

    if slot.appointment and slot.appointment.status != "Cancelled":
        flash("Cannot delete a booked slot", "error") #validation
        return redirect(url_for("mediconnect_doctor.slots"))

    db.session.delete(slot)
    db.session.commit()
    flash("Slot deleted successfully.", "success")
    return redirect(url_for("mediconnect_doctor.slots"))


@doctor_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("mediconnect.login"))

