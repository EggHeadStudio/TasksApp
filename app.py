from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from flask_socketio import SocketIO
import psycopg2
from psycopg2.extras import RealDictCursor
import qrcode
import os

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(app)

# PostgreSQL database URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://cleaning_app_db_user:OuFFL7EALuKUT1OnXOhT4HA7kVmWlrJq@dpg-cts1b4rtq21c7394qbb0-a/cleaning_app_db")

# Create database connection
def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require', cursor_factory=RealDictCursor)

# Database initialization
def init_db():
    """Initialize the database with required tables and default admin user."""
    with get_db_connection() as conn:
        with conn.cursor() as c:
            # Create tables
            c.execute('''CREATE TABLE IF NOT EXISTS cleaners (
                            id SERIAL PRIMARY KEY, 
                            name TEXT NOT NULL UNIQUE
                        )''')
            c.execute('''CREATE TABLE IF NOT EXISTS tasks (
                            id SERIAL PRIMARY KEY, 
                            cleaner_id INTEGER NOT NULL, 
                            day TEXT NOT NULL, 
                            task TEXT NOT NULL, 
                            completed BOOLEAN NOT NULL DEFAULT FALSE, 
                            FOREIGN KEY (cleaner_id) REFERENCES cleaners(id)
                        )''')
            # Add Admin user if not present
            c.execute("SELECT COUNT(*) AS count FROM cleaners WHERE name = %s", ("Admin",))
            result = c.fetchone()
            if result["count"] == 0:  # Use dictionary key instead of index
                c.execute("INSERT INTO cleaners (name) VALUES (%s)", ("Admin",))
                print("Admin user added to the database.")
            conn.commit()

# Initialize database on app startup
init_db()

# Route for the main page
@app.route('/')
def index():
    return render_template('index.html')

# Route to provide the QR code for the Render URL
@app.route('/api/qr', methods=['GET'])
def get_qr_code():
    """Generate and return a QR code for the application."""
    render_url = "https://tasksapp-qcba.onrender.com"

    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(render_url)
    qr.make(fit=True)

    # Save QR code to static directory
    qr_img_path = "static/qr_code.png"
    if not os.path.exists('static'):
        os.makedirs('static')
    qr.make_image(fill_color="black", back_color="white").save(qr_img_path)
    return send_file(qr_img_path, mimetype='image/png')

# Route to provide the Render application URL or IP
@app.route('/api/ip', methods=['GET'])
def get_ip():
    # Return the Render app URL as the IP is irrelevant in production
    return jsonify({"ip": "https://tasksapp-qcba.onrender.com"})

# Route for user authentication
@app.route('/api/authenticate', methods=['POST'])
def authenticate_user():
    """Authenticate the user as Admin or Cleaner."""
    try:
        data = request.get_json()
        password = data.get('password', None)
        name = data.get('name', None)

        # Admin access
        if password == "1234":
            return jsonify({
                "message": "Authentication successful (Admin mode)",
                "is_admin": True,
                "cleaner_id": None
            }), 200

        # Cleaner access
        if not name:
            return jsonify({"error": "Name is required for non-admin access"}), 400

        with get_db_connection() as conn:
            with conn.cursor() as c:
                c.execute("SELECT id FROM cleaners WHERE name = %s", (name,))
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

# API endpoint for cleaners
@app.route('/api/cleaners', methods=['GET', 'POST', 'DELETE'])
def cleaners():
    """Manage cleaners."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                if request.method == 'POST':  # Add a cleaner
                    data = request.get_json()
                    c.execute("INSERT INTO cleaners (name) VALUES (%s)", (data['name'],))
                    conn.commit()
                    socketio.emit('update')
                    return jsonify({"message": "Cleaner added successfully"}), 201

                elif request.method == 'DELETE':  # Delete a cleaner
                    cleaner_id = request.args.get('id')
                    c.execute("DELETE FROM tasks WHERE cleaner_id = %s", (cleaner_id,))
                    c.execute("DELETE FROM cleaners WHERE id = %s", (cleaner_id,))
                    conn.commit()
                    socketio.emit('update')
                    return jsonify({"message": "Cleaner deleted successfully"}), 200

                else:  # Get all cleaners
                    c.execute("SELECT * FROM cleaners")
                    cleaners = [{"id": row[0], "name": row[1]} for row in c.fetchall()]
                    return jsonify(cleaners)

    except Exception as e:
        print(f"Error in /api/cleaners: {str(e)}")
        return jsonify({"error": str(e)}), 500

# API endpoint for tasks
@app.route('/api/tasks', methods=['GET', 'POST', 'DELETE', 'PUT'])
def tasks():
    """Manage tasks."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as c:
                if request.method == 'POST':  # Add a task
                    data = request.get_json()
                    c.execute("INSERT INTO tasks (cleaner_id, day, task, completed) VALUES (%s, %s, %s, %s)", 
                              (data['cleaner_id'], data['day'], data['task'], False))
                    conn.commit()
                    socketio.emit('update')
                    return jsonify({"message": "Task added successfully"}), 201

                elif request.method == 'DELETE':  # Delete a task
                    task_id = request.args.get('id')
                    c.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
                    conn.commit()
                    socketio.emit('update')
                    return jsonify({"message": "Task deleted successfully"}), 200

                elif request.method == 'PUT':  # Update task
                    data = request.get_json()
                    c.execute("UPDATE tasks SET completed = %s WHERE id = %s", 
                              (data['completed'], data['id']))
                    conn.commit()
                    socketio.emit('update')
                    return jsonify({"message": "Task updated successfully"}), 200

                else:  # Get all tasks
                    c.execute("""SELECT tasks.id, cleaners.name, tasks.day, tasks.task, tasks.completed
                                 FROM tasks 
                                 JOIN cleaners ON tasks.cleaner_id = cleaners.id""")
                    tasks = [{"id": row[0], "cleaner": row[1], "day": row[2], "task": row[3], "completed": row[4]} for row in c.fetchall()]
                    return jsonify(tasks)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Run the app
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8000, debug=True)