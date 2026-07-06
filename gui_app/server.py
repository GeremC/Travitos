"""Flask server : routes, SSE, sous-processus du scan."""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from queue import Queue

from flask import Flask, Response, jsonify, render_template, request, send_from_directory

import config

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "sortie"

app = Flask(__name__, template_folder=RACINE / "templates")

process = None
output_queue = Queue()


def run_scan(args_list):
    global process
    env = os.environ.copy()
    process = subprocess.Popen(
        [sys.executable, str(RACINE / "main.py")] + args_list,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=env, text=True, bufsize=1,
    )
    for line in process.stdout:
        output_queue.put(line)
    process.wait()
    output_queue.put(None)
    process = None


@app.route("/")
def index():
    return render_template("gui.html", naf_codes=config.NAF_CODES)


@app.route("/run", methods=["POST"])
def run():
    global process, output_queue
    if process is not None:
        return jsonify({"error": "Un scan est déjà en cours"}), 409

    data = request.get_json()
    args = ["--mode", data.get("mode", "reprise")]

    max_ent = data.get("max_entreprises", "")
    if max_ent:
        args.extend(["--max-entreprises", str(max_ent)])

    naf = data.get("naf", [])
    if naf:
        args.extend(["--naf"] + naf)

    if data.get("verbeux"):
        args.append("-v")

    while not output_queue.empty():
        output_queue.get()

    threading.Thread(target=run_scan, args=(args,), daemon=True).start()
    return jsonify({"status": "ok"})


@app.route("/stream")
def stream():
    def generate():
        while True:
            line = output_queue.get()
            if line is None:
                break
            yield f"data: {json.dumps(line.rstrip())}\n\n"
        yield "data: null\n\n"
    return Response(generate(), mimetype="text/event-stream")


@app.route("/sortie/<path:filename>")
def sortie_files(filename):
    return send_from_directory(SORTIE, filename)


@app.route("/cancel", methods=["POST"])
def cancel():
    global process
    if process is not None:
        proc = process
        process = None
        proc.kill()
        return jsonify({"status": "ok"})
    return jsonify({"status": "aucun_scan"}), 400


@app.route("/rapport-existe")
def rapport_existe():
    return jsonify({
        "rapport": (SORTIE / "rapport.html").exists(),
        "resultats": (SORTIE / "resultats.csv").exists(),
        "entreprises": (SORTIE / "entreprises.csv").exists(),
    })
