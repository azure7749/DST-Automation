
# DST Automation

### About

_Life  is short_

This is a selenium-based automation tool built to improve the work efficiency of tedious digital library tasks.
It significantly improves the needed time for transcript uploading and metadata editing of the items in a digital collection. 

It is able to:
  * Merge multiple ```.txt``` transcript files with the same name tag into a ```.pdf```  and a ```.txt``` transcripts based.
  * Generate a ```.csv``` file that maps the ```uuid``` of the collections websites to item names and identifiers.
  * Automates the editing and uploading process through ```selenium```
  * Update the ```.xlsx``` spreadsheet after successful upload and edit. 

<!-- GETTING STARTED -->
## Getting Started

### Prerequisites

* Download the required libraries.

  ```sh
  pip install -r requirements.txt
  ```
* Update the login credential in ```config.ini```
* Prepare the input/output directories, which should resemble this structure:
  ```
  └── files/
      ├── file_uploader/
      │   └── input/
      │       ├── pdf
      │       └── txt
      └── merge_txt_to_pdf/
          ├── input
          └── output
  ```
* To merge txt and generate transcripts:
 ``` 
 python merge_pdf_to_txt.py 
 ```
* To generate uuid_mappings.csv:
 ``` 
 python uuid.mapper.py 
 ```
* To begin upload and edit process:
 ``` 
 python file_uploader.py 
 ```
* To edit spreadsheet:
 ``` 
 python spreadsheet_editor.py 
 ```

<!-- LICENSE -->
## License

Distributed under the Unlicense License. See `LICENSE.txt` for more information.

