import os
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

from database import (
    initialize_database,
    add_server,
    create_event,
    create_attendance_records,
    get_event,
    mark_attendance,
    remove_attendance,
    get_attendance_count,
    get_event_attendance,
    get_leaderboard,
    adjust_points,
    reset_points,
    reset_all_points
)


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")


# --------------------------------------------------
# BOT SETUP
# --------------------------------------------------

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned,
    intents=intents
)


# --------------------------------------------------
# ATTENDANCE MANAGEMENT ROLES
# --------------------------------------------------

MANAGEMENT_ROLES = {
    "core",
    "officer",
    "officers",
    "TENCHU_L9_Core",
    "L9_Core_Sub"
}


def can_manage_attendance(member: discord.Member):

    # Server Administrator
    if member.guild_permissions.administrator:
        return True

    # Check Discord roles
    for role in member.roles:

        if role.name.lower() in MANAGEMENT_ROLES:
            return True

    return False


# --------------------------------------------------
# CREATE EVENT EMBED
# --------------------------------------------------

def create_event_embed(event_id):

    event = get_event(event_id)

    if event is None:
        return None

    total, attended = get_attendance_count(event_id)

    attendance_rows = get_event_attendance(event_id)

    member_list = []

    for row in attendance_rows:
        display_name = row[1]
        attended_status = int(row[2])

        if attended_status == 1:
            member_list.append(f"✅ {display_name}")
        else:
            member_list.append(f"⬜ {display_name}")

    # Put each member on a separate line
    member_text = "\n".join(member_list)

    if len(member_text) > 3500:
        member_text = (
            member_text[:3400]
            + "\n\n...member list continues..."
        )

    status_text = "🟢 OPEN"

    embed = discord.Embed(
        title=f"⚔️ {event['boss_name'].upper()}",
        description=(
            "**Attendance is OPEN!**\n\n"
            f"{member_text}"
        ),
        color=discord.Color.green()
    )

    embed.add_field(
        name="👥 Attendance",
        value=f"**{attended} / {total}**",
        inline=True
    )

    embed.add_field(
        name="⭐ Points",
        value=str(event["points_value"]),
        inline=True
    )

    embed.add_field(
        name="⏰ Duration",
        value=f"{event['duration_minutes']} minutes",
        inline=True
    )

    embed.add_field(
        name="🆔 Event ID",
        value=str(event_id),
        inline=True
    )

    embed.add_field(
        name="Status",
        value=status_text,
        inline=True
    )

    embed.set_footer(
        text="Click ✅ I ATTENDED if you participated."
    )

    return embed

async def update_event_message(event_id):
    event = get_event(event_id)

    if event is None:
        return

    channel_id = event["discord_channel_id"]
    message_id = event["discord_message_id"]

    if not channel_id or not message_id:
        return

    channel = bot.get_channel(int(channel_id))

    if channel is None:
        return

    try:
        message = await channel.fetch_message(int(message_id))
    except discord.NotFound:
        return
    except discord.Forbidden:
        return
    except discord.HTTPException:
        return

    embed = create_event_embed(event_id)

    if embed is None:
        return

    await message.edit(
        embed=embed,
        view=AttendanceView(event_id)
    )


# --------------------------------------------------
# MEMBER SELECTION MENU
# --------------------------------------------------

