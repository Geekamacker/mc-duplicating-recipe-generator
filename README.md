Minecraft Recipe Generator
A web-based tool for generating custom Minecraft Bedrock duplication recipes. Create behavior packs with a custom "Duplicating Table" block that allows players to duplicate items.

Features
Bulk Catalog Upload: Upload crafting_item_catalog.json files to import hundreds of items at once
Interactive Management: Search, filter, and organize items with a modern web interface
Multiple Export Formats: Generate recipes-only, behavior packs, or complete packs with textures
Session Persistence: Your work is automatically saved between visits
Docker Ready: Easy deployment with containerization
Quick Start
Docker (Recommended)
bash
git clone https://github.com/yourusername/minecraft-recipe-generator.git
cd minecraft-recipe-generator
docker build -t minecraft-recipe-generator .
docker run -d -p 5096:5096 --name mc-recipes minecraft-recipe-generator
Access at: http://localhost:5096

Local Python
bash
git clone https://github.com/yourusername/minecraft-recipe-generator.git
cd minecraft-recipe-generator
pip install -r requirements.txt
python app.py
How to Use
Add Items:
Type item names manually (one per line)
Upload Minecraft catalog files for bulk import
Drag and drop multiple files
Select Items:
Use checkboxes to choose which items to include
Search and filter for specific items
Bulk select/deselect operations
Generate Recipes:
Click "Generate Recipes" to create duplication recipes
Each recipe converts 1 item → 2 items using the Duplicating Table
Download:
Recipes Only: Simple JSON files
Behavior Pack: Complete Bedrock pack with custom block
Complete Pack: Behavior Pack + Resource Pack with textures
In-Game Usage
Craft the Duplicating Table:
[Iron] [Iron] [Iron]
[Iron] [Table] [Iron]  →  [Duplicating Table]
[Iron] [Iron] [Iron]
Duplicate Items:
Place any supported item in the Duplicating Table to get 2 of that item.

Project Structure
minecraft-recipe-generator/
├── app.py                 # Main application
├── index.html             # Web interface
├── requirements.txt       # Dependencies
├── Dockerfile            # Container config
├── data/
│   └── recipe.json.j2    # Recipe template
├── textures/blocks/      # Block textures
└── pack_icon.png         # Pack icon
Configuration
Environment Variables
PUID=1000 - User ID for file permissions
PGID=1000 - Group ID for file permissions
Docker Compose
yaml
version: '3.8'
services:
  minecraft-recipes:
    build: .
    ports:
      - "5096:5096"
    environment:
      - PUID=1000
      - PGID=1000
    restart: unless-stopped
API Endpoints
GET / - Main web interface
POST /upload-catalog - File upload and parsing
POST /download-custom - Custom format downloads
GET /api/last-session - Session data retrieval
Troubleshooting
Common Issues
"No items found in file"

Ensure JSON file contains "items" arrays
Check file encoding (UTF-8)
Verify JSON syntax
"Template file not found"

Ensure data/recipe.json.j2 exists
Check file permissions
Restart container
Docker Issues

bash
# Check logs
docker logs mc-recipes

# Restart
docker restart mc-recipes

# Rebuild
docker build --no-cache -t minecraft-recipe-generator .
Contributing
Fork the repository
Create a feature branch: git checkout -b feature/new-feature
Commit changes: git commit -m 'Add new feature'
Push to branch: git push origin feature/new-feature
Open a Pull Request
Roadmap
 Java Edition datapack support
 Recipe customization options
 Mod integration
 Texture generator
 Web API for automation
License
MIT License - see LICENSE file for details.

Support
Issues: GitHub Issues
Discussions: GitHub Discussions
Made with ❤️ for the Minecraft community

