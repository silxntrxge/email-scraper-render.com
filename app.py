from flask import Flask, jsonify, request
import os

app = Flask(__name__)

LOG_FILE = 'app_logs.txt'

def ensure_log_file():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'w') as f:
            f.write("Log file created\n")

@app.route('/logs', methods=['GET'])
def get_logs():
    ensure_log_file()
    try:
        with open(LOG_FILE, 'r') as f:
            logs = f.read()
        return jsonify({"logs": logs}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/logs-reset', methods=['POST'])
def reset_logs():
    try:
        with open(LOG_FILE, 'w') as f:
            f.write("Logs reset\n")
        return jsonify({"message": "Logs reset successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# You can keep your original health check if needed
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(debug=True)