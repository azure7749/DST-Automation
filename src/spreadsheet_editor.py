import pandas as pd
import csv

# Load CSV data into a dictionary
csv_data = {}
path = "../docs/upload_progress.csv"
with open(path, 'r') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        base_id = row['BaseIdentifier']
        pdf = row['PDF']
        metadata = row['Metadata']
        csv_data[base_id] = (pdf, metadata)

# Load the Excel file
excel_file = pd.ExcelFile('../files/spreadsheet.xlsx')
df = pd.read_excel(excel_file, sheet_name=0)  # Assuming the first sheet is the data

# Update PDF and Transcript columns based on CSV data
for index, row in df.iterrows():
    identifiers = str(row['field_identifier']).split(',')
    pdf_created = 'No'
    transcript_uploaded = 'No'

    for part in identifiers:
        # Clean the part: strip whitespace and remove leading non-alphanumeric characters
        cleaned_part = part.strip().lstrip(':').strip()
        if cleaned_part.startswith('mvp_'):
            if cleaned_part in csv_data:
                pdf_val, metadata_val = csv_data[cleaned_part]
                if pdf_val == 'Yes':
                    pdf_created = 'Yes'
                if metadata_val == 'Yes':
                    transcript_uploaded = 'Yes'

    # Update the row in the DataFrame
    df.at[index, 'PDF/TXT Created?'] = pdf_created
    df.at[index, 'Transcript Uploaded?'] = transcript_uploaded

# Save the updated DataFrame to a new Excel file
with pd.ExcelWriter('../files/updated_project_status.xlsx') as writer:
    df.to_excel(writer, sheet_name='spreadsheet', index=False)
    # If there's a second sheet with file names, include it as well
    if len(excel_file.sheet_names) > 1:
        file_names_df = pd.read_excel(excel_file, sheet_name=1)
        file_names_df.to_excel(writer, sheet_name='file names', index=False)

print("Update completed. Saved to 'updated_project_status.xlsx'")