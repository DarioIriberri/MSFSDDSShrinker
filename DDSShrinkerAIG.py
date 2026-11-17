import os
import re
import subprocess
import time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

# Path configuration
BASE_DIR = Path(r"C:/ddsConvert")
TEXCONV_PATH = BASE_DIR / "texconv.exe"
TEXDIAG_PATH = BASE_DIR / "texdiag.exe"
CONFIG_SRC = BASE_DIR / ".last_aig_src"
FORCED_DDS_FORMAT = "BC1_UNORM"
SKIP_TECH_SUFFIXES = False
SKIP_MIN_DIMENSION = True
SRC_DIR = "C:/Users/dazz/AppData/Roaming/Microsoft Flight Simulator/Packages/Community/aig-aitraffic-oci/SimObjects/Airplanes"

# Minimum dimension threshold to skip tiny files
MIN_DIMENSION = 64

# Suffixes to skip (normal maps, PBR/comp maps, lightmaps, metallic/specular maps)
EXCLUDED_SUFFIXES = [
    "_NORMAL",
    "_NORM",
    "_NOMAL",
    "-NORMAL",
    "-NORM",
    "-NOMAL",
    "_COMP",
    "-COMP",
    "_COMB",
    "_MTL",
    "_METALIC",
    "_METALLIC",
    "-METAL",
    "_MET",
    "_LM",
    "_SPECULAR",
    "_SPACULER",
    "_EMISSIVE",
    "_EMMISIVE",
    "_AO",
]