class MemberSelect(discord.ui.Select):

    def __init__(self, event_id, members):

        self.event_id = event_id

        options = []

        for member in members[:25]:

            options.append(
                discord.SelectOption(
                    label=member.display_name[:100],
                    value=str(member.id)
                )
            )

        super().__init__(
            placeholder="Select a member...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        # Check permissions
        if not can_manage_attendance(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ You don't have permission to manage attendance.",
                ephemeral=True
            )
            return

        member_id = int(
            self.values[0]
        )

        member = interaction.guild.get_member(
            member_id
        )

        if member is None:

            await interaction.response.send_message(
                "❌ Member could not be found.",
                ephemeral=True
            )
            return

        event = get_event(
            self.event_id
        )

        if event is None:

            await interaction.response.send_message(
                "❌ Event could not be found.",
                ephemeral=True
            )
            return

        # Get current attendance status
        rows = get_event_attendance(
            self.event_id
        )

        attended = False

        for row in rows:

            if int(row["discord_user_id"]) == member.id:

                attended = bool(
                    row["attended"]
                )

                break

        view = ManageMemberView(
            event_id=self.event_id,
            member=member,
            attended=attended
        )

        status = (
            "✅ Attended"
            if attended
            else "⬜ Not Attended"
        )

        await interaction.response.edit_message(
            content=(
                f"🛠️ **Manage Attendance**\n\n"
                f"👤 **{member.display_name}**\n"
                f"Status: {status}"
            ),
            view=view
        )

# --------------------------------------------------
# MANAGE MEMBER VIEW
# --------------------------------------------------

class ManageMemberView(discord.ui.View):

    def __init__(
        self,
        event_id,
        member,
        attended
    ):

        super().__init__(
            timeout=120
        )

        self.event_id = event_id
        self.member = member
        self.attended = attended

        # Disable inappropriate button
        self.add_item(
            AddAttendanceButton(
                event_id,
                member,
                disabled=attended
            )
        )

        self.add_item(
            RemoveAttendanceButton(
                event_id,
                member,
                disabled=not attended
            )
        )

        self.add_item(
            BackToManageButton(
                event_id
            )
        )
class AddAttendanceButton(
    discord.ui.Button
):

    def __init__(
        self,
        event_id,
        member,
        disabled=False
    ):

        super().__init__(
            label="ADD ATTENDANCE",
            emoji="✅",
            style=discord.ButtonStyle.success,
            disabled=disabled
        )

        self.event_id = event_id
        self.member = member

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if not can_manage_attendance(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ You don't have permission to manage attendance.",
                ephemeral=True
            )

            return

        event = get_event(
            self.event_id
        )

        if event is None:

            await interaction.response.send_message(
                "❌ Event not found.",
                ephemeral=True
            )

            return

        success, reason = mark_attendance(
            self.event_id,
            interaction.guild.id,
            self.member.id,
            event["points_value"]
        )

        if not success:

            if reason == "already_attended":

                await interaction.response.send_message(
                    "ℹ️ This member is already marked as attended.",
                    ephemeral=True
                )

            else:

                await interaction.response.send_message(
                    "❌ Could not add attendance.",
                    ephemeral=True
                )

            return

        await update_event_message(
            self.event_id
        )

        await interaction.response.send_message(
            f"✅ Attendance added for **{self.member.display_name}**.",
            ephemeral=True
        )

class RemoveAttendanceButton(
    discord.ui.Button
):

    def __init__(
        self,
        event_id,
        member,
        disabled=False
    ):

        super().__init__(
            label="REMOVE ATTENDANCE",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            disabled=disabled
        )

        self.event_id = event_id
        self.member = member

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if not can_manage_attendance(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ You don't have permission to manage attendance.",
                ephemeral=True
            )

            return

        success, reason, display_name = remove_attendance(
            self.event_id,
            str(interaction.guild.id),
            str(self.member.id)
        )

        if not success:

            await interaction.response.send_message(
                "ℹ️ This member is not currently marked as attended.",
                ephemeral=True
            )

            return

        # Update the original event embed
        await update_event_message(
            self.event_id            
        )

        # Update the management panel
        await interaction.response.edit_message(
            content=(
                f"👤 **{display_name}**\n"
                f"Status: ⬜ Not Attended"
            ),
            view=ManageMemberView(
                self.event_id,
                self.member,
                attended=False
            )
        )

class BackToManageButton(
    discord.ui.Button
):

    def __init__(self, event_id):

        super().__init__(
            label="BACK",
            emoji="↩️",
            style=discord.ButtonStyle.secondary
        )

        self.event_id = event_id

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        if not can_manage_attendance(
            interaction.user
        ):

            await interaction.response.send_message(
                "❌ You don't have permission to manage attendance.",
                ephemeral=True
            )

            return

        await show_member_selection(
            interaction,
            self.event_id
        )

async def show_member_selection(
    interaction,
    event_id
):

    if not can_manage_attendance(
        interaction.user
    ):

        await interaction.response.send_message(
            "❌ You don't have permission to manage attendance.",
            ephemeral=True
        )

        return

    event = get_event(
        event_id
    )

    if event is None:

        await interaction.response.send_message(
            "❌ Event not found.",
            ephemeral=True
        )

        return

    # Get members from Discord
    members = [
        member
        for member in interaction.guild.members
        if not member.bot
    ]

    if not members:

        await interaction.response.send_message(
            "❌ No members found.",
            ephemeral=True
        )

        return

    view = discord.ui.View(
        timeout=120
    )

    view.add_item(
        MemberSelect(
            event_id,
            members
        )
    )

    await interaction.response.edit_message(
        content=(
            f"🛠️ **Manage Attendance**\n\n"
            f"⚔️ **{event['boss_name']}**\n\n"
            "Select the member you want to manage."
        ),
        view=view
    )

# --------------------------------------------------
# ATTENDANCE VIEW
# --------------------------------------------------

# ATTENDANCE VIEW
class AttendanceView(discord.ui.View):

    def __init__(self, event_id):
        super().__init__(timeout=None)
        self.event_id = event_id

    @discord.ui.button(
        label="I ATTENDED",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="attendance_button"
    )
    async def attendance_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        # Make sure this is being used inside a server
        if interaction.guild is None:
            return

        # Get event
        event = get_event(self.event_id)

        if not event:
            await interaction.response.send_message(
                "❌ Event not found.",
                ephemeral=True
            )
            return

        # Check if event is still open
        if event["status"] != "open":
            await interaction.response.send_message(
                "❌ This attendance event is closed.",
                ephemeral=True
            )
            return

        # Check event time
        if event["end_time"]:
            end_time = datetime.fromisoformat(event["end_time"])

            if datetime.utcnow() >= end_time:
                await interaction.response.send_message(
                    "❌ This attendance event has ended.",
                    ephemeral=True
                )
                return

        # Record attendance
        success, result = mark_attendance(
            self.event_id,
            str(interaction.guild.id),
            str(interaction.user.id),
            event["points_value"]
        )

        if not success:

            if result == "already_attended":
                await interaction.response.send_message(
                    "ℹ️ You have already been marked as attended.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ {result}",
                    ephemeral=True
                )

            return

        # Acknowledge the interaction without sending a message
        await interaction.response.defer()

        # Update the original event message
        await update_event_message(self.event_id)


    @discord.ui.button(
        label="MANAGE ATTENDANCE",
        emoji="🛠️",
        style=discord.ButtonStyle.secondary,
        custom_id="manage_attendance_button"
    )
    async def manage_attendance_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        # Check permissions
        if not can_manage_attendance(interaction.user):
            await interaction.response.send_message(
                "❌ You don't have permission to manage attendance.",
                ephemeral=True
            )
            return

        # Show member selection
        await show_member_selection(
            interaction,
            self.event_id
        )

# --------------------------------------------------
# EVENT COMMAND GROUP
# --------------------------------------------------

event_group = app_commands.Group(
    name="event",
    description="Attendance event commands"
)


@event_group.command(
    name="create",
    description="Create a new attendance event"
)
@app_commands.describe(
    boss="Name of the boss/event",
    duration="Duration in minutes",
    points="Attendance points"
)
@app_commands.default_permissions(
    manage_guild=True
)
async def event_create(
    interaction: discord.Interaction,
    boss: str,
    duration: app_commands.Range[
        int, 1, 1440
    ] = 60,
    points: app_commands.Range[
        int, 1, 100
    ] = 1
):

    if interaction.guild is None:

        await interaction.response.send_message(
            "❌ This command can only be used inside a server.",
            ephemeral=True
        )

        return

    if not interaction.user.guild_permissions.manage_guild:

        await interaction.response.send_message(
            "❌ You need Manage Server permission.",
            ephemeral=True
        )

        return

    await interaction.response.defer()

    guild = interaction.guild

    # Save server
    add_server(
        guild.id,
        guild.name
    )

    # Get current members
    members = [
        member
        for member in guild.members
        if not member.bot
    ]

    # Create event
    event_id = create_event(
        guild_id=guild.id,
        boss_name=boss,
        created_by=interaction.user.id,
        duration_minutes=duration,
        points_value=points,
        channel_id=interaction.channel.id
    )

    # Create attendance records
    create_attendance_records(
        event_id,
        guild.id,
        members
    )

    # Calculate end time
    end_time = (
        datetime.utcnow()
        + timedelta(minutes=duration)
    )

    # Save end time
    import sqlite3

    connection = sqlite3.connect(
        "attendance.db"
    )

    connection.execute(
        """
        UPDATE events
        SET end_time = ?
        WHERE id = ?
        """,
        (
            end_time.isoformat(),
            event_id
        )
    )

    connection.commit()
    connection.close()

    # Create embed
    embed = create_event_embed(
        event_id
    )

    message = await interaction.followup.send(
        embed=embed,
        view=AttendanceView(event_id)
    )

    # Save Discord message ID
    connection = sqlite3.connect(
        "attendance.db"
    )

    connection.execute(
        """
        UPDATE events
        SET discord_message_id = ?
        WHERE id = ?
        """,
        (
            str(message.id),
            event_id
        )
    )

    connection.commit()
    connection.close()



# --------------------------------------------------
# POINTS COMMAND GROUP
# --------------------------------------------------

points_group = app_commands.Group(
    name="points",
    description="Manage attendance points"
)


@points_group.command(
    name="adjust",
    description="Add or subtract points from a member"
)
@app_commands.describe(
    member="Member whose points you want to adjust",
    amount="Points to add or subtract"
)
async def points_adjust(
    interaction: discord.Interaction,
    member: discord.Member,
    amount: int
):

    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ This command can only be used inside a server.",
            ephemeral=True
        )
        return

    # Check permissions
    if not can_manage_attendance(interaction.user):
        await interaction.response.send_message(
            "❌ You don't have permission to manage points.",
            ephemeral=True
        )
        return

    success, reason, display_name, new_total = adjust_points(
        interaction.guild.id,
        member.id,
        amount
    )

    if not success:
        await interaction.response.send_message(
            f"❌ {reason}",
            ephemeral=True
        )
        return

    if amount >= 0:
        change_text = f"+{amount}"
    else:
        change_text = str(amount)

    await interaction.response.send_message(
        f"⭐ **{display_name}** points adjusted by **{change_text}**.\n"
        f"New total: **{new_total:g}**",
        ephemeral=True
    )


