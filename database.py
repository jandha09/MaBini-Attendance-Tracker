import sqlite3

DATABASE = "attendance.db"


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_connection()

    with open("schema.sql", "r", encoding="utf-8") as file:
        schema = file.read()

    connection.executescript(schema)
    connection.commit()
    connection.close()

    print("Database initialized.")


def add_server(guild_id, guild_name):
    connection = get_connection()

    connection.execute(
        """
        INSERT INTO servers (guild_id, guild_name)
        VALUES (?, ?)
        ON CONFLICT(guild_id)
        DO UPDATE SET guild_name = excluded.guild_name
        """,
        (str(guild_id), guild_name)
    )

    connection.commit()
    connection.close()


def create_event(
    guild_id,
    boss_name,
    created_by,
    duration_minutes=60,
    points_value=1,
    channel_id=None
):
    connection = get_connection()

    connection.execute(
        """
        INSERT INTO events (
            guild_id,
            boss_name,
            created_by,
            duration_minutes,
            points_value,
            discord_channel_id
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(guild_id),
            boss_name,
            str(created_by),
            duration_minutes,
            points_value,
            str(channel_id) if channel_id else None
        )
    )

    connection.commit()

    event = connection.execute(
        """
        SELECT *
        FROM events
        WHERE id = last_insert_rowid()
        """
    ).fetchone()

    connection.close()

    return event["id"]


def create_attendance_records(event_id, guild_id, members):
    connection = get_connection()

    for member in members:

        if member.bot:
            continue

        connection.execute(
            """
            INSERT INTO members (
                guild_id,
                discord_user_id,
                username,
                display_name,
                is_active
            )
            VALUES (?, ?, ?, ?, 1)

            ON CONFLICT(guild_id, discord_user_id)
            DO UPDATE SET
                username = excluded.username,
                display_name = excluded.display_name,
                is_active = 1
            """,
            (
                str(guild_id),
                str(member.id),
                member.name,
                member.display_name
            )
        )

        member_row = connection.execute(
            """
            SELECT id
            FROM members
            WHERE guild_id = ?
            AND discord_user_id = ?
            """,
            (str(guild_id), str(member.id))
        ).fetchone()

        connection.execute(
            """
            INSERT OR IGNORE INTO attendance (
                event_id,
                member_id
            )
            VALUES (?, ?)
            """,
            (
                event_id,
                member_row["id"]
            )
        )

    connection.commit()
    connection.close()


def get_event(event_id):
    connection = get_connection()

    event = connection.execute(
        """
        SELECT *
        FROM events
        WHERE id = ?
        """,
        (event_id,)
    ).fetchone()

    connection.close()

    return event


def mark_attendance(event_id, guild_id, discord_user_id, points):
    connection = get_connection()

    # Find the member
    member = connection.execute(
        """
        SELECT id, display_name
        FROM members
        WHERE guild_id = ?
        AND discord_user_id = ?
        """,
        (guild_id, discord_user_id)
    ).fetchone()

    if not member:
        connection.close()
        return False, "Member not found."

    # Find this member's attendance record for this event
    attendance = connection.execute(
        """
        SELECT id, attended, points_awarded
        FROM attendance
        WHERE event_id = ?
        AND member_id = ?
        """,
        (event_id, member["id"])
    ).fetchone()

    if not attendance:
        connection.close()
        return False, "Attendance record not found."

    # IMPORTANT:
    # The record existing does NOT mean they already attended.
    # We must check the attended column.
    if attendance["attended"] == 1:
        connection.close()
        return False, "already_attended"

    # Mark attendance
    connection.execute(
        """
        UPDATE attendance
        SET attended = 1,
            marked_at = CURRENT_TIMESTAMP,
            marked_by = ?,
            points_awarded = ?
        WHERE event_id = ?
        AND member_id = ?
        """,
        (
            discord_user_id,
            points,
            event_id,
            member["id"]
        )
    )

    # Add points to the member's total
    connection.execute(
        """
        INSERT INTO points (
            guild_id,
            member_id,
            total_points
        )
        VALUES (?, ?, ?)
        ON CONFLICT(guild_id, member_id)
        DO UPDATE SET
            total_points = points.total_points + excluded.total_points,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            guild_id,
            member["id"],
            points
        )
    )

    connection.commit()
    connection.close()

    return True, "success"


