import os
import re
import time
import subprocess
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

# Path configuration
BASE_DIR = Path(r"C:/ddsConvert")
TEXCONV_PATH = BASE_DIR / "texconv.exe"
TEXDIAG_PATH = BASE_DIR / "texdiag.exe"
CONFIG_SRC = BASE_DIR / ".last_aig_src"
FORCED_DDS_FORMAT = None
SKIP_TECH_SUFFIXES = True
SKIP_MIN_DIMENSION = True
SRC_DIR = "C:/Users/dazz/AppData/Roaming/Microsoft Flight Simulator/Packages/Community/aig-aitraffic-oci/SimObjects/Airplanes"

# Minimum dimension threshold to avoid downscaling small UI/icon textures
MIN_DIMENSION = 1

# Suffixes to skip (normal maps, PBR/comp maps, lightmaps, metallic/specular maps)
EXCLUDED_SUFFIXES = [
    "_NORMAL", "_NORM", "_NOMAL", "-NORMAL", "-NORM", "-NOMAL",
    "_COMP", "-COMP", "_COMB",
    "_MTL", "_METALIC", "_METALLIC", "-METAL", "_MET",
    "_LM", "_SPECULAR", "_SPACULER", "_EMISSIVE", "_EMMISIVE", "_AO"
]


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

    if not SRC_DIR:
        print("Operation cancelled.")
        return

    # Recursive search for all .dds files in the directory tree
    print(f"Scanning for DDS files recursively in: {SRC_DIR} ...")
    dds_files = [
        f for f in Path(SRC_DIR).rglob("*") if f.is_file() and f.suffix.lower() == ".dds"
    ]
    total_files = len(dds_files)

    if total_files == 0:
        print("No .dds files found in the selected folder or its subdirectories.")
        input("Press Enter to exit...")
        return

    print(f"\nTarget Directory: {SRC_DIR}")
    print(f"Found {total_files} DDS files to process. Starting downscaling...\n")

    # Start timer
    start_time = time.time()

    converted_count = 0
    verified_count = 0
    skipped_count = 0
    total_original_bytes = 0
    total_new_bytes = 0

    for index, file_path in enumerate(dds_files, start=1):
        progress_pct = (index / total_files) * 100
        upper_name = file_path.name.upper()

        # Skip technical maps (normals, comp, metallic, lightmaps, etc.)
        if SKIP_TECH_SUFFIXES and any(suffix in upper_name for suffix in EXCLUDED_SUFFIXES):
            skipped_count += 1
            print(f"[{index}/{total_files} - {progress_pct:.1f}%] SKIPPED (Technical map): {file_path.name}")
            continue

        orig_size = file_path.stat().st_size
        width, height, dds_format = get_dds_info(file_path)

        if width is None or height is None or dds_format is None:
            skipped_count += 1
            print(f"[{index}/{total_files} - {progress_pct:.1f}%] SKIPPED (Unable to read header): {file_path.name}")
            continue

        # Skip textures that are already small
        if SKIP_MIN_DIMENSION and width <= MIN_DIMENSION and height <= MIN_DIMENSION:
            skipped_count += 1
            print(f"[{index}/{total_files} - {progress_pct:.1f}%] SKIPPED (Resolution <= {MIN_DIMENSION}px: {width}x{height}): {file_path.name}")
            continue

        target_width = max(4, width // 2)
        target_height = max(4, height // 2)
        parent_dir = file_path.parent

        if FORCED_DDS_FORMAT is not None:
            dds_format = FORCED_DDS_FORMAT

        cmd = [
            str(TEXCONV_PATH),
            "-w", str(target_width),
            "-h", str(target_height),
            "-f", dds_format,
            "-m", "1",
            "-if", "CUBIC",
            "-y",
            "-o", str(parent_dir),
            str(file_path)
        ]

        # Execute conversion with texconv directly to the file's folder (overwriting)
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode == 0:
            converted_count += 1

            if file_path.exists():
                new_size = file_path.stat().st_size
                expected_size = orig_size / 4.0
                actual_ratio = (new_size / orig_size) * 100
                tolerance = expected_size * 0.02

                if abs(new_size - expected_size) <= tolerance:
                    verified_count += 1
                    print(
                        f"[{index}/{total_files} - {progress_pct:.1f}%] [OK] {file_path.name} ({width}x{height} -> {target_width}x{target_height} | {dds_format} | Ratio: {actual_ratio:.2f}%)"
                    )
                else:
                    print(
                        f"[{index}/{total_files} - {progress_pct:.1f}%] [WARNING] {file_path.name} ({width}x{height} -> {target_width}x{target_height} | {dds_format}) | Ratio: {actual_ratio:.2f}%"
                    )

                total_original_bytes += orig_size
                total_new_bytes += new_size
            else:
                print(
                    f"[{index}/{total_files} - {progress_pct:.1f}%] [ERROR] File not found after processing: {file_path.name}"
                )
        else:
            print(
                f"[{index}/{total_files} - {progress_pct:.1f}%] [ERROR] Conversion failed for {file_path.name}: {result.stderr.strip()}"
            )

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
    reduction_pct = (saved_bytes / total_original_bytes * 100) if total_original_bytes > 0 else 0

    print("\n" + "=" * 65)
    print("AIG Textures Downscale Process Completed.")
    print(f" - Files processed successfully : {converted_count}")
    print(f" - Verified at exact 1/4 ratio  : {verified_count}")
    print(f" - Skipped (excluded/small/err) : {skipped_count}")
    print("-" * 65)
    print("📊 DISK SPACE SUMMARY:")
    print(f" - Total original size : {orig_mb:.2f} MB")
    print(f" - Total reduced size  : {new_mb:.2f} MB")
    print(f" - Total space saved   : {saved_mb:.2f} MB ({reduction_pct:.1f}% reduction)")
    print("-" * 65)
    if minutes > 0:
        print(f" ⏱️ Total elapsed time: {minutes} minutes and {seconds:.2f} seconds ({elapsed_seconds:.2f}s)")
    else:
        print(f" ⏱️ Total elapsed time: {seconds:.2f} segundos")
    print("=" * 65)

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()