def get_dds_info(file_path: Path):
  """Uses texdiag.exe to extract width, height, DXGI format, and mipLevels from a DDS file."""
  cmd = [str(TEXDIAG_PATH), "info", str(file_path)]
  result = subprocess.run(
      cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
  )
  if result.returncode != 0:
    return None, None, None, None

  output = result.stdout
  width_match = re.search(r"width\s*=\s*(\d+)", output, re.IGNORECASE)
  height_match = re.search(r"height\s*=\s*(\d+)", output, re.IGNORECASE)
  format_match = re.search(r"format\s*=\s*([A-Z0-9_]+)", output, re.IGNORECASE)
  mipmaps_match = re.search(r"mipLevels\s*=\s*(\d+)", output, re.IGNORECASE)

  if width_match and height_match and format_match:
    mipmaps = int(mipmaps_match.group(1)) if mipmaps_match else 1
    return (
        int(width_match.group(1)),
        int(height_match.group(1)),
        format_match.group(1),
        mipmaps,
    )

  return None, None, None, None


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
      f
      for f in Path(SRC_DIR).rglob("*")
      if f.is_file() and f.suffix.lower() == ".dds"
  ]
  total_files = len(dds_files)

  if total_files == 0:
    print("No .dds files found in the selected folder or its subdirectories.")
    input("Press Enter to exit...")
    return

  print(f"\nTarget Directory: {SRC_DIR}")
  print(f"Found {total_files} DDS files to process. Starting re-encoding...\n")

  # Start timer
  start_time = time.time()

  processed_count = 0
  verified_count = 0
  skipped_count = 0
  total_original_bytes = 0
  total_new_bytes = 0

  for index, file_path in enumerate(dds_files, start=1):
    progress_pct = (index / total_files) * 100
    upper_name = file_path.name.upper()

    orig_size = file_path.stat().st_size
    width, height, dds_format, orig_mipmaps = get_dds_info(file_path)

    if width is None or height is None or dds_format is None:
      skipped_count += 1
      print(
          f"[{index}/{total_files} - {progress_pct:.1f}%] SKIPPED (Unable to"
          f" read header): {file_path.name}"
      )
      continue

    total_original_bytes += orig_size

    # Skip technical maps (normals, comp, metallic, lightmaps, etc.)
    if SKIP_TECH_SUFFIXES and any(
        suffix in upper_name for suffix in EXCLUDED_SUFFIXES
    ):
      skipped_count += 1
      print(
          f"[{index}/{total_files} - {progress_pct:.1f}%] SKIPPED (Technical"
          f" map): {file_path.name}"
      )
      continue

    # Skip textures that are already small based on minimum dimension
    if SKIP_MIN_DIMENSION and width <= MIN_DIMENSION and height <= MIN_DIMENSION:
      skipped_count += 1
      print(
          f"[{index}/{total_files} - {progress_pct:.1f}%] SKIPPED (Resolution"
          f" <= {MIN_DIMENSION}px: {width}x{height}): {file_path.name}"
      )
      continue

    # Keep original dimensions and mipmaps 1:1 to prevent visual corruption
    target_width = width
    target_height = height
    target_mipmaps = orig_mipmaps
    parent_dir = file_path.parent

    if FORCED_DDS_FORMAT is not None:
      dds_format = FORCED_DDS_FORMAT

    cmd = [
        str(TEXCONV_PATH),
        "-w", str(target_width),
        "-h", str(target_height),
        "-f", dds_format,
        "-m", "1",
        "-y", "-o",
        str(parent_dir),
        str(file_path),
    ]

    # Execute re-encoding with texconv directly to the file's folder (overwriting)
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    if result.returncode == 0:
      processed_count += 1

      if file_path.exists():
        new_size = file_path.stat().st_size
        actual_ratio = (new_size / orig_size) * 100
        # 3% tolerance for file size variations during container re-writing
        tolerance = orig_size * 0.03

        if abs(new_size - orig_size) <= tolerance:
          verified_count += 1
          print(
              f"[{index}/{total_files} - {progress_pct:.1f}%] [OK]"
              f" {file_path.name} ({width}x{height} | {dds_format} | Ratio:"
              f" {actual_ratio:.2f}%)"
          )
        else:
          print(
              f"[{index}/{total_files} - {progress_pct:.1f}%] [WARNING]"
              f" {file_path.name} ({width}x{height} | {dds_format}) | Ratio:"
              f" {actual_ratio:.2f}%"
          )

        total_new_bytes += new_size
      else:
        print(
            f"[{index}/{total_files} - {progress_pct:.1f}%] [ERROR] File not"
            f" found after processing: {file_path.name}"
        )
    else:
      print(
          f"[{index}/{total_files} - {progress_pct:.1f}%] [ERROR] Processing"
          f" failed for {file_path.name}: {result.stderr.strip()}"
      )

  # Stop timer and calculate elapsed time
  end_time = time.time()
  elapsed_seconds = end_time - start_time

  minutes = int(elapsed_seconds // 60)
  seconds = elapsed_seconds % 60

  # Calculate disk space changes
  saved_bytes = total_original_bytes - total_new_bytes
  saved_mb = saved_bytes / (1024 * 1024)
  orig_mb = total_original_bytes / (1024 * 1024)
  new_mb = total_new_bytes / (1024 * 1024)
  reduction_pct = (
      (saved_bytes / total_original_bytes * 100)
      if total_original_bytes > 0
      else 0
  )

  print("\n" + "=" * 65)
  print("AIG Textures Re-encoding Process Completed.")
  print(f" - Files processed successfully : {processed_count}")
  print(f" - Verified within tolerance  : {verified_count}")
  print(f" - Skipped (excluded/small/err) : {skipped_count}")
  print("-" * 65)
  print("📊 DISK SPACE SUMMARY:")
  print(f" - Total original size : {orig_mb:.2f} MB")
  print(f" - Total re-encoded size: {new_mb:.2f} MB")
  print(
      f" - Total space change  : {saved_mb:.2f} MB ({reduction_pct:+.1f}%)"
  )
  print("-" * 65)
  if minutes > 0:
    print(
        f" ⏱️ Total elapsed time: {minutes} minutes and {seconds:.2f} seconds"
        f" ({elapsed_seconds:.2f}s)"
    )
  else:
    print(f" ⏱️ Total elapsed time: {seconds:.2f} segundos")
  print("=" * 65)

  input("\nPress Enter to exit...")


if __name__ == "__main__":
  main()