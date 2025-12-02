from flask import Flask
from models import db, Admin
import os
from dotenv import load_dotenv

def create_app():
    load_dotenv()

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DB_URI")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")

    db.init_app(app)
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
                password=os.getenv("ADMIN_PASSWORD")
            )
            db.session.add(admin)
            db.session.commit()
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
