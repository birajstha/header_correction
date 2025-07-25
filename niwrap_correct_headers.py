from niwrap import afni
import os
import glob
import argparse
import multiprocessing as mp
from functools import partial
import tempfile
import uuid
import shutil
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box
from rich.prompt import Confirm
import time
import concurrent.futures

console = Console()

def convert_4d_to_3d(input_image_path, output_image_path):
    """
    Convert a 4D NIfTI image to a 3D NIfTI image by extracting the first volume using AFNI.
    """
    afni.v_3dcalc(
        in_file_a=input_image_path + "[0]",  # Input dataset, first volume
        expr="a",                    # Just copy the input
        prefix=output_image_path
    )

def deoblique(input_image_path, output_image_path):
    """
    Deoblique a NIfTI image using AFNI's 3dWarp.
    """
    afni.v_3d_warp(dataset=input_image_path, prefix=output_image_path, deoblique=True)

def reorient_to_orientation(input_image_path, output_image_path, orientation="LPI"):
    """
    Reorient image to specified orientation.
    """
    afni.v_3dresample(in_file=input_image_path, orientation=orientation, prefix=output_image_path)

def process_single_file(input_image_path, output_dir=None, orientation="LPI"):
    """
    Process a single T1w file with proper error handling.
    """
    try:
        # Determine output path
        if output_dir:
            filename = os.path.basename(input_image_path)
            final_output_path = os.path.join(output_dir, filename)
            os.makedirs(output_dir, exist_ok=True)
        else:
            final_output_path = input_image_path
        
        # Create unique temporary directory for this process
        temp_dir = tempfile.mkdtemp(prefix=f"niwrap_{os.getpid()}_{uuid.uuid4().hex[:8]}_")
        
        try:
            # Use unique temporary files within the temp directory
            temp_3d_path = os.path.join(temp_dir, "temp_3d.nii.gz")
            temp_deoblique_path = os.path.join(temp_dir, "temp_deoblique.nii.gz")
            temp_final_path = os.path.join(temp_dir, "temp_final.nii.gz")
            
            # Process the file
            convert_4d_to_3d(input_image_path, temp_3d_path)
            deoblique(temp_3d_path, temp_deoblique_path)
            reorient_to_orientation(temp_deoblique_path, temp_final_path, orientation)
            
            # Move to final location
            if output_dir:
                shutil.move(temp_final_path, final_output_path)
            else:
                shutil.move(temp_final_path, input_image_path)
            
            return {"status": "success", "file": input_image_path}
            
        finally:
            # Clean up temporary directory
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                    
    except Exception as e:
        return {"status": "error", "file": input_image_path, "error": str(e)}

def display_header():
    """Display a beautiful header."""
    title = Text("NIfTI Header Correction Tool", style="bold magenta")
    subtitle = Text("Processing T1w files with 4D→3D conversion, deobliquing, and reorientation", style="dim")
    
    panel = Panel.fit(
        f"{title}\n{subtitle}",
        border_style="blue",
        padding=(1, 2)
    )
    console.print(panel)
    console.print()

def display_summary(dataset, t1w_files, n_jobs, output_dir, orientation):
    """Display processing summary before starting."""
    table = Table(show_header=True, header_style="bold blue", box=box.ROUNDED)
    table.add_column("Parameter", style="cyan", width=20)
    table.add_column("Value", style="green")
    
    table.add_row("Dataset Path", dataset)
    table.add_row("Files Found", str(len(t1w_files)))
    table.add_row("Target Orientation", orientation)
    table.add_row("Parallel Jobs", str(n_jobs))
    table.add_row("Output Mode", output_dir if output_dir else "In-place")
    
    console.print(Panel(table, title="Processing Summary", border_style="green"))
    console.print()

def display_results(successful, failed, errors):
    """Display final results."""
    console.print()
    
    # Results table
    table = Table(show_header=True, header_style="bold blue", box=box.ROUNDED)
    table.add_column("Status", style="bold", width=12)
    table.add_column("Count", justify="right", style="bold", width=8)
    
    table.add_row("✅ Successful", str(successful), style="green")
    table.add_row("❌ Failed", str(failed), style="red")
    table.add_row("📊 Total", str(successful + failed), style="blue")
    
    console.print(Panel(table, title="Processing Results", border_style="blue"))
    
    # Show errors if any
    if errors:
        console.print()
        error_text = "\n".join([f"• {os.path.basename(error['file'])}: {error['error'][:100]}..." 
                               if len(error['error']) > 100 
                               else f"• {os.path.basename(error['file'])}: {error['error']}" 
                               for error in errors[:5]])
        error_panel = Panel(
            error_text,
            title=f"Errors ({len(errors)} total)",
            border_style="red"
        )
        console.print(error_panel)
        
        if len(errors) > 5:
            console.print(f"[dim]... and {len(errors) - 5} more errors[/dim]")

