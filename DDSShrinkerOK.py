import os
import re
import time
import shutil
import subprocess
import tkinter as tk
import sys
from tkinter import filedialog, messagebox
from pathlib import Path

# Path configuration
BASE_DIR = Path(r"C:/ddsConvert")
TEXCONV_PATH = BASE_DIR / "texconv.exe"
TEXDIAG_PATH = BASE_DIR / "texdiag.exe"
CONFIG_SRC = BASE_DIR / ".last_src"
OUTPUT_DIR = BASE_DIR / "OUT-Converted"
ORIGINAL_DIR = BASE_DIR / "OUT-Original"
EXCLUSIONS_DIR = BASE_DIR / "OUT-Excluded"
TOO_SMALL_DIR = BASE_DIR / "OUT-Small"
FORCED_DDS_FORMAT = None
# FORCED_DDS_FORMAT = "BC1_UNORM"
SKIP_TECH_SUFFIXES = False
SKIP_MIN_DIMENSION = True

# Minimum dimension threshold to avoid downscaling small UI/icon textures
MIN_PIXEL_DIMENSION = 8
MIN_FILE_SIZE_MB = 0

# Suffixes to skip (normal maps, PBR/comp maps, lightmaps, metallic/specular maps)
# EXCLUDED_SUFFIXES = [
#    "_NORMAL", "_NORM", "_NOMAL", "-NORMAL", "-NORM", "-NOMAL",
#    "_COMP", "-COMP", "_COMB",
#    "_MTL", "_METALIC", "_METALLIC", "-METAL", "_MET",
#    "_LM", "_SPECULAR", "_SPACULER", "_EMISSIVE", "_EMMISIVE", "_AO"
# ]

# Textures to exclude from resizing
EXCLUDED_SUFFIXES = [
    # Asphalt / road surfaces
    "ASPHALT", "ASPHAL", "ASPH",
    "TARMAC", "BITUMEN", "BITUMINOUS",
    "ROAD", "ROADS",

    # Concrete / cement / pavement
    "CONCRETE", "CONCRET", "CEMENT",
    "PAVEMENT", "PAVING", "PAVINGSTONE",
    "SIDEWALK", "FOOTPATH", "_TILE",

    # Ground surfaces
    "DIRT", "EARTH", "SOIL", "PUDDLE"
    "GRAVEL", "GRIT", "SAND", "MUD",
    "GROUND", "GROND", "TERRAIN", "DECAL",

    # Grass / vegetation
    "GRASS", "TURF", "SOD",
    "VEGETATION",

    # Airport markings
    "MARKING", "MARKINGS", "MARK",
    "PAINT", "STRIPE", "STRIPES",
    "STENCIL", "CHEVRON", "_EDGE", "_LINE"
    "DESIGNATOR", "NUMBER",

    # Runway / taxiway surfaces and markings
    "RUNWAY", "RWY",
    "TAXIWAY", "TAXI", "TWY",
    "APRON", "SKID", 
    "CENTERLINE", "CENTRELINE",
    "THRESHOLD", "HOLDING",
    "HOLD_SHORT", "HOLDINGPOINT",
    "SHOULDER", "BLASTPAD",
    "PARKING", "STAND"
]

# Read skip_excludes from command line argument (default to True if not provided)
if len(sys.argv) > 1:
    arg_val = sys.argv[1].strip().lower()
    if arg_val in ["false", "0", "no"]:
        SKIP_TECH_SUFFIXES = False
    else:
        SKIP_TECH_SUFFIXES = True


