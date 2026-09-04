CREATE TABLE IF NOT EXISTS servers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT UNIQUE NOT NULL,
    guild_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    discord_user_id TEXT NOT NULL,
    username TEXT,
    display_name TEXT,
    is_active INTEGER DEFAULT 1,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(guild_id, discord_user_id),

    FOREIGN KEY (guild_id)
        REFERENCES servers(guild_id)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id TEXT NOT NULL,
    boss_name TEXT NOT NULL,

    created_by TEXT NOT NULL,

    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,

    duration_minutes INTEGER DEFAULT 60,

    points_value INTEGER DEFAULT 1,

    status TEXT DEFAULT 'open',

    discord_channel_id TEXT,
    discord_message_id TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (guild_id)
        REFERENCES servers(guild_id)
);

CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    event_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,

    attended INTEGER DEFAULT 0,

    marked_at TIMESTAMP,
    marked_by TEXT,

    points_awarded INTEGER DEFAULT 0,

    UNIQUE(event_id, member_id),

    FOREIGN KEY (event_id)
        REFERENCES events(id),

    FOREIGN KEY (member_id)
        REFERENCES members(id)
);

CREATE TABLE IF NOT EXISTS points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    guild_id TEXT NOT NULL,
    member_id INTEGER NOT NULL,

    total_points INTEGER DEFAULT 0,

    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(guild_id, member_id),

    FOREIGN KEY (member_id)
        REFERENCES members(id)
);