def remove_attendance(event_id, guild_id, discord_user_id):

    connection = get_connection()

    # Find the member
    member = connection.execute(
        """
        SELECT id, display_name
        FROM members
        WHERE guild_id = ?
        AND discord_user_id = ?
        """,
        (guild_id, discord_user_id)
    ).fetchone()

    if not member:
        connection.close()
        return False, "Member not found.", None

    # Find attendance record
    attendance = connection.execute(
        """
        SELECT id, attended, points_awarded
        FROM attendance
        WHERE event_id = ?
        AND member_id = ?
        """,
        (event_id, member["id"])
    ).fetchone()

    if not attendance:
        connection.close()
        return False, "Attendance record not found.", member["display_name"]

    # Already not attended
    if attendance["attended"] != 1:
        connection.close()
        return False, "not_attended", member["display_name"]

    # Save the points before clearing them
    points_to_remove = attendance["points_awarded"] or 0

    # Remove attendance
    connection.execute(
        """
        UPDATE attendance
        SET attended = 0,
            marked_at = NULL,
            marked_by = NULL,
            points_awarded = 0
        WHERE event_id = ?
        AND member_id = ?
        """,
        (
            event_id,
            member["id"]
        )
    )

    # Remove the points
    connection.execute(
        """
        UPDATE points
        SET total_points = MAX(0, total_points - ?),
            updated_at = CURRENT_TIMESTAMP
        WHERE guild_id = ?
        AND member_id = ?
        """,
        (
            points_to_remove,
            guild_id,
            member["id"]
        )
    )

    connection.commit()
    connection.close()

    return True, "success", member["display_name"]

def get_event_attendance(event_id):
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT
            members.discord_user_id,
            members.display_name,
            attendance.attended
        FROM attendance
        JOIN members
            ON attendance.member_id = members.id
        WHERE attendance.event_id = ?
        ORDER BY members.display_name COLLATE NOCASE
        """,
        (event_id,)
    ).fetchall()

    connection.close()

    return rows

def get_attendance_count(event_id):
    connection = get_connection()

    row = connection.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN attended = 1 THEN 1 ELSE 0 END) AS attended
        FROM attendance
        WHERE event_id = ?
        """,
        (event_id,)
    ).fetchone()

    connection.close()

    total = row["total"] if row else 0
    attended = row["attended"] if row and row["attended"] else 0

    return total, attended

def get_leaderboard(guild_id):
    connection = get_connection()

    rows = connection.execute(
        """
        SELECT
            members.discord_user_id,
            members.display_name,
            COALESCE(points.total_points, 0) AS total_points
        FROM members
        LEFT JOIN points
            ON members.id = points.member_id
            AND points.guild_id = members.guild_id
        WHERE members.guild_id = ?
        AND members.is_active = 1
        ORDER BY total_points DESC,
                 members.display_name COLLATE NOCASE ASC
        """,
        (str(guild_id),)
    ).fetchall()

    connection.close()

    return rows

def adjust_points(guild_id, discord_user_id, amount):
    connection = get_connection()

    member = connection.execute(
        """
        SELECT id, display_name
        FROM members
        WHERE guild_id = ?
        AND discord_user_id = ?
        """,
        (str(guild_id), str(discord_user_id))
    ).fetchone()

    if not member:
        connection.close()
        return False, "Member not found.", None, None

    # Make sure a points record exists
    connection.execute(
        """
        INSERT INTO points (
            guild_id,
            member_id,
            total_points
        )
        VALUES (?, ?, 0)
        ON CONFLICT(guild_id, member_id)
        DO NOTHING
        """,
        (
            str(guild_id),
            member["id"]
        )
    )

    # Adjust points, but never allow a negative balance
    connection.execute(
        """
        UPDATE points
        SET total_points = MAX(0, total_points + ?),
            updated_at = CURRENT_TIMESTAMP
        WHERE guild_id = ?
        AND member_id = ?
        """,
        (
            amount,
            str(guild_id),
            member["id"]
        )
    )

    row = connection.execute(
        """
        SELECT total_points
        FROM points
        WHERE guild_id = ?
        AND member_id = ?
        """,
        (
            str(guild_id),
            member["id"]
        )
    ).fetchone()

    connection.commit()
    connection.close()

    return True, "success", member["display_name"], row["total_points"]

def reset_points(guild_id, discord_user_id):
    connection = get_connection()

    member = connection.execute(
        """
        SELECT id, display_name
        FROM members
        WHERE guild_id = ?
        AND discord_user_id = ?
        """,
        (str(guild_id), str(discord_user_id))
    ).fetchone()

    if not member:
        connection.close()
        return False, "Member not found.", None

    connection.execute(
        """
        INSERT INTO points (
            guild_id,
            member_id,
            total_points
        )
        VALUES (?, ?, 0)
        ON CONFLICT(guild_id, member_id)
        DO UPDATE SET
            total_points = 0,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            str(guild_id),
            member["id"]
        )
    )

    connection.commit()
    connection.close()

    return True, "success", member["display_name"]

def reset_all_points(guild_id):
    connection = get_connection()

    connection.execute(
        """
        UPDATE points
        SET total_points = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE guild_id = ?
        """,
        (str(guild_id),)
    )

    connection.commit()
    connection.close()

    return True