import os
import uuid
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)

DEVIN_API_URL = "https://api.devin.ai/v1/sessions"
DEVIN_API_TOKEN = os.getenv("DEVIN_API_TOKEN", "")
TARGET_REPO = os.getenv("TARGET_REPO", "jackmontinaro/dotw-copy1")

feature_flags = [
    {
        "id": str(uuid.uuid4()),
        "name": "enable_new_scoring",
        "description": "Enables the new drink scoring algorithm",
        "status": "active",
    },
    {
        "id": str(uuid.uuid4()),
        "name": "show_user_tables",
        "description": "Shows per-user breakdown tables on drink pages",
        "status": "active",
    },
    {
        "id": str(uuid.uuid4()),
        "name": "enable_drink_notes",
        "description": "Enables the notes field on drink entries",
        "status": "active",
    },
]

workflow_history = []


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/flags", methods=["GET"])
def get_flags():
    return jsonify(feature_flags)


@app.route("/api/flags", methods=["POST"])
def add_flag():
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Flag name is required"}), 400

    flag = {
        "id": str(uuid.uuid4()),
        "name": data["name"],
        "description": data.get("description", ""),
        "status": "active",
    }
    feature_flags.append(flag)
    return jsonify(flag), 201


@app.route("/api/flags/<flag_id>", methods=["DELETE"])
def delete_flag(flag_id):
    for i, flag in enumerate(feature_flags):
        if flag["id"] == flag_id:
            feature_flags.pop(i)
            return jsonify({"message": "Flag deleted"}), 200
    return jsonify({"error": "Flag not found"}), 404


@app.route("/api/trigger-removal", methods=["POST"])
def trigger_removal():
    data = request.get_json()
    if not data or not data.get("flag_id"):
        return jsonify({"error": "flag_id is required"}), 400

    flag = next((f for f in feature_flags if f["id"] == data["flag_id"]), None)
    if not flag:
        return jsonify({"error": "Flag not found"}), 404

    prompt = (
        f"Remove the feature flag '{flag['name']}' from the repository "
        f"{TARGET_REPO}. Search the codebase for any references to "
        f"'{flag['name']}' including environment variables, conditionals, "
        f"and configuration. Remove the flag checks and keep the code path "
        f"that was behind the enabled state of the flag. Create a PR with "
        f"the changes."
    )

    if not DEVIN_API_TOKEN:
        entry = {
            "id": str(uuid.uuid4()),
            "flag_id": flag["id"],
            "flag_name": flag["name"],
            "status": "error",
            "message": "DEVIN_API_TOKEN is not configured",
            "session_url": None,
            "triggered_at": datetime.now(timezone.utc).isoformat(),
        }
        workflow_history.insert(0, entry)
        return jsonify(entry), 500

    headers = {
        "Authorization": f"Bearer {DEVIN_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "prompt": prompt,
        "title": f"Remove feature flag: {flag['name']}",
    }

    try:
        resp = requests.post(DEVIN_API_URL, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        flag["status"] = "removing"

        entry = {
            "id": str(uuid.uuid4()),
            "flag_id": flag["id"],
            "flag_name": flag["name"],
            "status": "triggered",
            "message": "Devin session created",
            "session_url": result.get("url"),
            "session_id": result.get("session_id"),
            "triggered_at": datetime.now(timezone.utc).isoformat(),
        }
        workflow_history.insert(0, entry)
        return jsonify(entry), 200

    except requests.exceptions.RequestException as e:
        entry = {
            "id": str(uuid.uuid4()),
            "flag_id": flag["id"],
            "flag_name": flag["name"],
            "status": "error",
            "message": str(e),
            "session_url": None,
            "triggered_at": datetime.now(timezone.utc).isoformat(),
        }
        workflow_history.insert(0, entry)
        return jsonify(entry), 500


@app.route("/api/history", methods=["GET"])
def get_history():
    return jsonify(workflow_history)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
