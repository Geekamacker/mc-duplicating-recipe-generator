# 🎮 Minecraft Duplicating Recipe Generator

> A powerful web-based tool for generating custom Minecraft Bedrock duplication recipes.

Create behavior packs with a custom **Duplicating Table** block that lets players duplicate items in their world. Upload entire item catalogs and generate hundreds of recipes in seconds!

## ✨ Features

- 📁 **Bulk Catalog Upload** - Import `crafting_item_catalog.json` files with hundreds of items
- 🎯 **Smart Item Management** - Search, filter, and organize with an intuitive interface
- 📦 **Multiple Export Formats** - Recipes only, Behavior Packs, or Complete Packs
- 💾 **Session Persistence** - Never lose your work between visits
- 🐳 **Docker Ready** - Deploy using the prebuilt GitHub Container Registry image
- 🔄 **Automatic Container Builds** - New images can be published automatically through GitHub Actions

## 🚀 Quick Start

### 🐳 Docker — Recommended

Pull the latest image from GitHub Container Registry:

```bash
docker pull ghcr.io/geekamacker/mc-duplicating-recipe-generator:latest
```

Run the container:

```bash
docker run -d \
  --name minecraft-duplicating-recipe-generator \
  -p 5096:5096 \
  -e PUID=99 \
  -e PGID=100 \
  --restart unless-stopped \
  ghcr.io/geekamacker/mc-duplicating-recipe-generator:latest
```

Then open:

```text
http://localhost:5096
```

in your browser.

### 🐳 Docker Compose

```yaml
services:
  minecraft-duplicating-recipe-generator:
    image: ghcr.io/geekamacker/mc-duplicating-recipe-generator:latest
    container_name: minecraft-duplicating-recipe-generator

    ports:
      - "5096:5096"

    environment:
      - PUID=99
      - PGID=100

    restart: unless-stopped
```

Start the stack:

```bash
docker compose up -d
```

Update to the newest image:

```bash
docker compose pull
docker compose up -d
```

### 🔨 Build from Source

If you prefer to build the Docker image yourself:

```bash
git clone https://github.com/Geekamacker/mc-duplicating-recipe-generator.git
cd mc-duplicating-recipe-generator

docker build -t minecraft-duplicating-recipe-generator .

docker run -d \
  --name minecraft-duplicating-recipe-generator \
  -p 5096:5096 \
  -e PUID=99 \
  -e PGID=100 \
  --restart unless-stopped \
  minecraft-duplicating-recipe-generator
```

### 🐍 Python

Clone the repository:

```bash
git clone https://github.com/Geekamacker/mc-duplicating-recipe-generator.git
cd mc-duplicating-recipe-generator
```

Install the required Python packages:

```bash
pip install -r requirements.txt
```

Start the application:

```bash
python app.py
```

Then open:

```text
http://localhost:5096
```

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

Click **Generate Recipes** and choose your format:

- **📄 Recipes Only** - Just the JSON files
- **📦 Behavior Pack** - Ready-to-use Bedrock pack
- **🎁 Complete Pack** - Behavior + Resource Pack with textures

## 🎮 In-Game Usage

### Craft the Duplicating Table

```text
Iron | Iron  | Iron
Iron | Craft | Iron  →  Duplicating Table
Iron | Iron  | Iron
```

### Duplicate Items

Place any item in the Duplicating Table to get **2× that item**!

## 🏗️ Project Structure

```text
mc-duplicating-recipe-generator/
├── 🐍 app.py                    # Flask application
├── 🌐 index.html                # Web interface
├── 📋 requirements.txt          # Python dependencies
├── 🐳 Dockerfile                # Container image definition
├── 🚀 docker-entrypoint.sh      # Container startup script
├── 📁 data/
│   └── recipe.json.j2           # Recipe template
├── 📁 output/                   # Generated output
├── 🎨 textures/blocks/          # Block textures
└── 🖼️ pack_icon.png             # Pack icon
```

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PUID` | `99` | User ID used for container file permissions |
| `PGID` | `100` | Group ID used for container file permissions |

Example:

```yaml
environment:
  - PUID=99
  - PGID=100
```

### Persistent Storage

You can optionally mount the application's data and output directories:

```yaml
services:
  minecraft-duplicating-recipe-generator:
    image: ghcr.io/geekamacker/mc-duplicating-recipe-generator:latest
    container_name: minecraft-duplicating-recipe-generator

    ports:
      - "5096:5096"

    environment:
      - PUID=99
      - PGID=100

    volumes:
      - ./data:/app/data
      - ./output:/app/output

    restart: unless-stopped
```

For Unraid, absolute paths can be used instead:

```yaml
volumes:
  - /mnt/user/docker/mc-duplicating-recipe-generator/data:/app/data
  - /mnt/user/docker/mc-duplicating-recipe-generator/output:/app/output
```

## 📦 GitHub Container Registry

The Docker image is available from GitHub Container Registry:

```text
ghcr.io/geekamacker/mc-duplicating-recipe-generator:latest
```

Pull the newest release:

```bash
docker pull ghcr.io/geekamacker/mc-duplicating-recipe-generator:latest
```

The `latest` tag is intended to track the newest container build from the repository's main branch.

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

Check container status:

```bash
docker ps
```

Check container logs:

```bash
docker logs minecraft-duplicating-recipe-generator
```

Follow logs continuously:

```bash
docker logs -f minecraft-duplicating-recipe-generator
```

Restart the container:

```bash
docker restart minecraft-duplicating-recipe-generator
```

Pull the newest GHCR image:

```bash
docker pull ghcr.io/geekamacker/mc-duplicating-recipe-generator:latest
```

Rebuild from source without using the Docker build cache:

```bash
docker build --no-cache -t minecraft-duplicating-recipe-generator .
```

</details>

<details>
<summary><strong>🐳 GitHub Container Registry "denied" Error</strong></summary>

If Docker returns an error similar to:

```text
Head "https://ghcr.io/v2/geekamacker/mc-duplicating-recipe-generator/manifests/latest": denied
```

verify that:

1. The GitHub Actions container build completed successfully.
2. The package `mc-duplicating-recipe-generator` exists under GitHub Packages.
3. The GHCR package visibility is set to **Public** if anonymous Docker pulls are desired.
4. The `latest` tag has been published.

Then try again:

```bash
docker pull ghcr.io/geekamacker/mc-duplicating-recipe-generator:latest
```

</details>

## 🤝 Contributing

We welcome contributions!

1. 🍴 Fork the repository
2. 🌿 Create a feature branch:

   ```bash
   git checkout -b feature/amazing-feature
   ```

3. 💾 Commit your changes:

   ```bash
   git commit -m "Add amazing feature"
   ```

4. 📤 Push the branch:

   ```bash
   git push origin feature/amazing-feature
   ```

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

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/Geekamacker/mc-duplicating-recipe-generator/issues)
- 💡 **Feature Requests**: [GitHub Discussions](https://github.com/Geekamacker/mc-duplicating-recipe-generator/discussions)
- 📚 **Documentation**: [GitHub Wiki](https://github.com/Geekamacker/mc-duplicating-recipe-generator/wiki)

---

<div align="center">

**⭐ Star this repo if it helped you!**

Made with ❤️ for the Minecraft community

[Report Bug](https://github.com/Geekamacker/mc-duplicating-recipe-generator/issues) •
[Request Feature](https://github.com/Geekamacker/mc-duplicating-recipe-generator/issues) •
[Contribute](CONTRIBUTING.md)

</div>
