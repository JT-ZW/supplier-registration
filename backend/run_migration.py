"""
Run database migration for admin roles.
"""
import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db.supabase import db


def run_migration():
    """Execute the admin roles migration."""
    
    migration_file = os.path.join(
        os.path.dirname(__file__),
        "app",
        "db",
        "migrations",
        "013_admin_roles.sql"
    )
    
    with open(migration_file, "r") as f:
        sql_commands = f.read()
    
    # Split by semicolon and execute each command
    commands = [cmd.strip() for cmd in sql_commands.split(";") if cmd.strip()]
    
    print(f"Executing {len(commands)} SQL commands...")
    
    for i, command in enumerate(commands, 1):
        try:
            if command.upper().startswith(("CREATE", "ALTER", "UPDATE", "INSERT", "COMMENT")):
                print(f"Executing command {i}/{len(commands)}...")
                # For Supabase, we need to execute via REST API or use their client
                # Since direct SQL execution is limited, we'll print the command
                print(f"Command: {command[:100]}...")
        except Exception as e:
            print(f"Error executing command {i}: {str(e)}")
            print(f"Command was: {command[:200]}...")
    
    print("\nMigration script prepared.")
    print("\nPlease execute the following SQL in your Supabase SQL Editor:")
    print("=" * 80)
    print(sql_commands)
    print("=" * 80)


if __name__ == "__main__":
    run_migration()
