from flask import Flask
from models import db, Admin, mail
from datetime import datetime
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from flask_mail import Message
from email_utils import send_admin_creation_email

def create_app():
    load_dotenv()

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DB_URI")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")

    db.init_app(app)

    app.config['MAIL_SERVER'] = os.getenv("SMTP_SERVER")
    app.config['MAIL_PORT'] = int(os.getenv("SMTP_PORT", 587))
    app.config['MAIL_USERNAME'] = os.getenv("SMTP_LOGIN")
    app.config['MAIL_PASSWORD'] = os.getenv("SMTP_KEY")
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_DEFAULT_SENDER'] = ('MediConnect', os.getenv("MAIL_SENDER_EMAIL"))
    
    mail.init_app(app)

    from controllers.app_controller import app_bp
    from controllers.admin_controller import admin_bp
    from controllers.doctor_controller import doctor_bp
    from controllers.patient_controller import patient_bp

    app.register_blueprint(app_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(patient_bp)

    with app.app_context():
        db.create_all()

        admin = db.session.get(Admin, 1)
        if not admin:
            admin = Admin(
                admin_id=1,
                email=os.getenv("ADMIN_EMAIL"),
                password=generate_password_hash(os.getenv("ADMIN_PASSWORD"))
            )
            db.session.add(admin)
            db.session.commit()
            send_admin_creation_email(os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD"))
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