def process_files_with_progress(t1w_files, output_dir, n_jobs, orientation):
    """Process files with a beautiful progress bar."""
    results = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        console=console,
        expand=True
    ) as progress:
        
        task = progress.add_task("Processing T1w files...", total=len(t1w_files))
        
        # Use ProcessPoolExecutor for better progress tracking
        process_func = partial(process_single_file, output_dir=output_dir, orientation=orientation)
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=n_jobs) as executor:
            # Submit all tasks
            future_to_file = {executor.submit(process_func, file_path): file_path 
                             for file_path in t1w_files}
            
            # Process completed tasks as they finish
            for future in concurrent.futures.as_completed(future_to_file):
                try:
                    result = future.result()
                    results.append(result)
                    progress.advance(task)
                except Exception as e:
                    file_path = future_to_file[future]
                    results.append({"status": "error", "file": file_path, "error": str(e)})
                    progress.advance(task)
    
    # Separate successful and failed results
    successful = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "error")
    errors = [r for r in results if r["status"] == "error"]
    
    return successful, failed, errors

def validate_orientation(orientation):
    """Validate orientation string."""
    valid_orientations = [
        "RPI", "LPI", "RAI", "LAI", "RPS", "LPS", "RAS", "LAS",
        "IPR", "IPL", "IAR", "IAL", "SPR", "SPL", "SAR", "SAL",
        "PIR", "PIL", "AIR", "AIL", "PSR", "PSL", "ASR", "ASL"
    ]
    
    if orientation.upper() not in valid_orientations:
        raise argparse.ArgumentTypeError(
            f"Invalid orientation '{orientation}'. Must be one of: {', '.join(valid_orientations)}"
        )
    return orientation.upper()

def main():
    parser = argparse.ArgumentParser(
        description="Process T1w NIfTI files to correct headers using AFNI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -d /path/to/dataset
  %(prog)s -d /path/to/dataset -o /path/to/output -j 8
  %(prog)s -d /path/to/dataset --orient RAS
  %(prog)s -d /path/to/dataset --no-confirm

Orientation codes (default: LPI):
  L/R = Left/Right, A/P = Anterior/Posterior, I/S = Inferior/Superior
  Examples: LPI, RAS, LAI, etc.
        """
    )
    parser.add_argument("-d", "--dataset", required=True, 
                       help="Path to dataset directory containing T1w files")
    parser.add_argument("-o", "--output", 
                       help="Output directory (if not specified, files are processed in-place)")
    parser.add_argument("--orient", "--orientation", type=validate_orientation, 
                       default="LPI", metavar="ORIENT",
                       help="Target orientation (default: LPI). Examples: RAS, LAI, RPI, etc.")
    parser.add_argument("-j", "--jobs", type=int, default=mp.cpu_count(),
                       help=f"Number of parallel jobs (default: {mp.cpu_count()})")
    parser.add_argument("--no-confirm", action="store_true",
                       help="Skip confirmation prompt")
    
    args = parser.parse_args()
    
    # Display header
    display_header()
    
    # Validate inputs
    if not os.path.exists(args.dataset):
        console.print(f"[red]Error: Dataset directory '{args.dataset}' does not exist[/red]")
        return
    
    # Find all T1w files
    with console.status("[bold green]Searching for T1w files...", spinner="dots"):
        t1w_pattern = os.path.join(args.dataset, "**", "*T1w.nii.gz")
        t1w_files = glob.glob(t1w_pattern, recursive=True)
    
    if not t1w_files:
        console.print(f"[yellow]No T1w files found in {args.dataset}[/yellow]")
        return
    
    # Display summary
    display_summary(args.dataset, t1w_files, args.jobs, args.output, args.orient)
    
    # Confirmation prompt
    if not args.no_confirm:
        if not Confirm.ask(f"Proceed with processing {len(t1w_files)} files to {args.orient} orientation?"):
            console.print("[yellow]Operation cancelled.[/yellow]")
            return
        console.print()
    
    # Process files
    start_time = time.time()
    successful, failed, errors = process_files_with_progress(t1w_files, args.output, args.jobs, args.orient)
    end_time = time.time()
    
    # Display results
    display_results(successful, failed, errors)
    
    # Processing time
    processing_time = end_time - start_time
    console.print(f"\n[dim]Total processing time: {processing_time:.1f} seconds[/dim]")

if __name__ == "__main__":
    main()