from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
from flask_cors import CORS
import socket
import qrcode
from flask_socketio import SocketIO
import os

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(app)

# Set the database path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'cleaning.db')

print(f"Database path: {DATABASE_PATH}")
if os.path.exists(DATABASE_PATH):
    print("Database file found.")
else:
    print("Database file NOT found.")

# Database initialization
def init_db():
    with sqlite3.connect(DATABASE_PATH) as conn:  # Use the correct path
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS cleaners (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        name TEXT NOT NULL
                    )''')
        c.execute('''CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        cleaner_id INTEGER NOT NULL, 
                        day TEXT NOT NULL, 
                        task TEXT NOT NULL, 
                        completed BOOLEAN NOT NULL DEFAULT 0, 
                        FOREIGN KEY (cleaner_id) REFERENCES cleaners(id)
                    )''')
        # Check if the "Admin" user exists and insert it if not
        c.execute("SELECT COUNT(*) FROM cleaners WHERE name = ?", ("Admin",))
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO cleaners (name) VALUES (?)", ("Admin",))
            print("Admin user added to the database.")
        conn.commit()

# Initialize database on app startup
init_db()

# Route for the main page
@app.route('/')
def index():
    return render_template('index.html')

# Route to provide the server IP
@app.route('/api/ip', methods=['GET'])
def get_ip():
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    return jsonify({"ip": local_ip})

# Route to provide the QR code for the IP
@app.route('/api/qr', methods=['GET'])
def get_qr_code():
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    ip_url = f"http://{local_ip}:8000"

    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(ip_url)
    qr.make(fit=True)

    # Ensure the static directory exists
    if not os.path.exists('static'):
        os.makedirs('static')

    # Save QR code as an image
    qr_img_path = "static/qr_code.png"
    qr.make_image(fill_color="black", back_color="white").save(qr_img_path)
    return send_file(qr_img_path, mimetype='image/png')

# Route for user authentication
@app.route('/api/authenticate', methods=['POST'])
def authenticate_user():
    try:
        data = request.get_json()
        password = data.get('password', None)
        name = data.get('name', None)

        # Check admin access based on the password
        if password == "1234":
            return jsonify({
                "message": "Authentication successful (Admin mode)",
                "is_admin": True,
                "cleaner_id": None  # No specific cleaner tied to admin login
            }), 200

        # If no name is provided and the password is incorrect
        if not name:
            return jsonify({"error": "Name is required for non-admin access"}), 400

        # Check if the cleaner name exists in the database
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute("SELECT id FROM cleaners WHERE name = ?", (name,))
        cleaner = c.fetchone()

        if not cleaner:
            return jsonify({"error": "Invalid name"}), 400

        return jsonify({
            "message": "Authentication successful",
            "is_admin": False,
            "cleaner_id": cleaner[0]
        }), 200

    except Exception as e:
        return jsonify({"error": "Authentication failed", "details": str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()

# API endpoint for cleaners
@app.route('/api/cleaners', methods=['GET', 'POST', 'DELETE'])
def cleaners():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        
        if request.method == 'POST':  # Add a cleaner
            data = request.get_json()
            if not data or 'name' not in data:
                return jsonify({"error": "Invalid data"}), 400
            c.execute("INSERT INTO cleaners (name) VALUES (?)", (data['name'],))
            conn.commit()
            socketio.emit('update')  # Notify clients of the update
            cleaner_id = c.lastrowid
            return jsonify({"id": cleaner_id, "name": data['name']}), 201

        elif request.method == 'DELETE':  # Delete a cleaner and their tasks
            cleaner_id = request.args.get('id')
            if not cleaner_id:
                return jsonify({"error": "Cleaner ID is required"}), 400
            c.execute("DELETE FROM tasks WHERE cleaner_id = ?", (cleaner_id,))
            c.execute("DELETE FROM cleaners WHERE id = ?", (cleaner_id,))
            conn.commit()
            socketio.emit('update')  # Notify clients of the update
            return jsonify({"message": "Cleaner and associated tasks deleted"}), 200

        else:  # Get all cleaners
            c.execute("SELECT * FROM cleaners")
            cleaners = [{"id": row[0], "name": row[1]} for row in c.fetchall()]
            return jsonify(cleaners)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# API endpoint for tasks
@app.route('/api/tasks', methods=['GET', 'POST', 'DELETE', 'PUT'])
def tasks():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()

        if request.method == 'POST':  # Add a task
            try:
                data = request.get_json()
                if not data or not all(k in data for k in ("cleaner_id", "day", "task")):
                    return jsonify({"error": "Invalid data"}), 400

                # Ensure the cleaner_id exists
                c.execute("SELECT id FROM cleaners WHERE id = ?", (data['cleaner_id'],))
                if not c.fetchone():
                    return jsonify({"error": "Cleaner ID does not exist"}), 400

                c.execute("INSERT INTO tasks (cleaner_id, day, task, completed) VALUES (?, ?, ?, ?)", 
                          (data['cleaner_id'], data['day'], data['task'], False))
                conn.commit()
                socketio.emit('update')  # Notify clients of the update
                task_id = c.lastrowid
                return jsonify({"id": task_id, "cleaner_id": data['cleaner_id'], "day": data['day'], "task": data['task']}), 201
            except Exception as e:
                print("Error adding task:", str(e))
                return jsonify({"error": "Failed to add task", "details": str(e)}), 500

        elif request.method == 'DELETE':  # Delete a task
            task_id = request.args.get('id')
            if not task_id:
                return jsonify({"error": "Task ID is required"}), 400
            c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            socketio.emit('update')  # Notify clients of the update
            return jsonify({"message": "Task deleted"}), 200

        elif request.method == 'PUT':  # Update task completion status
            data = request.get_json()
            if not data or 'id' not in data or 'completed' not in data:
                return jsonify({"error": "Invalid data"}), 400
            c.execute("UPDATE tasks SET completed = ? WHERE id = ?", (data['completed'], data['id']))
            conn.commit()
            socketio.emit('update')  # Notify clients of the update
            return jsonify({"message": "Task status updated"}), 200
        
        elif request.method == 'GET':  # Get all tasks or filter by cleaner
            try:
                cleaner_id = request.args.get('cleaner_id', None)  # Optional filter
                if cleaner_id:
                    # Fetch tasks for the specific cleaner
                    c.execute("""SELECT tasks.id, cleaners.name, tasks.day, tasks.task, tasks.completed
                                 FROM tasks 
                                 JOIN cleaners ON tasks.cleaner_id = cleaners.id
                                 WHERE cleaners.id = ?""", (cleaner_id,))
                else:
                    # Fetch all tasks
                    c.execute("""SELECT tasks.id, cleaners.name, tasks.day, tasks.task, tasks.completed
                                 FROM tasks 
                                 JOIN cleaners ON tasks.cleaner_id = cleaners.id""")
                
                # Prepare the response data
                tasks = [{"id": row[0], "cleaner": row[1], "day": row[2], "task": row[3], "completed": bool(row[4])} for row in c.fetchall()]
                return jsonify(tasks), 200
            except Exception as e:
                print("Error fetching tasks:", str(e))
                return jsonify({"error": "Failed to fetch tasks", "details": str(e)}), 500

        else:  # Get all tasks
            try:
                c.execute("""SELECT tasks.id, cleaners.name, tasks.day, tasks.task, tasks.completed
                             FROM tasks 
                             JOIN cleaners ON tasks.cleaner_id = cleaners.id""")
                tasks = [{"id": row[0], "cleaner": row[1], "day": row[2], "task": row[3], "completed": bool(row[4])} for row in c.fetchall()]
                return jsonify(tasks)
            except Exception as e:
                print("Error fetching tasks:", str(e))
                return jsonify({"error": "Failed to fetch tasks", "details": str(e)}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# Run the app and make it accessible on the local network
if __name__ == '__main__':
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"App is running and accessible at: http://{local_ip}:8000")
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get("PORT", 8000)), debug=True)
    #socketio.run(app, host='0.0.0.0', port=8000, debug=True)
