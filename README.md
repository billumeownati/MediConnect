# 🌐 MediConnect  
### Simple. Secure. Smart Hospital Management System

MediConnect is an open source web based Hospital Management System built to make hospital work smooth and organised.  
It helps patients book appointments easily, helps doctors manage schedules and history, and helps admins run the system with full control.

---

## ⭐ Highlights
- Clean and easy interface  
- Strong security with 2FA  
- Separate dashboards for Admin, Doctor, and Patient  
- Full appointment and medical record system  
- Works with PostgreSQL and SQLite  

---

## 🔒 Security Features
- Role Based Access Control for Admin, Doctor, and Patient  
- Two Factor Authentication using TOTP apps  
- Email OTP fallback for safe recovery  
- Email verification for new patient sign up  
- Secure sessions using HttpOnly and SameSite cookies  

---

## 🏥 Patient Portal
- Easy registration and login  
- Search doctors by name or department  
- Book, view, reschedule, or cancel appointments  
- View full medical history  
- Manage personal details safely  

---

## 👨‍⚕️ Doctor Portal
- Create, edit, or clone appointment slots  
- View patient history  
- Add diagnoses and prescriptions  
- Dashboard with all appointments  
- Update profile details  

---

## 🛠️ Admin Portal
- Add and manage doctors  
- View and manage patients  
- Blacklist or unblacklist users  
- Create and update departments  
- Basic analytics for system activity  

---

## 🧱 Technology Stack
- **Backend:** Python, Flask  
- **Database:** PostgreSQL (production), SQLite (development)  
- **Frontend:** HTML, CSS, Bootstrap, Jinja templates  
- **Security:** Werkzeug hashing, PyOTP, Flask Session  
- **Email:** Flask Mail with SMTP  

---

## ⚙️ Installation Guide

### 1. Clone the project
```bash
git clone https://github.com/billumeownati/MediConnect.git
cd MediConnect
```

### 2. Create a virtual environment

Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

Mac/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Create a .env file  
Add the following:

```
SECRET_KEY=your_secret_key

DB_URI=sqlite:///mediconnect.db
# For production use:
# DB_URI=postgresql://user:password@localhost/dbname

SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_LOGIN=your_email@example.com
SMTP_KEY=your_api_key_or_password
MAIL_SENDER_EMAIL=noreply@yourdomain.com

ADMIN_EMAIL=admin@mediconnect.com
ADMIN_PASSWORD=your_admin_password
```

### 5. First run  
The system will auto create tables and the admin account.

### 6. Start the server
```bash
python app.py
```
Visit **http://localhost:5000**

---

## 🤝 Contribute
1. Fork the project  
2. Make a new branch  
3. Commit your changes  
4. Push the branch  
5. Open a pull request  

Simple coding style and proper error handling is appreciated.

---

## 📜 License
This project is under **GNU GPL v3.0**.  
You may use, share, and modify it as long as it stays open source under the same license.  
Selling a rebranded closed version is not allowed.

---

### ❤️ 2025 MediConnect | Open Source Hospital Management System
