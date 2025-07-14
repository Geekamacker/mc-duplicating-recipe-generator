# 🎮 Minecraft Recipe Generator

> A powerful web-based tool for generating custom Minecraft Bedrock duplication recipes

Create behavior packs with a custom **Duplicating Table** block that lets players duplicate items in their world. Upload entire item catalogs and generate hundreds of recipes in seconds!

## ✨ Features

- 📁 **Bulk Catalog Upload** - Import `crafting_item_catalog.json` files with hundreds of items
- 🎯 **Smart Item Management** - Search, filter, and organize with an intuitive interface  
- 📦 **Multiple Export Formats** - Recipes only, Behavior Packs, or Complete Packs
- 💾 **Session Persistence** - Never lose your work between visits
- 🐳 **Docker Ready** - One-command deployment

## 🚀 Quick Start

**With Docker (Recommended):**
```bash
git clone https://github.com/yourusername/minecraft-recipe-generator.git
cd minecraft-recipe-generator
docker build -t minecraft-recipe-generator .
docker run -d -p 5096:5096 minecraft-recipe-generator
```

**With Python:**
```bash
pip install -r requirements.txt
python app.py
```

Then open **http://localhost:5096** in your browser.

## 📖 How It Works

### 1. Add Items
- **Manual**: Type item names one per line
- **Bulk Upload**: Drop your `crafting_item_catalog.json` file
- **Multi-File**: Upload multiple catalogs at once

### 2. Select & Organize  
- Use checkboxes to choose items
- Search for specific items or categories
- Bulk select/deselect operations

### 3. Generate & Download
- Click "Generate Recipes" 
- Choose your format:
  - **📄 Recipes Only** - Just the JSON files
  - **📦 Behavior Pack** - Ready-to-use Bedrock pack  
  - **🎁 Complete Pack** - Behavior + Resource Pack with textures

## 🎮 In-Game Usage

**Craft the Duplicating Table:**
```
Iron | Iron | Iron
Iron | Craft| Iron  →  Duplicating Table
Iron | Iron | Iron
```

**Duplicate Items:**
Place any item in the Duplicating Table to get 2× that item!

## 🏗️ Project Structure

```
minecraft-recipe-generator/
├── 🐍 app.py                    # Flask application
├── 🌐 index.html                # Web interface  
├── 📋 requirements.txt          # Python deps
├── 🐳 Dockerfile               # Container setup
├── 📁 data/
│   └── recipe.json.j2          # Recipe template
├── 🎨 textures/blocks/         # Block textures
└── 🖼️ pack_icon.png            # Pack icon
```

## ⚙️ Configuration

**Environment Variables:**
- `PUID=1000` - User ID for file permissions
- `PGID=1000` - Group ID for file permissions

**Docker Compose:**
```yaml
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
```

## 🔧 API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main web interface |
| `/upload-catalog` | POST | Upload & parse catalog files |
| `/download-custom` | POST | Generate custom format downloads |
| `/api/last-session` | GET | Retrieve saved session |

## 🛠️ Troubleshooting

<details>
<summary><strong>❌ "No items found in file"</strong></summary>

- Ensure your JSON contains `"items"` arrays
- Check file encoding (must be UTF-8)
- Validate JSON syntax
</details>

<details>
<summary><strong>❌ "Template file not found"</strong></summary>

- Check that `data/recipe.json.j2` exists
- Verify file permissions
- Try restarting the container
</details>

<details>
<summary><strong>🐳 Docker Issues</strong></summary>

```bash
# Check container logs
docker logs [container-name]

# Restart container  
docker restart [container-name]

# Complete rebuild
docker build --no-cache -t minecraft-recipe-generator .
```
</details>

## 🤝 Contributing

We welcome contributions! Here's how:

1. 🍴 Fork the repository
2. 🌿 Create feature branch: `git checkout -b feature/amazing-feature`
3. 💾 Commit changes: `git commit -m 'Add amazing feature'`
4. 📤 Push to branch: `git push origin feature/amazing-feature`  
5. 🔀 Open a Pull Request

## 🗺️ Roadmap

- [ ] Java Edition datapack support
- [ ] Custom recipe ratios (1→3, 1→4, etc.)
- [ ] Mod integration support
- [ ] AI texture generation
- [ ] Recipe sharing marketplace
- [ ] REST API for automation

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

## 💬 Support & Community

- 🐛 **Bug Reports**: [Issues](https://github.com/yourusername/minecraft-recipe-generator/issues)
- 💡 **Feature Requests**: [Discussions](https://github.com/yourusername/minecraft-recipe-generator/discussions)
- 📚 **Documentation**: [Wiki](https://github.com/yourusername/minecraft-recipe-generator/wiki)

---

<div align="center">

**⭐ Star this repo if it helped you!**

Made with ❤️ for the Minecraft community

[Report Bug](https://github.com/yourusername/minecraft-recipe-generator/issues) • [Request Feature](https://github.com/yourusername/minecraft-recipe-generator/issues) • [Contribute](CONTRIBUTING.md)

</div>
