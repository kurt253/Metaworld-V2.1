"""
start_services.py — Start auth_service, data_service en career_service tegelijk.

Gebruik:
    python Scripts/start_services.py

Alle services stoppen via Ctrl+C.
"""

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth_service   import app as auth_app
from data_service   import app as data_app
from career_service import app as career_app


def _run(app, port):
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


print("=" * 60)
print("  Metaworld v2 – Alle diensten")
print()
print("  FAS (aanmelden)   →  http://localhost:5001")
print("  Datadienst        →  http://localhost:5002")
print("  Loopbaandienst    →  http://localhost:5003")
print()
print("  Stoppen: Ctrl+C")
print("=" * 60)

t1 = threading.Thread(target=_run, args=(auth_app,   5001), daemon=True)
t2 = threading.Thread(target=_run, args=(data_app,   5002), daemon=True)
t3 = threading.Thread(target=_run, args=(career_app, 5003), daemon=True)
t1.start()
t2.start()
t3.start()

try:
    t1.join()
    t2.join()
    t3.join()
except KeyboardInterrupt:
    print("\nStoppen…")
