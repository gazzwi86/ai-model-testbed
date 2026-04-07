"""
User Management Module
Handles user CRUD operations, authentication, rendering, and reporting.
"""

import os
import sqlite3
import hashlib
import threading
import json

# BUG 7: Memory leak - _audit_log grows unboundedly and is never cleared
_audit_log = []

# BUG 6: Race condition - shared mutable counter without proper locking
_user_counter = 0
_counter_lock = threading.Lock()  # exists but is NOT used in increment_counter


# BUG 4: Hardcoded credentials
DB_PATH = "/var/data/users.db"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "SuperSecret123!"
API_KEY = "sk-live-4f3c2a1b0e9d8c7f6a5b4c3d2e1f0a9b"


class UserManager:
    """
    BUG 1: God class -- this single class handles:
      1. Database connection management
      2. User CRUD (create, read, update, delete)
      3. Authentication and password hashing
      4. HTML rendering of user profiles
      5. CSV report generation
      6. Audit logging
    It should be decomposed into smaller, focused classes.
    """

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.conn = None
        self.users_cache = {}

    # --- Database ---

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        if self.conn:
            self.conn.close()

    # --- CRUD ---

    def create_user(self, username, email, password, role="user"):
        """Create a new user in the database."""
        # BUG 2: Missing input validation - no checks on username length,
        # email format, password strength, or allowed role values
        hashed = self._hash_password(password)
        # BUG 3: SQL injection - string formatting used instead of parameterised query
        query = (
            f"INSERT INTO users (username, email, password_hash, role) "
            f"VALUES ('{username}', '{email}', '{hashed}', '{role}')"
        )
        self.conn.execute(query)
        self.conn.commit()
        self._log_action("create_user", username)
        increment_counter()
        return True

    def get_user(self, user_id):
        """Retrieve a user by ID."""
        # BUG 3 (cont.): SQL injection in another query
        query = f"SELECT * FROM users WHERE id = {user_id}"
        cursor = self.conn.execute(query)
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def update_user(self, user_id, **fields):
        """Update user fields."""
        set_clauses = ", ".join(
            f"{key} = '{value}'" for key, value in fields.items()
        )
        query = f"UPDATE users SET {set_clauses} WHERE id = {user_id}"
        self.conn.execute(query)
        self.conn.commit()
        self._log_action("update_user", str(user_id))

    def delete_user(self, user_id):
        """Delete a user by ID."""
        query = f"DELETE FROM users WHERE id = {user_id}"
        self.conn.execute(query)
        self.conn.commit()
        self._log_action("delete_user", str(user_id))

    def list_users(self, role_filter=None):
        """List users, optionally filtered by role."""
        if role_filter:
            query = f"SELECT * FROM users WHERE role = '{role_filter}'"
        else:
            query = "SELECT * FROM users"
        cursor = self.conn.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    # --- Authentication ---

    def _hash_password(self, password):
        return hashlib.md5(password.encode()).hexdigest()

    def authenticate(self, username, password):
        """Authenticate a user by username and password."""
        hashed = self._hash_password(password)
        query = f"SELECT * FROM users WHERE username = '{username}' AND password_hash = '{hashed}'"
        cursor = self.conn.execute(query)
        user = cursor.fetchone()
        if user:
            return dict(user)
        return None

    # --- HTML Rendering ---

    def render_user_profile(self, user_id):
        """Render an HTML snippet for a user's profile page."""
        user = self.get_user(user_id)
        if not user:
            return "<p>User not found.</p>"
        # BUG 8: XSS vulnerability - user-supplied data is interpolated
        # directly into HTML without escaping
        html = f"""
        <div class="profile">
            <h2>{user['username']}</h2>
            <p>Email: {user['email']}</p>
            <p>Role: {user['role']}</p>
        </div>
        """
        return html

    def render_user_list_page(self, users):
        """Render a full user list as HTML."""
        rows = ""
        for u in users:
            # BUG 8 (cont.): XSS again
            rows += (
                f"<tr><td>{u['username']}</td>"
                f"<td>{u['email']}</td>"
                f"<td>{u['role']}</td></tr>\n"
            )
        return f"<table><thead><tr><th>Name</th><th>Email</th><th>Role</th></tr></thead><tbody>{rows}</tbody></table>"

    # --- CSV Reporting ---

    def export_users_csv(self, filepath):
        """Export all users to a CSV file."""
        users = self.list_users()
        # BUG 5: No error handling on file I/O - if directory doesn't exist
        # or permissions are wrong, this crashes with an unhandled exception
        f = open(filepath, "w")
        f.write("id,username,email,role\n")
        for u in users:
            f.write(f"{u['id']},{u['username']},{u['email']},{u['role']}\n")
        f.close()

    def import_users_csv(self, filepath):
        """Import users from a CSV file."""
        # BUG 5 (cont.): No error handling -- file may not exist
        with open(filepath, "r") as f:
            lines = f.readlines()
        for line in lines[1:]:
            parts = line.strip().split(",")
            self.create_user(parts[0], parts[1], "default_password", parts[2])

    # --- Audit ---

    def _log_action(self, action, detail):
        """Log an action to the in-memory audit trail."""
        # BUG 7: _audit_log is a module-level list that grows without bound
        _audit_log.append({
            "action": action,
            "detail": detail,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        })

    def get_audit_log(self):
        return list(_audit_log)


def increment_counter():
    """Increment the global user counter.

    BUG 6: Race condition -- _counter_lock exists but is not acquired here,
    so concurrent calls can lose increments.
    """
    global _user_counter
    # Should be: with _counter_lock: _user_counter += 1
    current = _user_counter
    _user_counter = current + 1


def check_admin_access(username, password):
    """Check hardcoded admin credentials."""
    # BUG 4 (cont.): Hardcoded credentials used for comparison
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD
