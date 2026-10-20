import sqlite3
from flask import Flask, redirect, render_template, request

app = Flask(__name__)
DATABASE = "casefile.db"


def connect_db():
    connection = sqlite3.connect(DATABASE)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with connect_db() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS Investigators (
                investigator_id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE,
                role TEXT
            );

            CREATE TABLE IF NOT EXISTS Cases (
                case_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'Open',
                investigator_id INTEGER,
                FOREIGN KEY (investigator_id)
                    REFERENCES Investigators(investigator_id)
            );

            CREATE TABLE IF NOT EXISTS Suspects (
                suspect_id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                full_name TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (case_id) REFERENCES Cases(case_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS Evidence (
                evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                collected_at TEXT,
                FOREIGN KEY (case_id) REFERENCES Cases(case_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS Witnesses (
                witness_id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                full_name TEXT NOT NULL,
                statement TEXT,
                FOREIGN KEY (case_id) REFERENCES Cases(case_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS Case_Activity (
                activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                activity TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES Cases(case_id)
                    ON DELETE CASCADE
            );
        """)

        case_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(Cases)")
        }

        if "investigator_id" not in case_columns:
            connection.execute("""
                ALTER TABLE Cases
                ADD COLUMN investigator_id INTEGER
                REFERENCES Investigators(investigator_id)
            """)

        connection.executescript("""
            CREATE TRIGGER IF NOT EXISTS log_case_created
            AFTER INSERT ON Cases
            BEGIN
                INSERT INTO Case_Activity (case_id, activity)
                VALUES (NEW.case_id, 'Case created: ' || NEW.title);
            END;

            CREATE TRIGGER IF NOT EXISTS log_case_status_change
            AFTER UPDATE OF status ON Cases
            WHEN OLD.status <> NEW.status
            BEGIN
                INSERT INTO Case_Activity (case_id, activity)
                VALUES (
                    NEW.case_id,
                    'Status changed from ' || OLD.status || ' to ' || NEW.status
                );
            END;
        """)


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        title = request.form["title"].strip()
        description = request.form["description"].strip()
        investigator_id = request.form.get("investigator_id") or None

        if title:
            with connect_db() as connection:
                connection.execute(
                    """
                    INSERT INTO Cases (title, description, investigator_id)
                    VALUES (?, ?, ?)
                    """,
                    (title, description, investigator_id),
                )

        return redirect("/")

    with connect_db() as connection:
        cases = connection.execute("""
            SELECT Cases.case_id, Cases.title, Cases.status,
                   Investigators.full_name
            FROM Cases
            LEFT JOIN Investigators
                ON Cases.investigator_id = Investigators.investigator_id
            ORDER BY Cases.case_id
        """).fetchall()

        investigators = connection.execute("""
            SELECT investigator_id, full_name
            FROM Investigators
            ORDER BY full_name
        """).fetchall()

    return render_template(
        "index.html",
        cases=cases,
        investigators=investigators,
    )


@app.route("/investigators", methods=["GET", "POST"])
def investigators_page():
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        email = request.form["email"].strip() or None
        role = request.form["role"].strip()

        if full_name:
            with connect_db() as connection:
                connection.execute(
                    """
                    INSERT INTO Investigators (full_name, email, role)
                    VALUES (?, ?, ?)
                    """,
                    (full_name, email, role),
                )

        return redirect("/investigators")

    with connect_db() as connection:
        investigators = connection.execute("""
            SELECT investigator_id, full_name, email, role
            FROM Investigators
            ORDER BY full_name
        """).fetchall()

    return render_template(
        "investigators.html",
        investigators=investigators,
    )


@app.route("/cases/<int:case_id>/suspects", methods=["GET", "POST"])
def suspects_page(case_id):
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        notes = request.form["notes"].strip()

        if full_name:
            with connect_db() as connection:
                connection.execute(
                    """
                    INSERT INTO Suspects (case_id, full_name, notes)
                    VALUES (?, ?, ?)
                    """,
                    (case_id, full_name, notes),
                )

        return redirect(f"/cases/{case_id}/suspects")

    with connect_db() as connection:
        case = connection.execute(
            "SELECT case_id, title FROM Cases WHERE case_id = ?",
            (case_id,),
        ).fetchone()

        if case is None:
            return "Case not found", 404

        suspects = connection.execute(
            """
            SELECT suspect_id, full_name, notes
            FROM Suspects
            WHERE case_id = ?
            ORDER BY suspect_id
            """,
            (case_id,),
        ).fetchall()

    return render_template(
        "suspects.html",
        case=case,
        suspects=suspects,
    )


@app.route("/cases/<int:case_id>/evidence", methods=["GET", "POST"])
def evidence_page(case_id):
    if request.method == "POST":
        description = request.form["description"].strip()
        collected_at = request.form["collected_at"].strip() or None

        if description:
            with connect_db() as connection:
                connection.execute(
                    """
                    INSERT INTO Evidence (case_id, description, collected_at)
                    VALUES (?, ?, ?)
                    """,
                    (case_id, description, collected_at),
                )

        return redirect(f"/cases/{case_id}/evidence")

    with connect_db() as connection:
        case = connection.execute(
            "SELECT case_id, title FROM Cases WHERE case_id = ?",
            (case_id,),
        ).fetchone()

        if case is None:
            return "Case not found", 404

        evidence_list = connection.execute(
            """
            SELECT evidence_id, description, collected_at
            FROM Evidence
            WHERE case_id = ?
            ORDER BY evidence_id
            """,
            (case_id,),
        ).fetchall()

    return render_template(
        "evidence.html",
        case=case,
        evidence_list=evidence_list,
    )

@app.route("/cases/<int:case_id>/witnesses", methods=["GET", "POST"])
def witnesses_page(case_id):
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        statement = request.form["statement"].strip()

        if full_name:
            with connect_db() as connection:
                connection.execute(
                    """
                    INSERT INTO Witnesses (case_id, full_name, statement)
                    VALUES (?, ?, ?)
                    """,
                    (case_id, full_name, statement),
                )

        return redirect(f"/cases/{case_id}/witnesses")

    with connect_db() as connection:
        case = connection.execute(
            "SELECT case_id, title FROM Cases WHERE case_id = ?",
            (case_id,),
        ).fetchone()

        if case is None:
            return "Case not found", 404

        witnesses = connection.execute(
            """
            SELECT witness_id, full_name, statement
            FROM Witnesses
            WHERE case_id = ?
            ORDER BY witness_id
            """,
            (case_id,),
        ).fetchall()

    return render_template(
        "witnesses.html",
        case=case,
        witnesses=witnesses,
    )

@app.route("/cases/<int:case_id>/activity", methods=["GET", "POST"])
def activity_page(case_id):
    if request.method == "POST":
        activity = request.form["activity"].strip()

        if activity:
            with connect_db() as connection:
                connection.execute(
                    """
                    INSERT INTO Case_Activity (case_id, activity)
                    VALUES (?, ?)
                    """,
                    (case_id, activity),
                )

        return redirect(f"/cases/{case_id}/activity")

    with connect_db() as connection:
        case = connection.execute(
            "SELECT case_id, title FROM Cases WHERE case_id = ?",
            (case_id,),
        ).fetchone()

        if case is None:
            return "Case not found", 404

        activities = connection.execute(
            """
            SELECT activity_id, activity, created_at
            FROM Case_Activity
            WHERE case_id = ?
            ORDER BY activity_id DESC
            """,
            (case_id,),
        ).fetchall()

    return render_template(
        "activity.html",
        case=case,
        activities=activities,
    )

@app.route("/cases/<int:case_id>/edit", methods=["GET", "POST"])
def edit_case(case_id):
    if request.method == "POST":
        title = request.form["title"].strip()
        description = request.form["description"].strip()
        status = request.form["status"]
        investigator_id = request.form.get("investigator_id") or None

        if title:
            with connect_db() as connection:
                connection.execute(
                    """
                    UPDATE Cases
                    SET title = ?, description = ?, status = ?,
                        investigator_id = ?
                    WHERE case_id = ?
                    """,
                    (title, description, status, investigator_id, case_id),
                )

        return redirect("/")

    with connect_db() as connection:
        case = connection.execute(
            """
            SELECT case_id, title, description, status, investigator_id
            FROM Cases
            WHERE case_id = ?
            """,
            (case_id,),
        ).fetchone()

        if case is None:
            return "Case not found", 404

        investigators = connection.execute(
            """
            SELECT investigator_id, full_name
            FROM Investigators
            ORDER BY full_name
            """
        ).fetchall()

    return render_template(
        "edit_case.html",
        case=case,
        investigators=investigators,
    )


@app.route("/cases/<int:case_id>/delete", methods=["POST"])
def delete_case(case_id):
    with connect_db() as connection:
        connection.execute(
            "DELETE FROM Cases WHERE case_id = ?",
            (case_id,),
        )

    return redirect("/")

@app.route("/suspects/<int:suspect_id>/edit", methods=["GET", "POST"])
def edit_suspect(suspect_id):
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        notes = request.form["notes"].strip()

        with connect_db() as connection:
            suspect = connection.execute(
                "SELECT case_id FROM Suspects WHERE suspect_id = ?",
                (suspect_id,),
            ).fetchone()

            if suspect is None:
                return "Suspect not found", 404

            if full_name:
                connection.execute(
                    """
                    UPDATE Suspects
                    SET full_name = ?, notes = ?
                    WHERE suspect_id = ?
                    """,
                    (full_name, notes, suspect_id),
                )

        return redirect(f"/cases/{suspect[0]}/suspects")

    with connect_db() as connection:
        suspect = connection.execute(
            """
            SELECT suspect_id, case_id, full_name, notes
            FROM Suspects
            WHERE suspect_id = ?
            """,
            (suspect_id,),
        ).fetchone()

    if suspect is None:
        return "Suspect not found", 404

    return render_template("edit_suspect.html", suspect=suspect)


@app.route("/suspects/<int:suspect_id>/delete", methods=["POST"])
def delete_suspect(suspect_id):
    with connect_db() as connection:
        suspect = connection.execute(
            "SELECT case_id FROM Suspects WHERE suspect_id = ?",
            (suspect_id,),
        ).fetchone()

        if suspect is None:
            return "Suspect not found", 404

        connection.execute(
            "DELETE FROM Suspects WHERE suspect_id = ?",
            (suspect_id,),
        )

    return redirect(f"/cases/{suspect[0]}/suspects")

@app.route("/evidence/<int:evidence_id>/edit", methods=["GET", "POST"])
def edit_evidence(evidence_id):
    if request.method == "POST":
        description = request.form["description"].strip()
        collected_at = request.form["collected_at"].strip() or None

        with connect_db() as connection:
            evidence = connection.execute(
                "SELECT case_id FROM Evidence WHERE evidence_id = ?",
                (evidence_id,),
            ).fetchone()

            if evidence is None:
                return "Evidence not found", 404

            if description:
                connection.execute(
                    """
                    UPDATE Evidence
                    SET description = ?, collected_at = ?
                    WHERE evidence_id = ?
                    """,
                    (description, collected_at, evidence_id),
                )

        return redirect(f"/cases/{evidence[0]}/evidence")

    with connect_db() as connection:
        evidence = connection.execute(
            """
            SELECT evidence_id, case_id, description, collected_at
            FROM Evidence
            WHERE evidence_id = ?
            """,
            (evidence_id,),
        ).fetchone()

    if evidence is None:
        return "Evidence not found", 404

    return render_template("edit_evidence.html", evidence=evidence)


@app.route("/evidence/<int:evidence_id>/delete", methods=["POST"])
def delete_evidence(evidence_id):
    with connect_db() as connection:
        evidence = connection.execute(
            "SELECT case_id FROM Evidence WHERE evidence_id = ?",
            (evidence_id,),
        ).fetchone()

        if evidence is None:
            return "Evidence not found", 404

        connection.execute(
            "DELETE FROM Evidence WHERE evidence_id = ?",
            (evidence_id,),
        )

    return redirect(f"/cases/{evidence[0]}/evidence")

@app.route("/witnesses/<int:witness_id>/edit", methods=["GET", "POST"])
def edit_witness(witness_id):
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        statement = request.form["statement"].strip()

        with connect_db() as connection:
            witness = connection.execute(
                "SELECT case_id FROM Witnesses WHERE witness_id = ?",
                (witness_id,),
            ).fetchone()

            if witness is None:
                return "Witness not found", 404

            if full_name:
                connection.execute(
                    """
                    UPDATE Witnesses
                    SET full_name = ?, statement = ?
                    WHERE witness_id = ?
                    """,
                    (full_name, statement, witness_id),
                )

        return redirect(f"/cases/{witness[0]}/witnesses")

    with connect_db() as connection:
        witness = connection.execute(
            """
            SELECT witness_id, case_id, full_name, statement
            FROM Witnesses
            WHERE witness_id = ?
            """,
            (witness_id,),
        ).fetchone()

    if witness is None:
        return "Witness not found", 404

    return render_template("edit_witness.html", witness=witness)


@app.route("/witnesses/<int:witness_id>/delete", methods=["POST"])
def delete_witness(witness_id):
    with connect_db() as connection:
        witness = connection.execute(
            "SELECT case_id FROM Witnesses WHERE witness_id = ?",
            (witness_id,),
        ).fetchone()

        if witness is None:
            return "Witness not found", 404

        connection.execute(
            "DELETE FROM Witnesses WHERE witness_id = ?",
            (witness_id,),
        )

    return redirect(f"/cases/{witness[0]}/witnesses")

@app.route("/investigators/<int:investigator_id>/edit", methods=["GET", "POST"])
def edit_investigator(investigator_id):
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        email = request.form["email"].strip() or None
        role = request.form["role"].strip()

        if full_name:
            with connect_db() as connection:
                connection.execute(
                    """
                    UPDATE Investigators
                    SET full_name = ?, email = ?, role = ?
                    WHERE investigator_id = ?
                    """,
                    (full_name, email, role, investigator_id),
                )

        return redirect("/investigators")

    with connect_db() as connection:
        investigator = connection.execute(
            """
            SELECT investigator_id, full_name, email, role
            FROM Investigators
            WHERE investigator_id = ?
            """,
            (investigator_id,),
        ).fetchone()

    if investigator is None:
        return "Investigator not found", 404

    return render_template(
        "edit_investigator.html",
        investigator=investigator,
    )


@app.route("/investigators/<int:investigator_id>/delete", methods=["POST"])
def delete_investigator(investigator_id):
    with connect_db() as connection:
        investigator = connection.execute(
            "SELECT investigator_id FROM Investigators WHERE investigator_id = ?",
            (investigator_id,),
        ).fetchone()

        if investigator is None:
            return "Investigator not found", 404

        # Keep cases, but make them unassigned before deleting the investigator.
        connection.execute(
            "UPDATE Cases SET investigator_id = NULL WHERE investigator_id = ?",
            (investigator_id,),
        )
        connection.execute(
            "DELETE FROM Investigators WHERE investigator_id = ?",
            (investigator_id,),
        )

    return redirect("/investigators")

@app.route("/search")
def search_cases():
    query = request.args.get("q", "").strip()
    results = []

    if query:
        search_pattern = f"%{query}%"

        with connect_db() as connection:
            results = connection.execute(
                """
                SELECT Cases.case_id, Cases.title, Cases.status,
                       Investigators.full_name
                FROM Cases
                LEFT JOIN Investigators
                    ON Cases.investigator_id = Investigators.investigator_id
                WHERE Cases.title LIKE ?
                   OR Cases.description LIKE ?
                   OR Cases.status LIKE ?
                   OR Investigators.full_name LIKE ?
                ORDER BY Cases.case_id
                """,
                (search_pattern, search_pattern, search_pattern, search_pattern),
            ).fetchall()

    return render_template(
        "search.html",
        query=query,
        results=results,
    )

@app.route("/dashboard")
def dashboard():
    with connect_db() as connection:
        counts = {
            "cases": connection.execute(
                "SELECT COUNT(*) FROM Cases"
            ).fetchone()[0],
            "open_cases": connection.execute(
                "SELECT COUNT(*) FROM Cases WHERE status = 'Open'"
            ).fetchone()[0],
            "investigators": connection.execute(
                "SELECT COUNT(*) FROM Investigators"
            ).fetchone()[0],
            "suspects": connection.execute(
                "SELECT COUNT(*) FROM Suspects"
            ).fetchone()[0],
            "evidence": connection.execute(
                "SELECT COUNT(*) FROM Evidence"
            ).fetchone()[0],
            "witnesses": connection.execute(
                "SELECT COUNT(*) FROM Witnesses"
            ).fetchone()[0],
        }

    return render_template("dashboard.html", counts=counts)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)