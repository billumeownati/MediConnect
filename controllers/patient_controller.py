from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from models import db, Patient, Appointment, Department, Slot, Doctor, Treatment, User
from sqlalchemy import or_
from datetime import datetime

patient_bp = Blueprint("mediconnect_patient", __name__, url_prefix="/patient")

@patient_bp.route("/dashboard")
def dashboard():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    patient = Patient.query.filter_by(user_id=user_id).first()
    if not patient:
        flash("Patient profile not found.", "error")
        return redirect(url_for("mediconnect.login"))

    search_term = request.args.get("search", "").strip()
    search_by = request.args.get("search_by", "doctor")
    
    query = (
        Appointment.query
        .filter(Appointment.patient_id == patient.patient_id)
        .outerjoin(Slot, Appointment.slot_id == Slot.slot_id)
        .outerjoin(Doctor, Appointment.doctor_id == Doctor.doctor_id)
        .outerjoin(User, Doctor.user_id == User.user_id)
        .outerjoin(Treatment, Appointment.appointment_id == Treatment.appointment_id)
    )

    if search_term:
        if search_by == "doctor":
            query = query.filter(
                or_(
                    User.full_name.ilike(f"%{search_term}%"),
                    Treatment.diagnosed_by.ilike(f"%{search_term}%")
                )
            )
        elif search_by == "date":
            query = query.filter(Slot.date.cast(db.String).ilike(f"%{search_term}%"))
        elif search_by == "status":
            query = query.filter(Appointment.status.ilike(f"%{search_term}%"))

    appointments = query.order_by(Slot.date, Slot.time).all()

    upcoming = [a for a in appointments if a.status == "Booked"]
    past = [a for a in appointments if a.status in ["Completed", "Cancelled"]]

    #pie chart
    chart_completed = sum(1 for a in past if a.status == 'Completed')
    chart_cancelled = sum(1 for a in past if a.status == 'Cancelled')

    #line chart
    date_counts = {}
    for appt in past:
        if appt.slot and appt.slot.date:
            date_str = appt.slot.date.isoformat()
            date_counts[date_str] = date_counts.get(date_str, 0) + 1
    
    sorted_items = sorted(date_counts.items())
    chart_dates = [item[0] for item in sorted_items]
    chart_counts = [item[1] for item in sorted_items]

    return render_template(
        "patient/dashboard.html",
        patient=patient,
        upcoming=upcoming,
        past=past,
        search_term=search_term,
        chart_completed=chart_completed,
        chart_cancelled=chart_cancelled,
        chart_dates=chart_dates,
        chart_counts=chart_counts
    )


@patient_bp.route("/profile", methods=["GET", "POST"])
def profile():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    patient = Patient.query.filter_by(user_id=user_id).first()
    if not patient:
        flash("Patient record not found.", "error")
        return redirect(url_for("mediconnect_patient.dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name").strip() #updating user info
        email = request.form.get("email").strip()
        password = request.form.get("password").strip()
        phone_no = request.form.get("phone_no").strip()

        if User.query.filter(User.email == email, User.user_id != user_id).first():
            #preventing duplicate user email
            flash("Email already exists.", "error")
            return redirect(url_for("mediconnect_patient.profile"))

        if full_name:
            patient.user.full_name = full_name
        if email:
            patient.user.email = email
        if phone_no:
            patient.user.phone_no = phone_no
        if password:
            patient.user.password = password

        dob_str = request.form.get("dob") #updating patient info
        gender = request.form.get("gender")
        address = request.form.get("address")
        blood_group = request.form.get("blood_group")
        emergency_contact = request.form.get("emergency_contact")

        if dob_str:
            patient.dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
        if gender:
            patient.gender = gender
        if address:
            patient.address = address
        if blood_group:
            patient.blood_group = blood_group
        if emergency_contact:
            patient.emergency_contact = emergency_contact

        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("mediconnect_patient.dashboard"))

    return render_template("patient/profile.html", patient=patient)


