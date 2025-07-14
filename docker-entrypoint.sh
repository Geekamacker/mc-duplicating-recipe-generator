#!/bin/bash
set -e

# Default values
PUID=${PUID:-99}
PGID=${PGID:-100}

echo "Starting Minecraft Recipe Generator with PUID=$PUID, PGID=$PGID"

# Create group and user if they don't exist
if ! getent group $PGID > /dev/null 2>&1; then
    groupadd -g $PGID appgroup
fi

if ! getent passwd $PUID > /dev/null 2>&1; then
    useradd -u $PUID -g $PGID -d /app -s /bin/bash appuser
fi

# Ensure directories exist
mkdir -p /app/data /app/output /app/textures/blocks

# Fix ownership and permissions
echo "Setting up permissions..."
chown -R $PUID:$PGID /app/data /app/output
chmod -R 755 /app/data /app/output

# Make sure the template file exists
if [ ! -f /app/data/recipe.json.j2 ]; then
    echo "Creating missing template file..."
    cat > /app/data/recipe.json.j2 << 'EOF'
{
  "format_version": "1.12",
  "minecraft:recipe_shaped": {
    "description": {
      "identifier": "duplicating:{{ result_item }}"
    },
    "tags": [
      "duplicating_table"
    ],
    "pattern": [
      "#"
    ],
    "key": {
      "#": {
        "item": "minecraft:{{ result_item }}"
      }
    },
    "result": {
      "item": "minecraft:{{ result_item }}",
      "count": 2
    }
  }
}
EOF
    chown $PUID:$PGID /app/data/recipe.json.j2
fi

echo "Permissions setup complete. Starting application..."

# Drop privileges and run the application
exec gosu $PUID:$PGID "$@"