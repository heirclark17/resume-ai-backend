#!/bin/bash
# Link to Railway project and run migration

cd "$(dirname "$0")"

echo "Linking to Railway project..."
# Use expect to automate the interactive prompt
expect << 'EOF'
set timeout 30
spawn railway link

expect "Select a workspace"
send "\r"

expect "Select a project"
send "distinguished-illumination\r"

expect eof
EOF

echo "Getting DATABASE_URL..."
DATABASE_URL=$(railway variables get DATABASE_URL)

if [ -z "$DATABASE_URL" ]; then
    echo "Error: Could not get DATABASE_URL"
    exit 1
fi

echo "Running migration..."
psql "$DATABASE_URL" -f migrations/add_missing_columns.sql

echo "Migration complete!"