@patient_bp.route("/book-appointment", methods=["GET", "POST"])
def book_appointment():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    patient = Patient.query.filter_by(user_id=user_id).first()
    if not patient:
        flash("Patient record not found.", "error")
        return redirect(url_for("mediconnect_patient.dashboard"))

    search_term = request.args.get("search", "").strip()
    search_by = request.args.get("search_by", "name")

    doctors_query = Doctor.query.join(User).outerjoin(Department).filter(User.status == "active")

    if search_term:
        if search_by == "name":
            doctors_query = doctors_query.filter(User.full_name.ilike(f"%{search_term}%"))
        elif search_by == "department":
            doctors_query = doctors_query.filter(Department.name.ilike(f"%{search_term}%"))

    doctors = doctors_query.all()

    selected_doctor_id = request.args.get("doctor_id", type=int)
    selected_doctor = None
    available_slots = []

    if selected_doctor_id:
        #checking if the doctor is not blacklisted when the booking is under process
        selected_doctor = Doctor.query.join(User).filter(Doctor.doctor_id == selected_doctor_id, User.status == "active").first()

        if not selected_doctor:
            flash("This doctor is currently not available.", "error")
            return redirect(url_for("mediconnect_patient.book_appointment"))

        available_slots = Slot.query.filter_by(
            doctor_id=selected_doctor_id,
            status="Available"
        ).order_by(Slot.date, Slot.time).all()

        if not available_slots:
            flash("No available slots for this doctor.", "info")

    if request.method == "POST":
        slot_id = int(request.form.get("slot_id", 0))
        doctor_id = int(request.form.get("doctor_id", 0))

        if not slot_id or not doctor_id:
            flash("Please select a doctor and a slot.", "error")
            return redirect(url_for("mediconnect_patient.book_appointment"))

        #double checking if the doctor is not blacklisted before booking
        doctor_active = Doctor.query.join(User).filter(Doctor.doctor_id == doctor_id, User.status == "active").first()

        if not doctor_active:
            flash("This doctor is no longer available.", "error")
            return redirect(url_for("mediconnect_patient.book_appointment"))

        slot = Slot.query.get_or_404(slot_id)
        if slot.status != "Available":
            flash("Selected slot is no longer available.", "error")
            return redirect(url_for("mediconnect_patient.book_appointment"))

        slot.status = "Booked"

        new_appointment = Appointment(
            patient_id=patient.patient_id,
            doctor_id=slot.doctor_id,
            slot_id=slot.slot_id,
            status="Booked",
            created_at=datetime.now()
        )

        db.session.add(new_appointment)
        db.session.commit()

        flash("Appointment booked successfully!", "success")
        return redirect(url_for("mediconnect_patient.dashboard"))

    return render_template(
        "patient/book_appointment.html",
        doctors=doctors,
        available_slots=available_slots,
        selected_doctor_id=selected_doctor_id,
        selected_doctor=selected_doctor,
        search_term=search_term,
        search_by=search_by
    )


@patient_bp.route("/cancel-appointment/<int:appointment_id>", methods=["POST"])
def cancel_appointment(appointment_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    appointment = Appointment.query.get_or_404(appointment_id)

    if appointment.patient.user_id != user_id:
        flash("Not authorized to cancel this appointment.", "error")
        return redirect(url_for("mediconnect_patient.dashboard"))

    appointment.status = "Cancelled"

    if appointment.slot:
        appointment.slot.status = "Available"
        appointment.slot_id = None

    db.session.commit()
    flash("Appointment cancelled successfully.", "success")
    return redirect(url_for("mediconnect_patient.dashboard"))


@patient_bp.route("/reschedule-appointment/<int:appointment_id>", methods=["GET", "POST"])
def reschedule_appointment(appointment_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.doctor and appointment.doctor.user.status != "active":
        flash("This doctor is currently not available. You cannot reschedule this appointment.", "error")
        return redirect(url_for("mediconnect_patient.dashboard"))


    if appointment.patient.user_id != user_id:
        flash("Not authorized to reschedule this appointment.", "error")
        return redirect(url_for("mediconnect_patient.dashboard"))

    doctor_id = appointment.doctor_id

    available_slots = Slot.query.filter_by(
        doctor_id=doctor_id,
        status="Available"
    ).order_by(Slot.date, Slot.time).all()

    if not available_slots and request.method == "GET":
        flash("No free slots available for this doctor.", "info")
        return redirect(url_for("mediconnect_patient.dashboard"))

    if request.method == "POST":
        new_slot_id = request.form.get("slot_id")
        new_slot = Slot.query.get_or_404(new_slot_id)

        if new_slot.status != "Available":
            flash("Selected slot is no longer available.", "error")
            return redirect(url_for("mediconnect_patient.reschedule_appointment", appointment_id=appointment_id))

        if appointment.slot:
            appointment.slot.status = "Available" #freeing old slot

        appointment.slot_id = new_slot.slot_id
        new_slot.status = "Booked"
        appointment.status = "Booked"

        db.session.commit()

        flash("Appointment rescheduled successfully.", "success")
        return redirect(url_for("mediconnect_patient.dashboard"))

    return render_template(
        "patient/reschedule_appointment.html",
        appointment=appointment,
        available_slots=available_slots
    )


@patient_bp.route("/delete-account", methods=["POST"])
def delete_account():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in first.", "error")
        return redirect(url_for("mediconnect.login"))

    user = User.query.get(user_id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("mediconnect_patient.dashboard"))

    # patient will be auto-deleted via delete-on-cascade
    db.session.delete(user)
    db.session.commit()

    session.clear()
    flash("Your account has been deleted successfully.", "success")
    return redirect(url_for("mediconnect.login"))


@patient_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("mediconnect.login"))
