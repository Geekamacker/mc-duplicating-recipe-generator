from flask import Flask, request, send_file, render_template_string, jsonify
from jinja2 import Template
import os, zipfile, re, logging, json, tempfile, shutil
from datetime import datetime
from werkzeug.utils import secure_filename
import time

app = Flask(__name__)

# Configuration
TEMPLATE_PATH = "data/recipe.json.j2"
MASTER_LIST_PATH = "data/master_list.txt"
LAST_SESSION_PATH = "data/last_session.json"
OUTPUT_DIR = "output"
ZIP_PATH = "data/output.zip"
PACK_ICON_PATH = "pack_icon.png"
TEXTURE_DIR = "textures/blocks"

# Rate limiting - simple in-memory store (use Redis in production)
download_requests = {}
RATE_LIMIT_REQUESTS = 10  # requests per minute
RATE_LIMIT_WINDOW = 60    # seconds

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load HTML template
try:
    with open("index.html") as f:
        HTML_TEMPLATE = f.read()
        logger.info("HTML template loaded successfully")
except FileNotFoundError:
    logger.error("index.html not found, using basic template")
    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html><head><title>Recipe Generator</title></head>
    <body>
    <h1>Recipe Generator</h1>
    <p>Error: index.html template not found</p>
    <div>{{ message|safe }}</div>
    <div>{{ error }}</div>
    </body></html>
    """

def safe_filename(name):
    """Create safe filename from item name"""
    if not name or not isinstance(name, str):
        raise ValueError("Invalid item name")
    
    # Remove dangerous characters and limit length
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name.strip())
    if len(safe_name) > 50:
        safe_name = safe_name[:50]
    
    if not safe_name:
        raise ValueError("Item name results in empty filename")
    
    return safe_name

def validate_item_names(items):
    """Validate a list of item names"""
    if not isinstance(items, list):
        raise ValueError("Items must be a list")
    
    validated_items = []
    for item in items:
        if not isinstance(item, str):
            continue
        
        item = item.strip()
        if not item:
            continue
            
        # Check for reasonable length and characters
        if len(item) > 100:
            raise ValueError(f"Item name too long: {item}")
        
        if not re.match(r'^[a-zA-Z0-9_\-\s]+$', item):
            raise ValueError(f"Invalid characters in item name: {item}")
        
        validated_items.append(item)
    
    return validated_items

def check_rate_limit(client_ip):
    """Simple rate limiting"""
    now = time.time()
    
    # Clean old requests
    cutoff = now - RATE_LIMIT_WINDOW
    download_requests[client_ip] = [req_time for req_time in download_requests.get(client_ip, []) if req_time > cutoff]
    
    # Check if over limit
    if len(download_requests.get(client_ip, [])) >= RATE_LIMIT_REQUESTS:
        return False
    
    # Add current request
    if client_ip not in download_requests:
        download_requests[client_ip] = []
    download_requests[client_ip].append(now)
    
    return True

def load_last_session():
    """Load the user's last session data"""
    try:
        if os.path.exists(LAST_SESSION_PATH):
            with open(LAST_SESSION_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Validate loaded data
            if not isinstance(data, dict):
                raise ValueError("Invalid session data format")
            
            items = validate_item_names(data.get("items", []))
            selected = validate_item_names(data.get("selected", []))
            
            return {
                "items": items,
                "selected": selected,
                "timestamp": data.get("timestamp")
            }
    except (json.JSONDecodeError, IOError, ValueError) as e:
        logger.warning(f"Could not load last session data: {e}")
    
    return {"items": [], "selected": [], "timestamp": None}

def save_session(items, selected_items):
    """Save the current session data"""
    try:
        # Validate inputs
        items = validate_item_names(items)
        selected_items = validate_item_names(selected_items)
        
        session_data = {
            "items": items,
            "selected": selected_items,
            "timestamp": datetime.now().isoformat()
        }
        
        os.makedirs("data", exist_ok=True)
        
        # Write to temporary file first, then rename (atomic operation)
        temp_path = LAST_SESSION_PATH + ".tmp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
        
        os.replace(temp_path, LAST_SESSION_PATH)
        logger.info(f"Session saved: {len(items)} items, {len(selected_items)} selected")
        
    except (IOError, ValueError) as e:
        logger.error(f"Could not save session data: {e}")
        raise

def get_all_items():
    """Get all items from master list"""
    try:
        if os.path.exists(MASTER_LIST_PATH):
            with open(MASTER_LIST_PATH, 'r', encoding='utf-8') as f:
                items = [line.strip() for line in f if line.strip()]
            return validate_item_names(items)
    except (IOError, ValueError) as e:
        logger.warning(f"Could not read master list: {e}")
    
    return []

def cleanup_old_files():
    """Clean up old temporary files"""
    try:
        if os.path.exists(OUTPUT_DIR):
            for f_name in os.listdir(OUTPUT_DIR):
                file_path = os.path.join(OUTPUT_DIR, f_name)
                if os.path.isfile(file_path):
                    # Remove files older than 1 hour
                    if time.time() - os.path.getmtime(file_path) > 3600:
                        os.remove(file_path)
    except Exception as e:
        logger.warning(f"Error cleaning up old files: {e}")

def clean_item_name(item_string):
    """Clean item name by removing minecraft: prefix and other formatting"""
    if not item_string or not isinstance(item_string, str):
        return None
    
    # Remove quotes
    item_string = item_string.strip('"\'')
    
    # Remove minecraft: prefix
    if item_string.startswith('minecraft:'):
        item_string = item_string[10:]  # Remove 'minecraft:' (10 characters)
    
    # Remove any trailing data after : (like damage values)
    if ':' in item_string:
        item_string = item_string.split(':')[0]
    
    # Remove any whitespace
    item_string = item_string.strip()
    
    # Validate item name (only allow valid Minecraft item characters)
    if re.match(r'^[a-z0-9_]+$', item_string):
        return item_string
    
    return None

def parse_json_catalog(content):
    """Parse JSON catalog file and extract item names"""
    try:
        data = json.loads(content)
        items = []
        
        def extract_items_recursive(obj):
            """Recursively extract items from nested JSON structure"""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key == "items" and isinstance(value, list):
                        for item in value:
                            if isinstance(item, str):
                                clean_item = clean_item_name(item)
                                if clean_item:
                                    items.append(clean_item)
                    else:
                        extract_items_recursive(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_items_recursive(item)
        
        extract_items_recursive(data)
        return items
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON format")
        return []

def parse_text_catalog(content):
    """Parse text file and extract item names"""
    items = []
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('//'):
            clean_item = clean_item_name(line)
            if clean_item:
                items.append(clean_item)
    
    return items

def filter_stackable_items(items, show_stats=False):
    """Filter out non-stackable items (stack size = 1) that cannot be duplicated
    Updated for Minecraft Bedrock 1.21.94 - using explicit list only"""
    if not items:
        return [], []
    
    # Exact item names that don't stack (stack size = 1) - EXPLICIT LIST ONLY
    non_stackable_exact = {
        # === TOOLS ===
        # Swords
        'wooden_sword', 'stone_sword', 'iron_sword', 'golden_sword', 
        'diamond_sword', 'netherite_sword',
        
        # Pickaxes
        'wooden_pickaxe', 'stone_pickaxe', 'iron_pickaxe', 'golden_pickaxe',
        'diamond_pickaxe', 'netherite_pickaxe',
        
        # Axes
        'wooden_axe', 'stone_axe', 'iron_axe', 'golden_axe',
        'diamond_axe', 'netherite_axe',
        
        # Shovels
        'wooden_shovel', 'stone_shovel', 'iron_shovel', 'golden_shovel',
        'diamond_shovel', 'netherite_shovel',
        
        # Hoes
        'wooden_hoe', 'stone_hoe', 'iron_hoe', 'golden_hoe',
        'diamond_hoe', 'netherite_hoe',
        
        # Other tools/weapons
        'bow', 'crossbow', 'shield', 'fishing_rod', 'shears',
        'flint_and_steel', 'trident', 'mace',
        'carrot_on_a_stick', 'warped_fungus_on_a_stick',
        
        # === ARMOR ===
        # Helmets
        'leather_helmet', 'chainmail_helmet', 'iron_helmet', 'golden_helmet',
        'diamond_helmet', 'netherite_helmet', 'turtle_helmet',
        
        # Chestplates
        'leather_chestplate', 'chainmail_chestplate', 'iron_chestplate', 
        'golden_chestplate', 'diamond_chestplate', 'netherite_chestplate',
        
        # Leggings
        'leather_leggings', 'chainmail_leggings', 'iron_leggings',
        'golden_leggings', 'diamond_leggings', 'netherite_leggings',
        
        # Boots
        'leather_boots', 'chainmail_boots', 'iron_boots', 'golden_boots',
        'diamond_boots', 'netherite_boots',
        
        # Horse armor
        'leather_horse_armor', 'iron_horse_armor', 'golden_horse_armor',
        'diamond_horse_armor',
        
        # Other armor
        'elytra', 'wolf_armor',
        
        # === HARNESSES (Wolf Armor variants) ===
        'black_harness', 'white_harness', 'orange_harness', 'magenta_harness',
        'light_blue_harness', 'yellow_harness', 'lime_harness', 'pink_harness',
        'gray_harness', 'light_gray_harness', 'cyan_harness', 'purple_harness',
        'blue_harness', 'brown_harness', 'green_harness', 'red_harness',
        
        # === BUNDLES ===
        'bundle',  # Base bundle
        'black_bundle', 'white_bundle', 'orange_bundle', 'magenta_bundle',
        'light_blue_bundle', 'yellow_bundle', 'lime_bundle', 'pink_bundle', 
        'gray_bundle', 'light_gray_bundle', 'cyan_bundle', 'purple_bundle',
        'blue_bundle', 'brown_bundle', 'green_bundle', 'red_bundle',
        
        # === BANNER PATTERNS ===
        'flower_banner_pattern', 'creeper_banner_pattern', 'skull_banner_pattern',
        'mojang_banner_pattern', 'globe_banner_pattern', 'piglin_banner_pattern',
        'flow_banner_pattern', 'guster_banner_pattern', 'field_masoned_banner_pattern',
        'bordure_indented_banner_pattern',
        
        # === BUCKETS ===
        # NOTE: empty 'bucket' removed - it stacks to 16!
        'water_bucket', 'lava_bucket', 'milk_bucket',
        'powder_snow_bucket', 'cod_bucket', 'salmon_bucket',
        'pufferfish_bucket', 'tropical_fish_bucket', 
        'axolotl_bucket', 'tadpole_bucket',
        
        # === STEWS/SOUPS ===
        'mushroom_stew', 'rabbit_stew', 'beetroot_soup', 'suspicious_stew',
        
        # === POTIONS ===
        'potion', 'splash_potion', 'lingering_potion',
        # Note: Would need to add specific potion types if they have unique IDs
        
        # === MUSIC DISCS ===
        'music_disc_13', 'music_disc_cat', 'music_disc_blocks', 'music_disc_chirp',
        'music_disc_far', 'music_disc_mall', 'music_disc_mellohi', 'music_disc_stal',
        'music_disc_strad', 'music_disc_ward', 'music_disc_11', 'music_disc_wait',
        'music_disc_otherside', 'music_disc_5', 'music_disc_pigstep', 'music_disc_relic',
        'music_disc_creator', 'music_disc_creator_music_box', 'music_disc_precipice',
        'music_disc_tears', 'music_disc_lava_chicken',
        
        # === BOATS ===
        'boat', 'oak_boat', 'spruce_boat', 'birch_boat', 'jungle_boat',
        'acacia_boat', 'dark_oak_boat', 'mangrove_boat', 'cherry_boat',
        'bamboo_raft', 'pale_oak_boat',
        'chest_boat', 'oak_chest_boat', 'spruce_chest_boat', 'birch_chest_boat',
        'jungle_chest_boat', 'acacia_chest_boat', 'dark_oak_chest_boat',
        'mangrove_chest_boat', 'cherry_chest_boat', 'bamboo_chest_raft',
        'pale_oak_chest_boat',
        
        # === MINECARTS ===
        'minecart', 'chest_minecart', 'hopper_minecart', 'tnt_minecart',
        'furnace_minecart', 'command_block_minecart',
        
        # === BEDS ===
        'bed', 'white_bed', 'orange_bed', 'magenta_bed', 'light_blue_bed',
        'yellow_bed', 'lime_bed', 'pink_bed', 'gray_bed', 'light_gray_bed',
        'cyan_bed', 'purple_bed', 'blue_bed', 'brown_bed', 'green_bed',
        'red_bed', 'black_bed',
        
        # === SHULKER BOXES ===
        'shulker_box', 'undyed_shulker_box', 'white_shulker_box', 'orange_shulker_box', 
        'magenta_shulker_box', 'light_blue_shulker_box', 'yellow_shulker_box', 
        'lime_shulker_box', 'pink_shulker_box', 'gray_shulker_box', 
        'light_gray_shulker_box', 'cyan_shulker_box', 'purple_shulker_box', 
        'blue_shulker_box', 'brown_shulker_box', 'green_shulker_box', 
        'red_shulker_box', 'black_shulker_box',
        
        # === BOOKS WITH NBT ===
        'written_book', 'writable_book', 'book_and_quill', 'enchanted_book',
        
        # === SPECIAL ITEMS ===
        'totem_of_undying', 'saddle', 'filled_map', 'cake',
        'spyglass', 'brush', 'goat_horn',
        
        # === EDUCATION EDITION ===
        'sparkler', 'glow_stick', 'medicine',
    }
    
    # Items often mistaken as non-stackable but actually DO stack:
    # - spawn_egg variants (stack to 64)
    # - armor_stand (stacks to 16)
    # - compass (stacks to 64)
    # - clock (stacks to 64)
    # - map/empty_map (stacks to 64)
    # - tipped_arrow (stacks to 64)
    # - banner (stacks to 16)
    # - sign (stacks to 16)
    # - bowl (stacks to 64)
    # - bottle (stacks to 64)
    # - bucket (empty bucket stacks to 16)
    # - pumpkin_pie (stacks to 64)
    # - name_tag (stacks to 64)
    # - lead (stacks to 64)
    
    stackable_items = []
    filtered_items = []
    
    for item in items:
        if not item or not isinstance(item, str):
            continue
            
        item_lower = item.lower()
        
        # Simple check - is it in our explicit list?
        if item_lower in non_stackable_exact:
            filtered_items.append(item)
        else:
            stackable_items.append(item)
    
    if show_stats:
        logger.info(f"Filtered items: {len(stackable_items)} stackable, {len(filtered_items)} non-stackable")
        if filtered_items and len(filtered_items) <= 20:
            logger.info(f"Filtered out: {', '.join(filtered_items[:20])}")
    
    return stackable_items, filtered_items

@app.route("/upload-catalog", methods=["POST"])
def upload_catalog():
    """Handle multiple catalog file uploads and extract item names"""
    try:
        # Handle both single file and multiple files
        files = request.files.getlist('catalog_file')
        
        if not files or (len(files) == 1 and files[0].filename == ''):
            return jsonify({"success": False, "error": "No files uploaded"})
        
        all_extracted_items = []
        processed_files = []
        failed_files = []
        
        for file in files:
            if file.filename == '':
                continue
                
            try:
                # Read file content
                file_content = file.read().decode('utf-8')
                
                # Parse and extract items based on file type
                file_items = []
                
                if file.filename.lower().endswith('.json'):
                    file_items = parse_json_catalog(file_content)
                elif file.filename.lower().endswith('.txt'):
                    file_items = parse_text_catalog(file_content)
                else:
                    failed_files.append(f"{file.filename} (unsupported format)")
                    continue
                
                if file_items:
                    all_extracted_items.extend(file_items)
                    processed_files.append(f"{file.filename} ({len(file_items)} items)")
                    logger.info(f"Successfully extracted {len(file_items)} items from {file.filename}")
                else:
                    failed_files.append(f"{file.filename} (no valid items found)")
                    
            except Exception as e:
                logger.error(f"Error processing file {file.filename}: {e}")
                failed_files.append(f"{file.filename} (processing error)")
                continue
        
        if not all_extracted_items:
            return jsonify({"success": False, "error": "No valid items found in any of the uploaded files"})
        
        # Remove duplicates and sort
        unique_items = sorted(list(set(all_extracted_items)))
        
        # Filter out non-stackable items
        stackable_items, filtered_items = filter_stackable_items(unique_items, show_stats=True)
        
        # Build success message
        message_parts = []
        if processed_files:
            message_parts.append(f"Successfully processed {len(processed_files)} file(s)")
            message_parts.append(f"Found {len(unique_items)} unique items")
            if filtered_items:
                message_parts.append(f"Filtered out {len(filtered_items)} non-stackable items")
            message_parts.append(f"Ready to use: {len(stackable_items)} stackable items")
        
        message = ". ".join(message_parts)
        
        response_data = {
            "success": True, 
            "items": stackable_items,
            "count": len(stackable_items),
            "total_items": len(all_extracted_items),
            "unique_items": len(unique_items),
            "filtered_items": len(filtered_items),
            "processed_files": processed_files,
            "failed_files": failed_files,
            "message": message
        }
        
        if failed_files:
            response_data["warning"] = f"Some files could not be processed: {', '.join(failed_files)}"
        
        if filtered_items:
            response_data["filter_info"] = f"Filtered out {len(filtered_items)} non-stackable items (tools, armor, vehicles, etc.)"
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error processing catalog uploads: {e}")
        return jsonify({"success": False, "error": "Failed to process the uploaded files"})

@app.route("/", methods=["GET", "POST"])
def index():
    message = ""
    error = ""
    
    # Load last session for display
    last_session = load_last_session()
    
    if request.method == "POST":
        try:
            action = request.form.get("action", "generate")
            
            if action == "load_last":
                if last_session["items"]:
                    items_text = "\n".join(last_session["items"])
                    selected_items = last_session["selected"]
                    
                    js_script = f"""
                    <script>
                    document.addEventListener('DOMContentLoaded', function() {{
                        document.getElementById('textarea').value = {json.dumps(items_text)};
                        document.getElementById('convertBtn').click();
                        
                        setTimeout(function() {{
                            const selectedItems = {json.dumps(selected_items)};
                            document.querySelectorAll('#checklist input[type="checkbox"]').forEach(cb => {{
                                cb.checked = selectedItems.includes(cb.value);
                            }});
                            updatePreview();
                        }}, 100);
                    }});
                    </script>
                    """
                    
                    timestamp = datetime.fromisoformat(last_session["timestamp"]).strftime("%Y-%m-%d %H:%M:%S") if last_session["timestamp"] else "Unknown"
                    message = f"Last session loaded (from {timestamp}). {js_script}"
                else:
                    message = "No previous session found."
                    
                return render_template_string(HTML_TEMPLATE, message=message, error=error)
            
            # Handle normal form submission - Generate recipes
            submitted_items = request.form.getlist("selected")
            all_items_raw = request.form.get("all_items", "")
            
            if not submitted_items:
                error = "No items selected. Please select at least one item."
                return render_template_string(HTML_TEMPLATE, message=message, error=error)
            
            # Validate inputs
            submitted_items = validate_item_names(submitted_items)
            all_items = validate_item_names(all_items_raw.split("\n") if all_items_raw else [])
            
            # Filter out non-stackable items from submitted items
            stackable_submitted, filtered_submitted = filter_stackable_items(submitted_items, show_stats=True)
            
            if not stackable_submitted:
                if filtered_submitted:
                    error = f"All {len(filtered_submitted)} selected items are non-stackable (tools, armor, vehicles, etc.) and cannot be duplicated. Please select stackable items instead."
                else:
                    error = "No stackable items selected. Please select items that can be duplicated."
                return render_template_string(HTML_TEMPLATE, message=message, error=error)
            
            logger.info(f"Form submission: {len(stackable_submitted)} stackable items selected ({len(filtered_submitted)} non-stackable filtered out), {len(all_items)} total items")
            
            # Clean up old files
            cleanup_old_files()
            
            # Ensure directories exist
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            os.makedirs("data", exist_ok=True)

            if not os.path.exists(TEMPLATE_PATH):
                error = f"Template file '{TEMPLATE_PATH}' not found."
                logger.error(error)
                return render_template_string(HTML_TEMPLATE, message=message, error=error)

            with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
                template = Template(f.read())

            # Clear output directory
            for f_name in os.listdir(OUTPUT_DIR):
                file_path = os.path.join(OUTPUT_DIR, f_name)
                if os.path.isfile(file_path):
                    os.remove(file_path)

            # Update master list safely
            try:
                master_items = set()
                if os.path.exists(MASTER_LIST_PATH):
                    with open(MASTER_LIST_PATH, 'r', encoding='utf-8') as f:
                        master_items = set(line.strip().lower() for line in f if line.strip())

                new_items = [item for item in stackable_submitted if item.lower() not in master_items]
                if new_items:
                    with open(MASTER_LIST_PATH, "a", encoding='utf-8') as f:
                        for item in new_items:
                            f.write(item + "\n")
            except Exception as e:
                logger.warning(f"Could not update master list: {e}")

            # Generate recipe files
            generated_files = []
            for item in stackable_submitted:
                try:
                    safe_name = safe_filename(item)
                    rendered = template.render(result_item=item)
                    filename = f"{safe_name}_19.json"
                    file_path = os.path.join(OUTPUT_DIR, filename)
                    
                    with open(file_path, "w", encoding='utf-8') as f_out:
                        f_out.write(rendered)
                    
                    generated_files.append(filename)
                    logger.info(f"Generated: {filename}")
                    
                except Exception as e:
                    logger.error(f"Error generating recipe for {item}: {e}")
                    continue

            # Always add the duplicating table crafting recipe
            try:
                table_recipe_content = """{
    "format_version": "1.12",
    "minecraft:recipe_shaped": {
        "description": {
            "identifier": "duplicatingtable:duplicating_table"
        },
        "tags": [
            "crafting_table"
        ],
        "pattern": [
            "iii",
            "iCi",
            "iii"
        ],
        "key": {
            "i": {
                "item": "minecraft:iron_ingot"
            },
            "C": {
                "item": "minecraft:crafting_table"
            }
        },
        "result": {
            "item": "duplicatingtable:duplicating_table",
            "count": 1
        }
    }
}"""
                
                table_recipe_filename = "duplicating_table.json"
                table_recipe_path = os.path.join(OUTPUT_DIR, table_recipe_filename)
                
                with open(table_recipe_path, "w", encoding='utf-8') as f_out:
                    f_out.write(table_recipe_content)
                
                generated_files.append(table_recipe_filename)
                logger.info("Added duplicating table crafting recipe to output")
                
            except Exception as e:
                logger.error(f"Error adding table recipe: {e}")

            if not generated_files:
                error = "No recipe files were generated successfully."
                return render_template_string(HTML_TEMPLATE, message=message, error=error)

            # Create ZIP file safely
            temp_zip = ZIP_PATH + ".tmp"
            try:
                with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
                    for filename in generated_files:
                        file_path = os.path.join(OUTPUT_DIR, filename)
                        if os.path.exists(file_path):
                            zipf.write(file_path, arcname=filename)
                            logger.info(f"Added to ZIP: {filename}")
                
                # Atomic rename
                if os.path.exists(ZIP_PATH):
                    os.remove(ZIP_PATH)
                os.rename(temp_zip, ZIP_PATH)
                
            except Exception as e:
                logger.error(f"Error creating ZIP file: {e}")
                if os.path.exists(temp_zip):
                    os.remove(temp_zip)
                error = "Failed to create download package."
                return render_template_string(HTML_TEMPLATE, message=message, error=error)

            if not os.path.exists(ZIP_PATH) or os.path.getsize(ZIP_PATH) == 0:
                error = "ZIP file creation failed or is empty."
                logger.error(error)
                return render_template_string(HTML_TEMPLATE, message=message, error=error)

            # Save current session
            try:
                save_session(all_items, stackable_submitted)
            except Exception as e:
                logger.warning(f"Could not save session: {e}")

            zip_size = os.path.getsize(ZIP_PATH)
            filter_message = f" ({len(filtered_submitted)} non-stackable items filtered out)" if filtered_submitted else ""
            message = f"✅ Successfully generated {len(stackable_submitted)} recipe file(s) ({zip_size:,} bytes){filter_message}. <a href='/download' style='color: #90ee90; text-decoration: underline;'>Download ZIP</a>"
            logger.info(f"ZIP created successfully: {zip_size} bytes")

        except ValueError as e:
            error = f"Invalid input: {str(e)}"
            logger.error(f"Validation error: {e}")
        except Exception as e:
            error = f"An unexpected error occurred. Please try again."
            logger.error(f"Error in recipe generation: {e}", exc_info=True)

    return render_template_string(HTML_TEMPLATE, message=message, error=error)

@app.route("/download-custom", methods=["POST"])
def download_custom():
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
    
    # Rate limiting
    if not check_rate_limit(client_ip):
        logger.warning(f"Rate limit exceeded for {client_ip}")
        return "Too many requests. Please wait before downloading again.", 429
    
    try:
        format_type = request.form.get('format', 'standard')
        items_json = request.form.get('items', '[]')
        
        # Validate format type
        valid_formats = ['standard', 'datapack', 'behavior_pack', 'complete_pack', 'custom']
        if format_type not in valid_formats:
            return "Invalid format type", 400
        
        try:
            selected_items = json.loads(items_json)
            selected_items = validate_item_names(selected_items)
            
            # Filter out non-stackable items
            stackable_items, filtered_items = filter_stackable_items(selected_items, show_stats=True)
            selected_items = stackable_items  # Use only stackable items
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid items JSON: {e}")
            return "Invalid items data", 400
        
        logger.info(f"Custom download requested: format={format_type}, items={len(selected_items)} stackable ({len(filtered_items) if 'filtered_items' in locals() else 0} filtered out)")
        
        # Add progress logging for large batches
        if len(selected_items) > 500:
            logger.info(f"Processing large batch of {len(selected_items)} items - this may take a moment...")
        
        if not selected_items:
            return "No items selected", 400
            
        if len(selected_items) > 5000:  # Increased from 1000 to 5000
            return "Too many items selected. Please select fewer than 5000 items for performance reasons.", 400
            
        # Ensure directories exist
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.makedirs("data", exist_ok=True)
        
        if not os.path.exists(TEMPLATE_PATH):
            logger.error("Template file not found")
            return f"Template file '{TEMPLATE_PATH}' not found.", 404
            
        with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            template = Template(f.read())
        
        # Clean up old files
        cleanup_old_files()
        
        # Create custom structure based on format  
        # Use temp directory for better isolation
        import tempfile
        temp_dir = tempfile.gettempdir()
        custom_zip_path = os.path.join(temp_dir, f"custom_{format_type}_{int(time.time())}.zip")
        
        try:
            with zipfile.ZipFile(custom_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                # Generate recipe files
                successful_recipes = 0
                failed_recipes = 0
                
                for i, item in enumerate(selected_items):
                    try:
                        safe_name = safe_filename(item)
                        rendered = template.render(result_item=item)
                        filename = f"{safe_name}_19.json"
                        
                        # Determine file path based on format
                        if format_type == 'datapack':
                            arcname = f"data/duplicating/recipes/{filename}"
                        elif format_type == 'behavior_pack':
                            arcname = f"Duplicating Table BP/recipes/{filename}"
                        elif format_type == 'complete_pack':
                            arcname = f"Duplicating Table BP/recipes/{filename}"
                        elif format_type == 'custom':
                            category = get_item_category(item)
                            arcname = f"{category}/{filename}"
                        else:
                            arcname = filename
                        
                        zipf.writestr(arcname, rendered)
                        successful_recipes += 1
                        
                        # Log progress for large batches
                        if len(selected_items) > 500 and (i + 1) % 100 == 0:
                            logger.info(f"Progress: {i + 1}/{len(selected_items)} recipes generated")
                        
                    except Exception as e:
                        logger.error(f"Error processing item {item}: {e}")
                        failed_recipes += 1
                        continue
                
                logger.info(f"Recipe generation complete: {successful_recipes} successful, {failed_recipes} failed")
                
                # ALWAYS add the duplicating table crafting recipe for behavior packs and complete packs
                if format_type in ['behavior_pack', 'complete_pack']:
                    try:
                        table_recipe_content = """{
    "format_version": "1.12",
    "minecraft:recipe_shaped": {
        "description": {
            "identifier": "duplicatingtable:duplicating_table"
        },
        "tags": [
            "crafting_table"
        ],
        "pattern": [
            "iii",
            "iCi",
            "iii"
        ],
        "key": {
            "i": {
                "item": "minecraft:iron_ingot"
            },
            "C": {
                "item": "minecraft:crafting_table"
            }
        },
        "result": {
            "item": "duplicatingtable:duplicating_table",
            "count": 1
        }
    }
}"""
                        
                        if format_type == 'behavior_pack':
                            table_recipe_arcname = "Duplicating Table BP/recipes/duplicating_table.json"
                        elif format_type == 'complete_pack':
                            table_recipe_arcname = "Duplicating Table BP/recipes/duplicating_table.json"
                        
                        zipf.writestr(table_recipe_arcname, table_recipe_content)
                        successful_recipes += 1
                        logger.info("Added duplicating table crafting recipe to pack")
                        
                    except Exception as e:
                        logger.error(f"Error adding table recipe to pack: {e}")
                        failed_recipes += 1
                        
                # Add metadata files based on format
                try:
                    if format_type == 'datapack':
                        add_datapack_metadata(zipf)
                    elif format_type == 'behavior_pack':
                        add_behavior_pack_metadata(zipf)
                    elif format_type == 'complete_pack':
                        add_complete_pack_metadata(zipf)
                    elif format_type == 'custom':
                        add_custom_metadata(zipf, selected_items)
                except Exception as e:
                    logger.error(f"Error adding metadata: {e}")
        
        except Exception as e:
            logger.error(f"Error creating custom ZIP: {e}")
            if os.path.exists(custom_zip_path):
                os.remove(custom_zip_path)
            return "Error creating download package", 500
        
        if not os.path.exists(custom_zip_path) or os.path.getsize(custom_zip_path) == 0:
            logger.error("Custom ZIP creation failed or empty")
            return "Download package creation failed", 500
        
        zip_size = os.path.getsize(custom_zip_path)
        logger.info(f"Custom ZIP created: {custom_zip_path} ({zip_size:,} bytes)")
        
        # Clean up file after sending
        def remove_file():
            try:
                if os.path.exists(custom_zip_path):
                    os.remove(custom_zip_path)
            except:
                pass
        
        # Schedule cleanup (simple approach - use Celery in production)
        import threading
        cleanup_timer = threading.Timer(300, remove_file)  # Clean up after 5 minutes
        cleanup_timer.start()
        
        return send_file(custom_zip_path, as_attachment=True, 
                        download_name=f"minecraft_recipes_{format_type}.zip", 
                        mimetype='application/zip')
                        
    except Exception as e:
        logger.error(f"Error in custom download: {e}", exc_info=True)
        return "Internal server error", 500

def get_item_category(item):
    """Categorize items for custom folder structure"""
    if not item:
        return 'misc'
    
    item_lower = item.lower()
    
    if any(word in item_lower for word in ['ore', 'raw_']):
        return 'ores'
    elif any(word in item_lower for word in ['ingot', 'nugget']):
        return 'metals'
    elif any(word in item_lower for word in ['wood', 'log', 'plank']):
        return 'wood'
    elif any(word in item_lower for word in ['stone', 'cobble', 'granite', 'diorite']):
        return 'stone'
    elif any(word in item_lower for word in ['diamond', 'emerald', 'ruby', 'sapphire']):
        return 'gems'
    elif any(word in item_lower for word in ['food', 'bread', 'meat', 'apple']):
        return 'food'
    else:
        return 'misc'

def add_datapack_metadata(zipf):
    """Add pack.mcmeta for Java datapack"""
    logger.info("Adding datapack metadata...")
    pack_mcmeta = {
        "pack": {
            "pack_format": 10,
            "description": "Duplication Recipes Datapack"
        }
    }
    zipf.writestr("pack.mcmeta", json.dumps(pack_mcmeta, indent=2))

def add_behavior_pack_metadata(zipf):
    """Add manifest.json and pack structure for Bedrock behavior pack"""
    logger.info("Adding behavior pack metadata...")
    
    manifest = {
        "format_version": 2,
        "metadata": {
            "authors": ["foamwrap"]
        },
        "header": {
            "name": "Duplicating Table",
            "description": "By foamwrap",
            "min_engine_version": [1, 20, 60],
            "uuid": "3c96e59a-8381-4ead-9e5a-4ce147c137fb",
            "version": [3, 0, 1]
        },
        "modules": [
            {
                "type": "data",
                "uuid": "6a1e005c-2b3f-4b68-b9f0-cea14fea6205",
                "version": [3, 0, 1]
            }
        ],
        "dependencies": [
            {
                "uuid": "00f04670-f5ca-4fe3-8d07-67526b3e343b",
                "version": [3, 0, 1]
            }
        ]
    }
    zipf.writestr("Duplicating Table BP/manifest.json", json.dumps(manifest, indent=2))
    
    # Add block definition
    duplicating_table_block = {
        "format_version": "1.20.60",
        "minecraft:block": {
            "description": {
                "identifier": "duplicatingtable:duplicating_table",
                "menu_category": {"category": "equipment"},
                "is_experimental": False,
                "traits": {
                    "minecraft:placement_direction": {
                        "enabled_states": ["minecraft:cardinal_direction"]
                    }
                }
            },
            "components": {
                "minecraft:crafting_table": {
                    "crafting_tags": ["duplicating_table"],
                    "grid_size": 3,
                    "table_name": "Duplicating"
                },
                "minecraft:collision_box": {
                    "size": [16, 16, 16],
                    "origin": [-8, 0, -8]
                },
                "minecraft:geometry": "geometry.duplicating_table",
                "minecraft:material_instances": {
                    "up": {"texture": "dt_top", "render_method": "opaque"},
                    "*": {"texture": "dt_side", "render_method": "opaque"},
                    "north": {"texture": "dt_front", "render_method": "opaque"}
                },
                "minecraft:flammable": True,
                "minecraft:destructible_by_mining": {"seconds_to_destroy": 1},
                "minecraft:destructible_by_explosion": {"explosion_resistance": 7.5},
                "minecraft:selection_box": {"origin": [-8, 0, -8], "size": [16, 16, 16]}
            },
            "permutations": [
                {
                    "condition": "query.block_state('minecraft:cardinal_direction')=='south'",
                    "components": {"minecraft:transformation": {"rotation": [0, 0, 0]}}
                },
                {
                    "condition": "query.block_state('minecraft:cardinal_direction')=='east'",
                    "components": {"minecraft:transformation": {"rotation": [0, 90, 0]}}
                },
                {
                    "condition": "query.block_state('minecraft:cardinal_direction')=='west'",
                    "components": {"minecraft:transformation": {"rotation": [0, -90, 0]}}
                },
                {
                    "condition": "query.block_state('minecraft:cardinal_direction')=='north'",
                    "components": {"minecraft:transformation": {"rotation": [0, 180, 0]}}
                }
            ]
        }
    }
    zipf.writestr("Duplicating Table BP/blocks/duplicating_table.json", 
                  json.dumps(duplicating_table_block, separators=(',', ':')))
    
    # Copy pack icon
    try:
        if os.path.exists(PACK_ICON_PATH):
            with open(PACK_ICON_PATH, 'rb') as icon_file:
                pack_icon_content = icon_file.read()
            zipf.writestr("Duplicating Table BP/pack_icon.png", pack_icon_content)
            logger.info(f"Added pack icon from {PACK_ICON_PATH} (size: {len(pack_icon_content)} bytes)")
        else:
            logger.warning(f"Pack icon not found at {PACK_ICON_PATH}")
    except Exception as e:
        logger.error(f"Error adding pack icon: {e}")
    
    logger.info("Behavior pack metadata complete")

def add_complete_pack_metadata(zipf):
    """Add both Behavior Pack and Resource Pack metadata and files"""
    logger.info("Adding complete pack metadata (BP + RP)...")
    
    try:
        # First add the Behavior Pack components
        add_behavior_pack_metadata(zipf)
        logger.info("Behavior Pack metadata added successfully")
    except Exception as e:
        logger.error(f"Error adding behavior pack metadata: {e}")
        raise
    
    try:
        # RP Manifest
        rp_manifest = {
            "format_version": 2,
            "metadata": {"authors": ["foamwrap"]},
            "header": {
                "name": "Duplicating Table",
                "description": "By foamwrap",
                "min_engine_version": [1, 20, 60],
                "uuid": "00f04670-f5ca-4fe3-8d07-67526b3e343b",
                "version": [3, 0, 1]
            },
            "modules": [
                {
                    "type": "resources",
                    "uuid": "a39fb2ce-c028-44df-8749-09e4e71d9c48",
                    "version": [3, 0, 1]
                }
            ],
            "dependencies": [
                {
                    "uuid": "3c96e59a-8381-4ead-9e5a-4ce147c137fb",
                    "version": [3, 0, 1]
                }
            ]
        }
        zipf.writestr("Duplicating Table RP/manifest.json", json.dumps(rp_manifest, indent=2))
        logger.info("RP manifest added successfully")
    except Exception as e:
        logger.error(f"Error adding RP manifest: {e}")
        raise
    
    try:
        # RP blocks.json
        rp_blocks = {
            "format_version": [1, 1, 0],
            "duplicatingtable:duplicatingtable": {
                "sound": "wood",
                "textures": {"up": "dt_top", "side": "dt_side"}
            }
        }
        zipf.writestr("Duplicating Table RP/blocks.json", json.dumps(rp_blocks, separators=(',', ':')))
        logger.info("RP blocks.json added successfully")
    except Exception as e:
        logger.error(f"Error adding RP blocks.json: {e}")
        raise
    
    try:
        # Language files
        zipf.writestr("Duplicating Table RP/texts/languages.json", '[\n\t"en_US"\n]')
        zipf.writestr("Duplicating Table RP/texts/en_US.lang", 
                      "tile.duplicatingtable:duplicating_table.name=Duplicating Table")
        logger.info("Language files added successfully")
    except Exception as e:
        logger.error(f"Error adding language files: {e}")
        raise
    
    try:
        # Terrain texture
        terrain_texture = {
            "num_mip_levels": 4,
            "padding": 8,
            "resource_pack_name": "Duplicating Table",
            "texture_name": "atlasd.terrain",
            "texture_data": {
                "dt_side": {"textures": "textures/blocks/duplicating_table_side"},
                "dt_top": {"textures": "textures/blocks/duplicating_table_top"},
                "dt_front": {"textures": "textures/blocks/duplicating_table_front"}
            }
        }
        zipf.writestr("Duplicating Table RP/textures/terrain_texture.json", 
                      json.dumps(terrain_texture, separators=(',', ':')))
        logger.info("Terrain texture added successfully")
    except Exception as e:
        logger.error(f"Error adding terrain texture: {e}")
        raise
    
    try:
        # Geometry
        geometry = {
            "format_version": "1.12.0",
            "minecraft:geometry": [
                {
                    "description": {
                        "identifier": "geometry.duplicating_table",
                        "texture_width": 16,
                        "texture_height": 16,
                        "visible_bounds_width": 2,
                        "visible_bounds_height": 2.5,
                        "visible_bounds_offset": [0, 0.75, 0]
                    },
                    "bones": [
                        {
                            "name": "root",
                            "pivot": [0, 0, 0],
                            "cubes": [
                                {
                                    "origin": [-8, 0, -8],
                                    "size": [16, 16, 16],
                                    "uv": {
                                        "north": {"uv": [0, 0], "uv_size": [16, 16], "material_instance": "north"},
                                        "east": {"uv": [0, 0], "uv_size": [16, 16], "material_instance": "east"},
                                        "south": {"uv": [0, 0], "uv_size": [16, 16], "material_instance": "south"},
                                        "west": {"uv": [0, 0], "uv_size": [16, 16], "material_instance": "west"},
                                        "up": {"uv": [16, 16], "uv_size": [-16, -16], "material_instance": "up"},
                                        "down": {"uv": [16, 16], "uv_size": [-16, -16], "material_instance": "down"}
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        zipf.writestr("Duplicating Table RP/models/blocks/duplicating_table.geo.json", 
                      json.dumps(geometry, separators=(',', ':')))
        logger.info("Geometry added successfully")
    except Exception as e:
        logger.error(f"Error adding geometry: {e}")
        raise
    
    try:
        # Copy pack icon to RP as well
        if os.path.exists(PACK_ICON_PATH):
            with open(PACK_ICON_PATH, 'rb') as icon_file:
                pack_icon_content = icon_file.read()
            zipf.writestr("Duplicating Table RP/pack_icon.png", pack_icon_content)
            logger.info("Added pack icon to Resource Pack")
        else:
            logger.warning(f"Pack icon not found at {PACK_ICON_PATH}")
    except Exception as e:
        logger.error(f"Error adding RP pack icon: {e}")
        # Don't raise, continue without icon
    
    # Add real texture files with detailed logging
    texture_files = [
        ('textures/blocks/duplicating_table_front.png', 'Duplicating Table RP/textures/blocks/duplicating_table_front.png'),
        ('textures/blocks/duplicating_table_side.png', 'Duplicating Table RP/textures/blocks/duplicating_table_side.png'),
        ('textures/blocks/duplicating_table_top.png', 'Duplicating Table RP/textures/blocks/duplicating_table_top.png')
    ]
    
    logger.info("Starting texture file processing...")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Files in current directory: {os.listdir('.')}")
    
    if os.path.exists('textures'):
        logger.info(f"Textures directory exists. Contents: {os.listdir('textures')}")
        if os.path.exists('textures/blocks'):
            logger.info(f"Textures/blocks directory contents: {os.listdir('textures/blocks')}")
        else:
            logger.warning("textures/blocks directory does not exist")
    else:
        logger.warning("textures directory does not exist")
    
    for local_path, zip_path in texture_files:
        try:
            logger.info(f"Processing texture: {local_path}")
            if os.path.exists(local_path):
                with open(local_path, 'rb') as texture_file:
                    texture_content = texture_file.read()
                zipf.writestr(zip_path, texture_content)
                logger.info(f"Successfully added real texture: {local_path} -> {zip_path} ({len(texture_content)} bytes)")
            else:
                # Fall back to placeholder if texture file doesn't exist
                placeholder_png = create_placeholder_texture()
                zipf.writestr(zip_path, placeholder_png)
                logger.warning(f"Texture not found at {local_path}, using placeholder")
        except Exception as e:
            logger.error(f"Error processing texture {local_path}: {e}")
            # Add placeholder on error
            try:
                placeholder_png = create_placeholder_texture()
                zipf.writestr(zip_path, placeholder_png)
                logger.info(f"Added placeholder for {zip_path} due to error")
            except Exception as e2:
                logger.error(f"Error creating placeholder for {zip_path}: {e2}")
    
    logger.info("Complete pack metadata added (BP + RP)")

def create_placeholder_texture():
    """Create a simple placeholder texture for the block faces"""
    # Minimal 16x16 PNG file (transparent placeholder)
    return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10\x08\x06\x00\x00\x00\x1f\xf3\xffa\x00\x00\x00\x1dIDATx\x9cc\xf8\x0f\x00\x01\x01\x01\x00\x18\xdd\x8d\xb4\x1c\x00\x00\x00\x00IEND\xaeB`\x82'

def add_custom_metadata(zipf, items):
    """Add README for custom structure"""
    try:
        readme_content = f"""# Custom Recipe Pack

This pack contains {len(items)} duplication recipes organized by category.

## Folder Structure:
- ores/ - Ore-related items
- metals/ - Ingots and metal items  
- wood/ - Wood and wooden items
- stone/ - Stone and rock items
- gems/ - Precious gems and crystals
- food/ - Food and consumable items
- misc/ - Everything else

## Installation:
Place the recipe files in your Minecraft data folder according to your needs.

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total items: {len(items)}
"""
        zipf.writestr("README.md", readme_content)
        logger.info("Added custom metadata README")
    except Exception as e:
        logger.error(f"Error adding custom metadata: {e}")

@app.route("/download")
def download_zip():
    """Download the basic recipe ZIP"""
    try:
        if not os.path.exists(ZIP_PATH):
            logger.warning("ZIP file not found for download")
            return "ZIP file not found. Please generate recipes first.", 404
        
        # Check file size is reasonable
        file_size = os.path.getsize(ZIP_PATH)
        if file_size == 0:
            logger.error("ZIP file is empty")
            return "ZIP file is empty. Please regenerate recipes.", 404
        
        logger.info(f"Downloading ZIP file: {file_size:,} bytes")
        return send_file(ZIP_PATH, as_attachment=True, 
                        download_name="minecraft_recipes.zip", 
                        mimetype='application/zip')
    except Exception as e:
        logger.error(f"Error in download: {e}")
        return "Download failed. Please try again.", 500

@app.route("/api/last-session")
def get_last_session():
    """API endpoint to get last session data"""
    try:
        session_data = load_last_session()
        return jsonify(session_data)
    except Exception as e:
        logger.error(f"Error getting last session: {e}")
        return jsonify({"items": [], "selected": [], "timestamp": None})

@app.route("/api/update-session", methods=["POST"])
def update_session():
    """API endpoint to update session without generating recipes"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"})
        
        items = data.get("items", [])
        selected = data.get("selected", [])
        
        # Validate inputs
        items = validate_item_names(items)
        selected = validate_item_names(selected)
        
        # Save the session
        save_session(items, selected)
        
        return jsonify({"success": True, "message": "Session updated successfully"})
    except ValueError as e:
        logger.error(f"Validation error updating session: {e}")
        return jsonify({"success": False, "error": f"Invalid data: {str(e)}"})
    except Exception as e:
        logger.error(f"Error updating session: {e}")
        return jsonify({"success": False, "error": "Failed to save session"})

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return render_template_string(HTML_TEMPLATE, 
                                message="", 
                                error="Page not found."), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return render_template_string(HTML_TEMPLATE, 
                                message="", 
                                error="Internal server error. Please try again."), 500

@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

# Cleanup function for startup
def startup_cleanup():
    """Clean up old files on startup"""
    try:
        # Clean up old custom ZIP files
        if os.path.exists("data"):
            for filename in os.listdir("data"):
                if filename.startswith("custom_") and filename.endswith(".zip"):
                    file_path = os.path.join("data", filename)
                    try:
                        # Remove files older than 1 hour
                        if time.time() - os.path.getmtime(file_path) > 3600:
                            os.remove(file_path)
                            logger.info(f"Cleaned up old file: {filename}")
                    except Exception as e:
                        logger.warning(f"Could not clean up {filename}: {e}")
        
        # Clean up output directory
        cleanup_old_files()
        
    except Exception as e:
        logger.warning(f"Error in startup cleanup: {e}")

if __name__ == "__main__":
    # Perform startup cleanup
    startup_cleanup()
    
    # Log startup information
    logger.info("Starting Minecraft Recipe Generator")
    logger.info(f"Template path: {TEMPLATE_PATH}")
    logger.info(f"Pack icon path: {PACK_ICON_PATH}")
    logger.info(f"Texture directory: {TEXTURE_DIR}")
    
    # Check for required files
    if not os.path.exists(TEMPLATE_PATH):
        logger.error(f"Template file not found: {TEMPLATE_PATH}")
    if not os.path.exists(PACK_ICON_PATH):
        logger.warning(f"Pack icon not found: {PACK_ICON_PATH}")
    
    app.run(host="0.0.0.0", port=5096, debug=False)