@points_group.command(
    name="reset",
    description="Reset a member's points to zero"
)
@app_commands.describe(
    member="Member whose points you want to reset"
)
async def points_reset(
    interaction: discord.Interaction,
    member: discord.Member
):

    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ This command can only be used inside a server.",
            ephemeral=True
        )
        return

    # Check permissions
    if not can_manage_attendance(interaction.user):
        await interaction.response.send_message(
            "❌ You don't have permission to manage points.",
            ephemeral=True
        )
        return

    success, reason, display_name = reset_points(
        interaction.guild.id,
        member.id
    )

    if not success:
        await interaction.response.send_message(
            f"❌ {reason}",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"🔄 Points reset for **{display_name}**.\n"
        f"New total: **0**",
        ephemeral=True
    )


@points_group.command(
    name="reset_all",
    description="Reset all member points to zero"
)
async def points_reset_all(
    interaction: discord.Interaction
):

    if interaction.guild is None:
        await interaction.response.send_message(
            "❌ This command can only be used inside a server.",
            ephemeral=True
        )
        return

    # Check permissions
    if not can_manage_attendance(interaction.user):
        await interaction.response.send_message(
            "❌ You don't have permission to manage points.",
            ephemeral=True
        )
        return

    reset_all_points(
        interaction.guild.id
    )

    await interaction.response.send_message(
        "🔄 **All member points have been reset to 0.**",
        ephemeral=True
    )




