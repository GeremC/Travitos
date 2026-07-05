#!/usr/bin/env python3
"""Point d'entrée de l'interface web Travitos.

Usage :
    python gui.py

Puis ouvrir http://localhost:5000
"""

import argparse
import webbrowser

from gui_app.server import app


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Interface web Travitos")
    ap.add_argument("--port", type=int, default=5000,
                    help="port (défaut: 5000)")
    ap.add_argument("--sans-navigateur", action="store_true",
                    help="n'ouvre pas le navigateur automatiquement")
    args = ap.parse_args()
    if not args.sans_navigateur:
        webbrowser.open(f"http://localhost:{args.port}")
    app.run(debug=False, port=args.port)
