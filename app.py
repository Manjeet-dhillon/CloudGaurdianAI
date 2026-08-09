"""
CloudGuardian AI - advisory remediation for cloud error events.

Receives error events via webhook, sends them to the OpenAI API,
and returns a plain-language explanation with a suggested fix.
The developer decides whether to apply it.
"""

import itertools
import os
import json
import queue
import time
import logging
from flask import Flask, request, jsonify
from openai import OpenAI

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You are assisting a developer who has received an error \
from their cloud infrastructure. Respond with three clearly labelled sections:

CAUSE: what has gone wrong, in plain language.
FIX: the specific steps to resolve it.
CHECK: how to confirm the fix worked.

Be concise and specific. If the error data is insufficient to diagnose the \
problem confidently, say so and state what additional information is needed. \
Do not invent details that are not present in the error data."""
results_log = []
result_counter = itertools.count(1)


def build_prompt(payload):
    """Turn the webhook payload into a structured prompt for the model."""
    service = payload.get("service", "unknown service")
    environment = payload.get("environment", "unknown environment")
    error_type = payload.get("error_type", "unspecified")
    message = payload.get("message", "")
    logs = payload.get("logs", "")

    return (
        f"Service: {service}\n"
        f"Environment: {environment}\n"
        f"Error type: {error_type}\n"
        f"Message: {message}\n\n"
        f"Log output:\n{logs}"
    )


@app.route("/health", methods=["GET"])
def health():
    """Simple check that the service is running."""
    return jsonify({"status": "ok"}), 200


@app.route("/results")
def get_results():
    """
    The UI calls this every 1.5 seconds asking 'anything new since
    my last check?' Much simpler and more reliable than a permanently
    open connection - just an ordinary request/response, every time.
    """
    since = request.args.get("since", 0, type=int)
    new_results = [r for r in results_log if r["id"] > since]
    return jsonify(new_results), 200


@app.route("/webhook", methods=["POST"])
def webhook():
    """Receive an error event and return a remediation suggestion."""
    payload = request.get_json(silent=True)

    if not payload:
        return jsonify({"error": "Expected a JSON payload"}), 400

    if not payload.get("message") and not payload.get("logs"):
        return jsonify({"error": "Payload must contain 'message' or 'logs'"}), 400

    prompt = build_prompt(payload)
    app.logger.info("Received error event from %s",
                    payload.get("service", "unknown"))

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        suggestion = response.choices[0].message.content

    except Exception as exc:
        app.logger.error("OpenAI API call failed: %s", exc)
        return jsonify({"error": "Could not generate a suggestion"}), 502

    result = {
        "id": next(result_counter),
        "service": payload.get("service"),
        "error_type": payload.get("error_type"),
        "suggestion": suggestion,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    results_log.append(result)
    return jsonify(result), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
