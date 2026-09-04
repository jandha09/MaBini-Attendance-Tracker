# MaBini-Attendance-Tracker
Discord attendance bot built with Python, Discord.py, and SQLite. It tracks event attendance, manages member participation, awards points, and provides a leaderboard through Discord commands and interactive buttons.

# Discord Attendance Bot

A Discord attendance management bot built with Python, Discord.py, and SQLite.

## Features

- Create attendance events for different bosses
- Default event duration of 60 minutes
- Track server members for each event
- Mark attendance using an interactive button
- Management controls for authorized officers
- Add or remove attendance for members
- Automatically award attendance points
- Adjust or reset member points
- View an attendance leaderboard
- Store attendance and points data using SQLite

## Commands

/event create

/leaderboard

/ping

/points adjust

/points reset

/points reset_all

## Attendance Controls

✅ I ATTENDED  
Marks yourself as attended.

🛠️ MANAGE ATTENDANCE  
Allows authorized officers to add or remove attendance for members.

## Technologies

- Python
- Discord.py
- SQLite
- Discord Interactions / Slash Commands
- SQLite database

## Project Structure

    main.py
    database.py
    schema.sql
    requirements.txt
    .env
    attendance.db

## Setup

1. Install Python.

2. Install the required packages:

    pip install -r requirements.txt

3. Create a `.env` file:

    DISCORD_TOKEN=your_discord_bot_token

4. Create the SQLite database using the provided schema.

5. Run the bot:

    python main.py

## Database

The bot uses SQLite to store:

- Servers
- Members
- Events
- Attendance
- Points

## Notes

This project was built as a practical automation and software development project to learn Python, Discord bot development, databases, and workflow logic.

The bot is intended for managing attendance and participation within a Discord community.
