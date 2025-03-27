from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from collections import defaultdict
from pathlib import Path
import re

def process_transcripts(input_dir, output_root):
    """Process text files into merged transcripts and PDFs with specified file_uploader structure"""
    input_path = Path(input_dir)

    print(f"\n=== INITIAL SETUP ===")
    print(f"Input directory: {input_path.resolve()}")
    print(f"Output root: {output_root}")

    # Create file_uploader directories
    pdf_output_dir = Path(output_root) / " merged pdf Files"
    txt_output_dir = Path(output_root) / "merged txt Files"

    print(f"\nCreating directories:")
    print(f"PDF file_uploader: {pdf_output_dir}")
    print(f"TXT file_uploader: {txt_output_dir}")

    pdf_output_dir.mkdir(parents=True, exist_ok=True)
    txt_output_dir.mkdir(parents=True, exist_ok=True)

    # Verify directory creation
    print(f"\nDirectory check:")
    print(f"PDF dir exists: {pdf_output_dir.exists()}")
    print(f"TXT dir exists: {txt_output_dir.exists()}")

    # Organize files by their base identifier
    file_groups = defaultdict(list)
    print("\n=== FILE PROCESSING ===")

    # Process files matching the multi-page pattern
    for txt_file in input_path.rglob('*.txt'):
        print(f"\nProcessing file: {txt_file.name}")
        print(f"Full path: {txt_file.resolve()}")

        # Extract base identifier and page number from filename
        stem = txt_file.stem
        print(f"File stem: {stem}")

        match = re.match(r'^(.+?)_(\d{3})_(\d{3})$', stem)
        if match:
            print("Multi-page file detected")
            base_id = f"{match.group(1)}_{match.group(2)}"
            page_num = match.group(3)
        else:
            print("Single-page file detected")
            base_id = stem
            page_num = None

        print(f"Base ID: {base_id}")
        print(f"Page number: {page_num}")
        file_groups[base_id].append((page_num, txt_file))

    print(f"\n=== FILE GROUPS ===")
    print(f"Found {len(file_groups)} file groups")

    for group_id, files in file_groups.items():
        print(f"\nProcessing group: {group_id}")
        print(f"Number of files: {len(files)}")

        # Sort multi-page files numerically
        sorted_files = sorted(
            [f for f in files if f[0] is not None],
            key=lambda x: int(x[0])
        )
        print(f"Sorted multi-page files: {[f[0] for f in sorted_files]}")

        # Add single-page file if it exists
        sorted_files = [f for f in files if f[0] is None] + sorted_files
        print(f"Final sorted files: {[f[0] for f in sorted_files]}")

        # Read and merge content
        merged_content = []
        for page_num, file_path in sorted_files:
            print(f"\nProcessing page: {page_num or 'single-page'}")
            print(f"File path: {file_path}")

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"Original content length: {len(content)} characters")

                # Clean non-ASCII characters
                clean_content = re.sub(r'[^\x00-\x7F]+', '', content).strip()
                print(f"Cleaned content length: {len(clean_content)} characters")

                merged_content.append(clean_content)

        print(f"\nMerged content contains {len(merged_content)} pages")

        # Create file_uploader file names
        output_prefix = f"{group_id}_transcript"
        txt_output = txt_output_dir / f"{output_prefix}.txt"
        pdf_output = pdf_output_dir / f"{output_prefix}.pdf"

        print(f"\nSaving TXT to: {txt_output}")
        with open(txt_output, 'w', encoding='utf-8') as txt_file:
            txt_file.write('\n\n'.join(merged_content))
        print(f"TXT file created: {txt_output.exists()} ({txt_output.stat().st_size} bytes)")

        print(f"\nGenerating PDF to: {pdf_output}")
        try:
            c = canvas.Canvas(str(pdf_output), pagesize=letter)
            width, height = letter
            margin = 72
            line_height = 14
            y_position = height - margin
            font_size = 12

            c.setFont("Helvetica", font_size)
            print("PDF canvas created successfully")

            for page_content in merged_content:
                lines = page_content.split('\n')
                print(f"Processing {len(lines)} lines in page")

                for line in lines:
                    while len(line) > 0:
                        chunk = line[:85]
                        line = line[85:]

                        if y_position < margin + line_height:
                            print("New PDF page created")
                            c.showPage()
                            y_position = height - margin
                            c.setFont("Helvetica", font_size)

                        c.drawString(margin, y_position, chunk)
                        y_position -= line_height

                    y_position -= line_height  # Paragraph spacing

                y_position -= line_height * 2  # Page separation

            c.save()
            print(f"PDF saved successfully: {pdf_output.exists()} ({pdf_output.stat().st_size} bytes)")

        except Exception as e:
            print(f"Error generating PDF: {str(e)}")

if __name__ == '__main__':
    input_directory = '../files/merge_txt_to_pdf/input'
    output_root_directory = '../files/merge_txt_to_pdf/output'

    print("=== STARTING PROCESS ===")
    process_transcripts(input_directory, output_root_directory)
    print("\n=== PROCESS COMPLETE ===")