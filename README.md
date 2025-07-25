# NIfTI Header Correction Tool

A command-line tool for processing T1w NIfTI files with 4D→3D conversion, deobliquing, and reorientation using AFNI.

## What it does

For each T1w file found in your dataset, the tool:
1. **Extracts first volume** from 4D images (if needed)
2. **Removes obliquity** using AFNI's 3dWarp 
3. **Reorients to target orientation** (default: LPI)

## Quick Start

### Install
```bash
pip install niwrap rich
```

### Run
```bash
# Basic usage - process all T1w files in dataset
python niwrap_correct_headers.py -d /path/to/your/dataset

# With custom orientation 
python niwrap_correct_headers.py -d /path/to/dataset --orient RAS

# Save to output directory instead of in-place
python niwrap_correct_headers.py -d /path/to/dataset -o /path/to/output
```

## Usage Examples

```bash
# Process BIDS dataset with LPI orientation (default)
python niwrap_correct_headers.py -d /data/bids_study

# Process with RAS orientation and 8 parallel jobs
python niwrap_correct_headers.py -d /data/study --orient RAS -j 8

# Process to output directory, skip confirmation
python niwrap_correct_headers.py -d /data/study -o /data/corrected --no-confirm
```

## Options

| Flag | Description | Example |
|------|-------------|---------|
| `-d, --dataset` | **Required.** Path to dataset directory | `-d /data/study` |
| `--orient` | Target orientation (default: LPI) | `--orient RAS` |
| `-o, --output` | Output directory (default: in-place) | `-o /data/corrected` |
| `-j, --jobs` | Parallel jobs (default: all CPUs) | `-j 8` |
| `--no-confirm` | Skip confirmation prompt | `--no-confirm` |

## Orientations

Common orientation codes:
- **LPI**: Left-Posterior-Inferior (neurological)
- **RAS**: Right-Anterior-Superior (radiological) 
- **LAI**: Left-Anterior-Inferior
- **RPI**: Right-Posterior-Inferior

## File Discovery

Finds all files matching: `**/*T1w.nii.gz`

Works with any directory structure:
```
dataset/
├── sub-01/anat/sub-01_T1w.nii.gz     ✓
├── sub-02/ses-1/anat/sub-02_ses-1_T1w.nii.gz     ✓
└── derivatives/sub-03_T1w.nii.gz     ✓
```

## Requirements

- **AFNI** (for 3dcalc, 3dWarp, 3dresample)
- **Python 3.8+**
- **niwrap** and **rich** packages

Make sure AFNI is in your PATH:
```bash
which 3dcalc  # should return a path
```

## Output

The tool shows a nice progress bar and summary:

```
╭─ Processing Summary ─────────────────╮
│ Dataset Path      │ /data/study      │
│ Files Found       │ 42               │
│ Target Orientation│ LPI              │
│ Parallel Jobs     │ 8                │
╰───────────────────┴──────────────────╯

⠋ Processing T1w files... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 25/42 • 0:01:30 • 0:02:15

╭─ Processing Results ─────────────────╮
│ ✅ Successful    │       40          │
│ ❌ Failed        │        2          │
╰──────────────────┴───────────────────╯
```

## Troubleshooting

**"No T1w files found"**: Check your dataset path and ensure files end with `T1w.nii.gz`

**AFNI errors**: Make sure AFNI is installed and in your PATH

**Permission errors**: Ensure write permissions for in-place processing or