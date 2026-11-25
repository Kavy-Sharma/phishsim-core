import os
import sys
import time
import socket
import secrets
import base64
import subprocess
import pytest

def get_free_port():
    """Finds a free port on localhost by binding to 0."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        return s.getsockname()[1]

def is_port_open(host="127.0.0.1", port=5050):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(0.5)
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

def check_mysql_reachable():
    """Checks whether the MySQL database is reachable using configured environment."""
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "phishsim_db"),
            connection_timeout=3
        )
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        return True, None
    except Exception as e:
        return False, str(e)

def start_test_server(port=None):
    """Starts a Flask server on an isolated free port with complete test environment variables.
    Skips the calling test if MySQL is not reachable.
    """
    is_ok, err = check_mysql_reachable()
    if not is_ok:
        pytest.skip(f"MySQL database is not reachable ({err}). Set DB_* environment variables to run browser tests.")

    if port is None:
        port = get_free_port()

    base_url = f"http://127.0.0.1:{port}"

    # Build full hermetic environment
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["APP_BASE_URL"] = base_url
    env.setdefault("DB_HOST", os.getenv("DB_HOST", "localhost"))
    env.setdefault("DB_PORT", str(os.getenv("DB_PORT", 3306)))
    env.setdefault("DB_USER", os.getenv("DB_USER", "root"))
    env.setdefault("DB_PASSWORD", os.getenv("DB_PASSWORD", ""))
    env.setdefault("DB_NAME", os.getenv("DB_NAME", "phishsim_db"))
    env.setdefault("FLASK_SECRET_KEY", secrets.token_hex(32))
    env.setdefault("DECOY_ENCRYPTION_KEY", base64.b64encode(secrets.token_bytes(32)).decode())
    env["FLASK_DEBUG"] = "false"

    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scratch_dir = os.path.join(root_dir, "scratch")
    os.makedirs(scratch_dir, exist_ok=True)
    log_file = open(os.path.join(scratch_dir, f"flask_test_server_{port}.log"), "w", encoding="utf-8")

    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=root_dir,
        env=env
    )

    # Wait up to 30 seconds for server to be responsive
    for _ in range(60):
        if is_port_open("127.0.0.1", port):
            print(f"[SERVER] Test Flask server ready on {base_url}")
            return proc, base_url, port
        time.sleep(0.5)

    try:
        proc.terminate()
    except Exception:
        pass
    raise RuntimeError(f"Could not start Flask server on port {port}. Check scratch/flask_test_server_{port}.log")

def stop_test_server(proc):
    """Safely terminates the test server process."""
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