def get_dds_info(file_path: Path):
    """Uses texdiag.exe to extract width, height, and DXGI format from a DDS file."""
    cmd = [str(TEXDIAG_PATH), "info", str(file_path)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        return None, None, None

    output = result.stdout
    width_match = re.search(r"width\s*=\s*(\d+)", output, re.IGNORECASE)
    height_match = re.search(r"height\s*=\s*(\d+)", output, re.IGNORECASE)
    format_match = re.search(r"format\s*=\s*([A-Z0-9_]+)", output, re.IGNORECASE)

    if width_match and height_match and format_match:
        return int(width_match.group(1)), int(height_match.group(1)), format_match.group(1)

    return None, None, None


def get_saved_path(config_file: Path) -> str:
    if config_file.exists():
        saved = config_file.read_text(encoding="utf-8").strip()
        if os.path.isdir(saved):
            return saved
    return "C:\\"


def select_folder(title: str, config_file: Path) -> Path | None:
    initial = get_saved_path(config_file)
    selected = filedialog.askdirectory(title=title, initialdir=initial)
    if selected:
        config_file.write_text(selected, encoding="utf-8")
        return Path(selected)
    return None


def convert_dds(target_width, target_height, dds_format, file_path, output_dir):
    cmd = [
        str(TEXCONV_PATH),
        "-w", str(target_width),
        "-h", str(target_height),
        "-f", dds_format,
        "-m", "0",
        "-if", "CUBIC",
        "-y",
        "-o", str(output_dir),
        str(file_path)
    ]

    # Execute conversion with texconv
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    shutil.copy2(file_path, ORIGINAL_DIR / file_path.name)

    return result


def main():
    if not TEXCONV_PATH.exists():
        print(f"ERROR: texconv.exe not found at {TEXCONV_PATH}")
        input("Press Enter to exit...")
        return

    if not TEXDIAG_PATH.exists():
        print(f"ERROR: texdiag.exe not found at {TEXDIAG_PATH}")
        input("Press Enter to exit...")
        return

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    src_dir = select_folder("1. Select SOURCE folder containing DDS files", CONFIG_SRC)
    if not src_dir:
        print("Operation cancelled.")
        return

    dst_dir = Path(OUTPUT_DIR)
    if not dst_dir or not dst_dir.exists():
        print("Destination folder invalid or operation cancelled.")
        return

    dds_files = list(src_dir.glob("*.dds"))
    total_files = len(dds_files)

    if total_files == 0:
        print("No .dds files found in the source folder.")
        input("Press Enter to exit...")
        return

    # Clean previous working directories (IN- and OUT-) before starting
    print("Cleaning previous working folders (IN- and OUT-)...")
    for item in BASE_DIR.iterdir():
        if item.is_dir() and (item.name.startswith("IN-") or item.name.startswith("OUT-")):
            for sub_file in item.glob("*.*"):
                try:
                    sub_file.unlink()
                except Exception as e:
                    print(f"  [WARNING] Could not delete {sub_file.name}: {e}")

    # Clean exclusions folder before starting if it exists
    if EXCLUSIONS_DIR.exists():
        for sub_file in EXCLUSIONS_DIR.glob("*.*"):
            try:
                sub_file.unlink()
            except Exception as e:
                print(f"  [WARNING] Could not delete {sub_file.name} from exclusions folder: {e}")

    print(f"\nSource:      {src_dir}")
    print(f"Destination: {dst_dir}")
    print(f"Starting conversion of {total_files} files...\n")

    # Start timer
    start_time = time.time()

    converted_count = 0
    verified_count = 0
    skipped_count = 0
    excluded_count = 0
    small_count = 0
    total_original_bytes = 0
    total_new_bytes = 0
    total_excluded_bytes = 0
    total_small_bytes = 0

    for index, file_path in enumerate(dds_files, start=1):
        progress_pct = (index / total_files) * 100
        upper_name = file_path.name.upper()

        orig_size = file_path.stat().st_size
        orig_size_mb = orig_size / 1048576
        width, height, dds_format = get_dds_info(file_path)

        target_width = max(4, width // 2)
        target_height = max(4, height // 2)
        output_file_path = dst_dir / file_path.name

        if width is None or height is None or dds_format is None:
            skipped_count += 1
            print(
                f"[{index}/{total_files} - {progress_pct:.1f}%] SKIPPED (Unable to read DDS header via texdiag): {file_path.name}")

            continue

        total_original_bytes += orig_size

        # Skip technical maps (normals, comp, metallic, lightmaps, etc.)
        if any(suffix in upper_name for suffix in EXCLUDED_SUFFIXES):
            if SKIP_TECH_SUFFIXES:
                excluded_count += 1
                print(f"[{index}/{total_files} - {progress_pct:.1f}%] SKIPPED (Technical map suffix): {file_path.name} - {orig_size_mb:.3f}")
                # Copy excluded file to the configured exclusions folder
                try:
                    convert_dds(target_width, target_height, dds_format, file_path, Path(EXCLUSIONS_DIR))

                except Exception as e:
                    print(f"  [WARNING] Could not copy {file_path.name} to {EXCLUSIONS_DIR}: {e}")
                total_new_bytes += orig_size
                excluded_file_path = EXCLUSIONS_DIR / file_path.name
                if excluded_file_path.exists():
                    excl_size = excluded_file_path.stat().st_size
                    total_excluded_bytes += excl_size
                continue

            else:
                try:
                    shutil.copy2(file_path, EXCLUSIONS_DIR / file_path.name)

                except Exception as e:
                    print(f"  [WARNING] Could not copy {file_path.name} to {EXCLUSIONS_DIR}: {e}")

        # Skip textures that are already small
        if SKIP_MIN_DIMENSION and (
                (width <= MIN_PIXEL_DIMENSION and height <= MIN_PIXEL_DIMENSION) or orig_size_mb <= MIN_FILE_SIZE_MB):
            small_count += 1
            print(
                f"[{index}/{total_files} - {progress_pct:.1f}%] SKIPPED (Too small) {MIN_PIXEL_DIMENSION}px: {width}x{height}): {file_path.name} - {orig_size_mb:.3f}MB")

            try:
                TOO_SMALL_DIR.mkdir(parents=True, exist_ok=True)
                # shutil.copy2(file_path, TOO_SMALL_DIR / file_path.name)
                convert_dds(target_width, target_height, dds_format, file_path, Path(TOO_SMALL_DIR))

            except Exception as e:
                print(f"  [WARNING] Could not copy {file_path.name} to {EXCLUSIONS_DIR}: {e}")

            total_new_bytes += orig_size
            total_small_bytes += orig_size

            continue

        if FORCED_DDS_FORMAT is not None:
            dds_format = FORCED_DDS_FORMAT

        result = convert_dds(target_width, target_height, dds_format, file_path, dst_dir)

        if result.returncode == 0:
            converted_count += 1

            # Post-conversion size verification
            if output_file_path.exists():
                new_size = output_file_path.stat().st_size
                expected_size = orig_size / 4.0
                actual_ratio = (new_size / orig_size) * 100
                tolerance = expected_size * 0.02

                if abs(new_size - expected_size) <= tolerance:
                    verified_count += 1
                    print(
                        f"[{index}/{total_files} - {progress_pct:.1f}%] [OK] {file_path.name} ({width}x{height} -> {target_width}x{target_height} | {orig_size_mb:.1f}MB | {dds_format} | Ratio: {actual_ratio:.2f}%)"
                    )
                else:
                    print(
                        f"[{index}/{total_files} - {progress_pct:.1f}%] [WARNING] {file_path.name} ({width}x{height} -> {target_width}x{target_height} | {orig_size_mb:.1f}MB | {dds_format}) | Actual ratio: {actual_ratio:.2f}% (Expected ~25%)"
                    )

                total_new_bytes += new_size
            else:
                print(
                    f"[{index}/{total_files} - {progress_pct:.1f}%] [ERROR] Output file not found for {file_path.name}"
                )
        else:
            print(
                f"[{index}/{total_files} - {progress_pct:.1f}%] [ERROR] Conversion failed for {file_path.name}: {result.stderr.strip()}"
            )

    skipped_count += excluded_count + small_count

    # Stop timer and calculate elapsed time
    end_time = time.time()
    elapsed_seconds = end_time - start_time

    minutes = int(elapsed_seconds // 60)
    seconds = elapsed_seconds % 60

    # Calculate disk space saved
    saved_bytes = total_original_bytes - total_new_bytes
    saved_mb = saved_bytes / (1024 * 1024)
    orig_mb = total_original_bytes / (1024 * 1024)
    new_mb = total_new_bytes / (1024 * 1024)
    excl_mb = total_excluded_bytes / (1024 * 1024)
    small_mb = total_small_bytes / (1024 * 1024)
    reduction_pct = (saved_bytes / total_original_bytes * 100) if total_original_bytes > 0 else 0

    print("\n" + "=" * 65)
    print("Process completed successfully.")
    print(f" - Files converted successfully : {converted_count}")
    print(f" - Verified at exact 1/4 ratio  : {verified_count}")
    print(f" - Skipped (excluded/small/err) : {skipped_count}")
    print(f"    - Excluded                  : {excluded_count}")
    print(f"    - Too small                 : {small_count}")
    print("-" * 65)
    print("📊 DISK SPACE SUMMARY:")
    print(f" - Total original size  : {orig_mb:.2f} MB")
    print(f" - Total reduced size   : {new_mb:.2f} MB")
    print(f" - Total excluded size  : {excl_mb:.2f} MB")
    print(f" - Total too small size : {small_mb:.2f} MB")
    print(f" - Total space saved    : {saved_mb:.2f} MB ({reduction_pct:.1f}% reduction)")
    print("-" * 65)
    if minutes > 0:
        print(f" ⏱️ Total elapsed time: {minutes} minutes and {seconds:.2f} seconds ({elapsed_seconds:.2f}s)")
    else:
        print(f" ⏱️ Total elapsed time: {seconds:.2f} segundos")
    print("=" * 65)

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    answer = messagebox.askyesno(
        "Overwrite originals",
        f"Do you want to copy the {converted_count} converted files back to the source folder:\n\n{src_dir}\n\n(This will overwrite the original DDS files)"
    )

    if answer:
        print("\n🔄 Copying converted files back to source directory (overwriting)...")
        copied_to_source = 0
        for conv_file in dst_dir.glob("*.dds"):
            try:
                destination_original = src_dir / conv_file.name
                with open(conv_file, 'rb') as fsrc, open(destination_original, 'wb') as fdst:
                    fdst.write(fsrc.read())
                copied_to_source += 1
            except Exception as e:
                print(f"  [ERROR] Could not overwrite {conv_file.name}: {e}")
        print(f"✅ Successfully overwritten {copied_to_source} files in the source folder!")

        answer = messagebox.askyesno(
            "Launch backup",
            "Do you want to run the airport backup script?"
        )

        if answer:
            print("\n🚀 Launching airport backup script...")
            backup_script_path = BASE_DIR / "BackupShrinkedAirport.py"

            if backup_script_path.exists():
                try:
                    subprocess.run([sys.executable, str(backup_script_path)], check=True)
                    print("✅ Backup script finished successfully!")
                except Exception as e:
                    print(f"  [ERROR] An error occurred while running the backup script: {e}")
            else:
                print(f"  [ERROR] File not found at path: {backup_script_path}")

    else:
        print("\n📁 Converted files remain only in the destination folder.")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()