# --------------------------------------------------
# PING
# --------------------------------------------------

@bot.tree.command(
    name="ping",
    description="Check if the attendance bot is online."
)
async def ping(
    interaction: discord.Interaction
):

    await interaction.response.send_message(
        "🏓 Pong!"
    )


@bot.tree.command(
    name="leaderboard",
    description="Show the attendance points leaderboard"
)
async def leaderboard(
    interaction: discord.Interaction
):

    if interaction.guild is None:

        await interaction.response.send_message(
            "❌ This command can only be used inside a server.",
            ephemeral=True
        )

        return

    rows = get_leaderboard(
        interaction.guild.id
    )

    if not rows:

        await interaction.response.send_message(
            "❌ No members found.",
            ephemeral=True
        )

        return

    leaderboard_lines = []

    for position, row in enumerate(rows, start=1):

        name = row["display_name"]
        points = row["total_points"]

        leaderboard_lines.append(
            f"{position:>2}. {name:<25} {points:>5}"
        )

    leaderboard_text = "\n".join(
        leaderboard_lines
    )

    embed = discord.Embed(
        title="🏆 ATTENDANCE LEADERBOARD",
        description=(
            "```text\n"
            f"{'Member':<28} {'Points':>5}\n"
            f"{'-' * 34}\n"
            f"{leaderboard_text}\n"
            "```"
        ),
        color=discord.Color.gold()
    )

    embed.add_field(
        name="👥 Members",
        value=str(len(rows)),
        inline=True
    )

    embed.set_footer(
        text="Attendance points leaderboard"
    )

    await interaction.response.send_message(
        embed=embed
    )

# --------------------------------------------------
# BOT READY
# --------------------------------------------------

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")
    print(f"Bot ID: {bot.user.id}")

    try:

        # Add command groups
        if not bot.tree.get_command("event"):
            bot.tree.add_command(
                event_group
            )

        if not bot.tree.get_command("points"):
            bot.tree.add_command(
                points_group
            )

        synced = await bot.tree.sync()

        print(
            f"Synced {len(synced)} slash command(s)."
        )

    except Exception as error:

        print(
            f"Failed to sync commands: {error}"
        )


# --------------------------------------------------
# START
# --------------------------------------------------

initialize_database()

bot.run(TOKEN)