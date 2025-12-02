from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, UTC

db = SQLAlchemy()

class Admin(db.Model):
    __tablename__ = 'admin'
    admin_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(50), nullable=False)

class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    full_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(50), nullable=False, unique=True)
    password = db.Column(db.String(50), nullable=False)
    role = db.Column(db.String(10), nullable=False)
    phone_no = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='active')

    doctor = db.relationship('Doctor', back_populates='user', uselist=False, cascade='all, delete-orphan')
    patient = db.relationship('Patient', back_populates='user', uselist=False, cascade='all, delete-orphan')

class Department(db.Model):
    __tablename__ = 'departments'
    department_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(100), nullable=False)

    doctors = db.relationship('Doctor', back_populates='department', cascade='all, delete-orphan')

class Doctor(db.Model):
    __tablename__ = 'doctors'
    doctor_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), unique=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.department_id', ondelete='CASCADE'))
    qualification = db.Column(db.String(20), nullable=False)
    experience_years = db.Column(db.Integer, nullable=False)

    user = db.relationship('User', back_populates='doctor')
    department = db.relationship('Department', back_populates='doctors')
    slots = db.relationship('Slot', back_populates='doctor', cascade='all, delete-orphan')
    appointments = db.relationship('Appointment', back_populates='doctor', cascade='all, delete-orphan')

class Patient(db.Model):
    __tablename__ = 'patients'
    patient_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), unique=True)
    dob = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    address = db.Column(db.String(100), nullable=False)
    blood_group = db.Column(db.String(3), nullable=False)
    emergency_contact = db.Column(db.String(10), nullable=False)

    user = db.relationship('User', back_populates='patient')
    appointments = db.relationship('Appointment', back_populates='patient', cascade='all, delete-orphan')

class Slot(db.Model):
    __tablename__ = 'slots'
    slot_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.doctor_id', ondelete='CASCADE'))
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Available')

    doctor = db.relationship('Doctor', back_populates='slots')
    appointment = db.relationship('Appointment', back_populates='slot', uselist=False)

class Appointment(db.Model):
    __tablename__ = 'appointments'
    appointment_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    slot_id = db.Column(db.Integer, db.ForeignKey('slots.slot_id', ondelete='SET NULL'), unique=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.patient_id', ondelete='CASCADE'))
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.doctor_id', ondelete='CASCADE'))
    status = db.Column(db.String(20), nullable=False, default='Booked')
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))

    slot = db.relationship('Slot', back_populates='appointment')
    doctor = db.relationship('Doctor', back_populates='appointments')
    patient = db.relationship('Patient', back_populates='appointments')
    treatment = db.relationship('Treatment', back_populates='appointment', uselist=False, cascade='all, delete-orphan')

class Treatment(db.Model):
    __tablename__ = 'treatments'
    treatment_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.appointment_id', ondelete='CASCADE'), unique=True)
    diagnosed_by = db.Column(db.String(50), nullable=False)
    diagnosis = db.Column(db.String(1000), nullable=False)
    prescription = db.Column(db.String(1000), nullable=False)
    notes = db.Column(db.String(500))

    appointment = db.relationship('Appointment', back_populates='treatment')
