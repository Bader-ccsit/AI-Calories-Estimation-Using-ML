from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import hashlib
import datetime
import random
from flask_mail import Mail, Message
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# MySQL connection config
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="foodapp"
)
cursor = conn.cursor()

# Flask-Mail config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'calorieestimator0@gmail.com'
app.config['MAIL_PASSWORD'] = 'qkxhrhklshogealg'
mail = Mail(app)

# Temporary storage for reset codes
reset_codes = {}  # {'email': {'code': '123456', 'expires_at': datetime}}

# Create users table if not exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    username VARCHAR(100) UNIQUE,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255),
    age INT,
    gender VARCHAR(10),
    dietary VARCHAR(50),
    allergies TEXT,
    weight FLOAT,
    height FLOAT,
    goal VARCHAR(50),
    calorie_goal INT,
    activity_level INT
)
""")

# Create history table if not exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    food_name VARCHAR(100),
    calories FLOAT,
    date DATE,
    time TIME,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
""")

conn.commit()

@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.form
        email = data.get('email')
        username = data.get('username')
        password = data.get('password')

        cursor.execute("SELECT id FROM users WHERE email=%s OR username=%s", (email, username))
        if cursor.fetchone():
            return jsonify({"status": "User already exists"}), 400

        password_hash = hashlib.sha256(password.encode()).hexdigest()

        cursor.execute("""
            INSERT INTO users (name, username, email, password_hash, age, gender, dietary, allergies,
                               weight, height, goal, calorie_goal, activity_level)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data.get('name'), username, email, password_hash, data.get('age'), data.get('gender'),
            data.get('dietary'), data.get('allergies'), data.get('weight'), data.get('height'),
            data.get('goal'), data.get('calorieGoal'), data.get('activity')
        ))
        conn.commit()
        return jsonify({"status": "Registration successful"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.form
        identifier = data.get('email')
        password = data.get('password')
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        cursor.execute("""
            SELECT * FROM users WHERE (email=%s OR username=%s) AND password_hash=%s
        """, (identifier, identifier, password_hash))

        user = cursor.fetchone()
        if user:
            return jsonify({"status": "Login success", "user_id": user[0]})
        else:
            return jsonify({"status": "Invalid credentials"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/user/<int:user_id>', methods=['GET'])
def get_user(user_id):
    try:
        cursor.execute("""
            SELECT name, username, email, age, gender, dietary, allergies,
                   weight, height, goal, calorie_goal, activity_level
            FROM users WHERE id=%s
        """, (user_id,))
        row = cursor.fetchone()
        if row:
            keys = ['name', 'username', 'email', 'age', 'gender', 'dietary', 'allergies',
                    'weight', 'height', 'goal', 'calorie_goal', 'activity_level']
            return jsonify(dict(zip(keys, row)))
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/user/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    try:
        data = request.get_json()
        fields = ['name', 'username', 'email', 'age', 'gender', 'dietary', 'allergies',
                  'weight', 'height', 'goal', 'calorie_goal', 'activity_level']
        values = [data.get(f) for f in fields]
        values.append(user_id)

        cursor.execute("""
            UPDATE users SET
              name=%s, username=%s, email=%s, age=%s, gender=%s, dietary=%s, allergies=%s,
              weight=%s, height=%s, goal=%s, calorie_goal=%s, activity_level=%s
            WHERE id=%s
        """, values)
        conn.commit()
        return jsonify({"status": "Profile updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add-history', methods=['POST'])
def add_history():
    try:
        data = request.get_json()
        user_id = data['user_id']
        food_name = data['food']
        calories = data['calories']
        date = data.get('date') or datetime.now().strftime("%Y-%m-%d")
        time = data.get('time') or datetime.now().strftime("%H:%M:%S")

        cursor.execute("""
            INSERT INTO history (user_id, food_name, calories, date, time)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, food_name, calories, date, time))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/history', methods=['GET'])
def get_history():
    try:
        user_id = request.args.get('user_id')
        cursor.execute("""
            SELECT id, food_name, calories, date, time FROM history
            WHERE user_id = %s ORDER BY date DESC, time DESC
        """, (user_id,))
        rows = cursor.fetchall()
        entries = [
            {"id": row[0], "food": row[1], "calories": row[2], "date": str(row[3]), "time": str(row[4])}
            for row in rows
        ]
        return jsonify(entries)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/history/<int:entry_id>', methods=['DELETE'])
def delete_history(entry_id):
    try:
        cursor.execute("DELETE FROM history WHERE id = %s", (entry_id,))
        conn.commit()
        return jsonify({"status": "deleted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/reset-password', methods=['POST'])
def reset_password():
    try:
        data = request.get_json()
        email = data.get('email')

        if not email:
            return jsonify({'message': 'Email is required'}), 400

        code = f"{random.randint(100000, 999999)}"
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        reset_codes[email] = {'code': code, 'expires_at': expires_at}

        msg = Message(
            subject='Your Password Reset Code',
            sender=app.config['MAIL_USERNAME'],
            recipients=[email],
            body=f"Your password reset code is: {code}\nThis code is valid for 10 minutes."
        )
        mail.send(msg)
        return jsonify({'message': 'Reset code sent to your email'}), 200

    except Exception as e:
        return jsonify({'message': f'Failed to send reset email: {str(e)}'}), 500

@app.route('/verify-reset-code', methods=['POST'])
def verify_code():
    try:
        data = request.get_json()
        email = data.get('email')
        code = data.get('code')

        if email not in reset_codes:
            return jsonify({'error': 'No reset request found'}), 404

        entry = reset_codes[email]
        if datetime.utcnow() > entry['expires_at']:
            del reset_codes[email]
            return jsonify({'error': 'Code expired'}), 400

        if code != entry['code']:
            return jsonify({'error': 'Incorrect code'}), 400

        return jsonify({'message': 'Code verified'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/change-password', methods=['POST'])
def change_password():
    try:
        data = request.get_json()
        email = data.get('email')
        code = data.get('code')
        new_password = data.get('new_password')

        if email not in reset_codes:
            return jsonify({'error': 'No reset request found'}), 404

        entry = reset_codes[email]
        if code != entry['code'] or datetime.utcnow() > entry['expires_at']:
            return jsonify({'error': 'Invalid or expired code'}), 400

        password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        cursor.execute("UPDATE users SET password_hash=%s WHERE email=%s", (password_hash, email))
        conn.commit()
        del reset_codes[email]

        return jsonify({'message': 'Password changed successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
