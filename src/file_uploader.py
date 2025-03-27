from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common import TimeoutException
from selenium import webdriver
from datetime import datetime
from pathlib import Path
import pandas as pd
import configparser
import logging
import glob
import time
import re
import os


class DigitalLibraryUploader:

    def __init__(self, headless=False):
        config = configparser.ConfigParser()
        config.read('../docs/config.ini')
        self.driver = self._init_driver(headless)
        self.wait = WebDriverWait(self.driver, 20)
        self.base_url = config['Credentials']['base_url']
        self.collection_href = config['Credentials']['collection_href']

    def _init_driver(self, headless):
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])

        # Use Service object for ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(
            service=service,
            options=options
        )

    def _extract_base_identifier(self, filename):
        match = re.search(r'(mvp_[\d\.]+_\d+)', filename)
        if not match:
            raise ValueError(f"Invalid filename format: {filename}")
        base_id = match.group(1)
        print(f"ℹ️ Extracted base identifier: {base_id}")  # Debug print
        return base_id

    def _take_screenshot(self, name):
        path = os.path.abspath(f"screenshots/error_screenshot_{name}_{int(time.time())}.png")
        self.driver.save_screenshot(path)
        print(f"⚠️ Screenshot saved: file://{path}")

        # Manage the number of screenshots
        files = glob.glob(os.path.join("../screenshots", "error_screenshot_*.png"))
        file_times = []
        for file in files:
            filename = os.path.basename(file)
            parts = filename.split('_')
            if len(parts) < 3:
                continue  # Invalid filename format
            timestamp_part = parts[-1].split('.')[0]
            if not timestamp_part.isdigit():
                continue  # Invalid timestamp
            timestamp = int(timestamp_part)
            file_times.append((file, timestamp))

        # Sort files by timestamp (oldest first)
        file_times.sort(key=lambda x: x[1])

        # Delete oldest files if more than max_num
        max_num = 50
        if len(file_times) > max_num:
            num_to_delete = len(file_times) - max_num
            files_to_delete = [file for file, _ in file_times[:num_to_delete]]
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    print(f"Deleted old screenshot: {file_path}")
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")

    def login(self, username, password):
        print("🔑 Navigating to login page...")
        try:
            self.driver.get(f"{self.base_url}/user/login")
            self.wait.until(EC.presence_of_element_located((By.ID, "edit-name"))).send_keys(username)
            self.driver.find_element(By.ID, "edit-pass").send_keys(password)
            self.driver.find_element(By.ID, "edit-submit").click()
            WebDriverWait(self.driver, 1).until(
                (EC.url_contains("check_logged_in=1")))
            print("✅ Login successful")
        except TimeoutException as e:
            self._take_screenshot("login_failure")
            raise RuntimeError(f"Login failed: {str(e)} please make sure your username and password in config.ini are correct.")


    def _get_uuid_mapping(self):
        """Load UUID to identifier mapping from CSV"""
        mapping_file = Path("../docs/uuid_mapping.csv")
        if not mapping_file.exists():
            raise FileNotFoundError("UUID mapping file not found")

        df = pd.read_csv(mapping_file)
        return dict(zip(df['BaseIdentifier'], df['UUID']))

    def _navigate_to_record(self, identifier):
        """Direct navigation using UUID mapping"""
        base_id = self._extract_base_identifier(identifier)
        uuid_mapping = self._get_uuid_mapping()

        try:
            item_uuid = uuid_mapping[base_id]
            direct_url = f"{self.base_url}{self.collection_href}{item_uuid}"
            self.driver.get(direct_url)

            # Verify we're on the correct page
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, f"//div[contains(text(), '{base_id}')]"))
            )
            print(f"✅ Directly accessed {base_id}")
            return

        except KeyError:
            raise RuntimeError(f"No UUID mapping found for {base_id}")
        except Exception as e:
            self._take_screenshot("direct_access_error")
            raise RuntimeError(f"Failed direct navigation: {str(e)}")



    def _upload_media_file(self, file_path, media_type, media_url):
        """Optimized media file_uploader with direct URL handling"""
        try:
            print(f"🔄 Navigating to media creation page for {media_type}")
            self.driver.get(f"{media_url}/add")

            # Wait for media type selection
            WebDriverWait(self.driver, 1).until(
                EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'Add media')]"))
            )

            # Select media type
            media_choice = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, f"//span[@class='label' and contains(text(), '{media_type}')]")
            ))
            media_choice.click()
            print(f"📁 File {file_path.name} selected")
            print(f"Current page title: {self.driver.title}")
            print(f"Current URL: {self.driver.current_url}")
            self._take_screenshot("pre_upload_state")
            # File file_uploader handling
            file_input = self.wait.until(EC.presence_of_element_located(
                (By.XPATH, "//input[@type='file']")
            ))
            file_input.send_keys(str(file_path))

            # 6. Handle save button with multiple fallbacks
            save_button_xpaths = [
                "//input[@data-drupal-selector='edit-submit' and @value='Save']",
                "//input[@id='edit-submit' and @name='op']",
                "//input[contains(@class, 'button--primary') and @value='Save']",
                "//*[@id='edit-submit']"
            ]

            save_button = None
            for xpath in save_button_xpaths:
                try:
                    save_button = self.wait.until(EC.element_to_be_clickable(
                        (By.XPATH, xpath)
                    ))
                    break
                except TimeoutException:
                    continue

            if not save_button:
                raise RuntimeError("Could not find save button with any selector")

            # 7. Enhanced error handling during save
            error_detected = False
            for attempt in range(3):
                try:
                    self.driver.execute_script("arguments[0].click();", save_button)

                    # Check for "File locked" error immediately after click
                    error_xpath = """
                                     //div[@role='contentinfo' and contains(@class, 'messages--error')]
                                     //div[contains(text(), 'File already locked for writing')]
                                 """
                    try:
                        WebDriverWait(self.driver, 1).until(  # Timeout set to 1 second
                            EC.presence_of_element_located((By.XPATH, error_xpath))
                        )
                        print("⚠️ File lock error detected, refreshing...")
                        self.driver.refresh()
                        error_detected = True
                        break  # Exit retry loop to handle refresh
                    except TimeoutException:
                        pass  # No error found, continue

                    # Original success check
                    self.wait.until(lambda d: "media" in d.current_url)
                    error_detected = False
                    break  # If no error detected, exit the loop

                except Exception as e:
                    print(f"❌ Error on attempt {attempt + 1}: {str(e)}")
                    if attempt == 2:  # After 3 attempts, raise the error
                        raise e


            if error_detected:
                print("🔄 Retrying after error refresh...")
                return self._upload_media_file(file_path, media_type)
            self.driver.refresh()
            self.wait.until(EC.url_matches(f"{self.base_url}/admin/content/media"))
            print("✅ Media saved successfully")
            return

        except Exception as e:
            self._take_screenshot("metadata_update_error")
            raise RuntimeError(f"Metadata update failed: {str(e)}")

    def get_file_urls(self):
        """Get URLs for both PDF and TXT files from item media page"""
        try:
            # Ensure we're on the item's media page
            if not self.driver.current_url.endswith("/media"):
                raise RuntimeError("Not on item media page")

            print("🔗 Collecting file URLs from media page...")
            urls = {
                'pdf': None,
                'txt': None
            }

            # Find all media links with type indicators
            media_links = self.wait.until(EC.presence_of_all_elements_located(
                (By.XPATH, "//a[contains(@href, '/media/')]")
            ))

            # Map URL paths to our types
            type_mapping = {
                'document': 'pdf',
                'extracted-text': 'txt'
            }

            for link in media_links:
                href = link.get_attribute('href')
                for path_segment, file_type in type_mapping.items():
                    if f'/media/{path_segment}/' in href and not urls[file_type]:
                        urls[file_type] = href
                        print(f"  ✅ Found {file_type.upper()} URL: {href}")

            # Validate we found both
            if not all(urls.values()):
                missing = [k.upper() for k,v in urls.items() if not v]
                raise RuntimeError(f"Missing file URLs: {', '.join(missing)}")

            return urls

        except Exception as e:
            self._take_screenshot("get_file_urls_error")
            raise RuntimeError(f"Failed to get file URLs: {str(e)}")


    def _fill_url_fields(self, pdf_url, txt_url):
        """Fill both URL fields with proper field addition handling"""
        try:
            print("📝Filling PDF metadata!")
            # First field (PDF)
            self._fill_single_url_field(pdf_url, "PDF Transcript", 0)
            print("✅PDF metadata filled successfully!")
            save_button = self.wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'input#edit-submit')
            ))
            current_url = self.driver.current_url
            print(current_url)
            save_button.click()
            self.driver.get(current_url)

            print("📝Filling TXT metadata!")
            # Now fill second field (TXT)
            self._fill_single_url_field(txt_url, "TXT Transcript", 1)
            save_button = self.wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'input#edit-submit')
            ))
            save_button.click()
            print("✅TXT metadata filled successfully!")

        except Exception as e:
            self._take_screenshot("url_field_fill_error")
            raise RuntimeError(f"Failed to fill URL fields: {str(e)}")

    def _fill_single_url_field(self, url, title, index):
        """Fill individual URL and title fields"""
        try:
            # URI field with dynamic ID

            uri_input_id = f"edit-field-transcript-file-s-{index}-uri"
            uri_field = self.wait.until(EC.element_to_be_clickable((By.ID, uri_input_id)))
            uri_field.clear()
            uri_field.send_keys(url)


            # Title field with dynamic ID

            title_input_id = f"edit-field-transcript-file-s-{index}-title"
            title_field = self.driver.find_element(By.ID, title_input_id)
            title_field.clear()
            title_field.send_keys(title)

        except Exception as e:
            self._take_screenshot(f"url_field_fill_error_{index}")
            raise RuntimeError(f"Failed to fill URL field {index}: {str(e)}")

    def _add_another_item(self):
        """Click the 'Add another item' button and wait for new fields"""
        try:
            # Find the table containing transcript files
            transcript_table = self.wait.until(EC.presence_of_element_located(
                (By.XPATH, "//table[contains(@id, 'field-transcript-file-s-values')]")
            ))

            # Find the 'Add another item' button
            add_button = self.wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'input[name="field_transcript_file_s__add_more"]')
            ))

            # Scroll to and click the add button
            self.driver.execute_script("arguments[0].scrollIntoView(true);", add_button)
            add_button.click()


            print("➕ Added new URL field set")

        except Exception as e:
            self._take_screenshot("add_item_failure")
            raise RuntimeError(f"Failed to add new URL field set: {str(e)}")

    def _update_metadata(self, pdf_url, txt_url):
        """Update parent record with both file URLs"""
        try:
            print("📝 Updating metadata...")
            current_url = self.driver.current_url
            edit_url = current_url.replace("/media", "/edit")
            self.driver.get(edit_url)
            # Fill both URL fields
            self._fill_url_fields(pdf_url, txt_url)


            self.wait.until(EC.url_contains("/collections/"))
            print("✅ Metadata updated successfully")
            return

        except Exception as e:
            self._take_screenshot("metadata_update_error")
            raise RuntimeError(f"Metadata update failed: {str(e)}")

    def upload_transcript(self, identifier, pdf_path, txt_path):
        """Optimized file_uploader process with direct access"""
        try:
            # Direct navigation using UUID mapping
            self._navigate_to_record(identifier)

            # Navigate to media page through proper menu
            media_url = self._access_media_page()

            # Process PDF
            if not self._check_file_exists("Document", media_url):
                print(f"📤 Starting PDF file_uploader process for {pdf_path}")
                self._upload_media_file(pdf_path, "Document", media_url)
                self.driver.get(media_url)  # Refresh media page

            # Process TXT
            if not self._check_file_exists("Extracted Text", media_url):
                print(f"📤 Starting TXT file_uploader process for {txt_path}")
                self._upload_media_file(txt_path, "Extracted Text", media_url)
                self.driver.get(media_url)  # Refresh media page

            # Get URLs and update metadata
            urls = self.get_file_urls()
            print(f"🔗 Obtained URLs: PDF={urls['pdf']}, TXT={urls['txt']}")
            self._update_metadata(urls['pdf'], urls['txt'])
            return

        except Exception as e:
            self._take_screenshot("upload_process_error")
            raise

    def _access_media_page(self):
        """Reliable media page navigation"""
        try:
            # Use the admin toolbar for consistent access
            admin_menu = self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div.toolbar-tab a[href='/admin']")
            ))
            self.driver.execute_script("arguments[0].click();", admin_menu)

            media_link = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(@href, '/media') and contains(text(), 'Media')]")
            ))
            media_url = media_link.get_attribute("href")
            media_link.click()

            self.wait.until(EC.url_contains("/media"))
            return self.driver.current_url

        except Exception as e:
            self._take_screenshot("media_access_error")
            raise RuntimeError(f"Failed to access media page: {str(e)}")

    def _check_file_exists(self, media_type, media_url):
        """Check for existing files without page reload"""
        try:
            self.driver.get(media_url)
            type_mapping = {
                "Document": "document",
                "Extracted Text": "extracted-text"
            }
            path_segment = type_mapping[media_type]

            return bool(self.driver.find_elements(
                By.XPATH, f"//a[contains(@href, '/media/{path_segment}/')]"
            ))
        except Exception:
            return False


    def close(self):
        self.driver.quit()
        print("🛑 Browser closed")



def process_uploads():
    """
    Optimized batch processor with robust error handling and logging
    """
    # Configure logging
    required_files = [
        "../docs/uuid_mapping.csv",
        "../docs/upload_progress.csv",
        "../docs/config.ini",
        "../files/file_uploader/input/pdf",
        "../files/file_uploader/input/txt"

    ]

    # Check required files
    missing_files = [file for file in required_files if not Path(file).exists()]

    if missing_files:
        for file in missing_files:
            logging.critical(f"Critical file/directory missing: {file}")
        raise FileNotFoundError(f"Critical files missing: {', '.join(missing_files)}")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s: %(message)s',
        filename='../docs/upload_log.txt'
    )
    uploader = DigitalLibraryUploader(headless=False)
    config = configparser.ConfigParser()
    config.read('../docs/config.ini')
    account = config['Credentials']['account']
    password = config['Credentials']['password']
    try:
        uploader.login(account, password)

        # Configuration
        config = {
            'base_dir': Path("../"),
            'source_pdf': "files/file_uploader/input/pdf",
            'source_txt': "files/file_uploader/input/txt",
            'processed_dir': "files/file_uploader/output",
            'max_retries': 3
        }

        # Initialize progress tracker
        progress = ProgressTracker(config)

        # Flag to track if any files were processed
        batches = list(progress.get_upload_batches(chunk_size=10))
        # Get batch of files to process
        for batch in batches:
            print(f"🚀 Processing batch of {len(batch)} files")

            for (base_name, pdf_path, txt_path) in batch:
                print(base_name, pdf_path, txt_path)
                for attempt in range(config['max_retries']):
                    try:
                        uploader.upload_transcript(base_name, pdf_path, txt_path)
                        progress.mark_completed(base_name, pdf_path, txt_path)
                        break
                    except Exception as retry_error:
                        logging.warning(f"Attempt {attempt+1} failed for {base_name}: {str(retry_error)}")

                        if attempt == config['max_retries'] - 1:
                            progress.mark_failed(base_name, str(retry_error))
                            logging.error(f"Final attempt failed for {base_name}: {str(retry_error)}")

        progress.generate_report()

    except Exception as e:
        logging.critical(f"Unexpected error during file_uploader: {str(e)}")
        raise

    finally:
        uploader.close()
        print("🏁 Processing complete")

class ProgressTracker:
    """Enhanced progress tracking with batch processing"""
    def __init__(self, config):
        self.config = config
        self.progress_file = self.config['base_dir'] / "docs/upload_progress.csv"
        self._init_storage()

    def _init_storage(self):
        """Initialize file structure and progress tracking"""
        # Create processed directories
        self.validate_csv_structure()

        (self.config['base_dir'] / self.config['processed_dir']).mkdir(parents=True, exist_ok=True)

        # Initialize CSV with proper columns
        required_columns = [
            'BaseIdentifier', 'PDF', 'TXT', 'Metadata',
            'Timestamp', 'Attempts', 'LastError'
        ]

        if not self.progress_file.exists():
            pd.DataFrame(columns=required_columns).to_csv(self.progress_file, index=False)
        else:
            # Ensure existing CSV has all required columns
            df = pd.read_csv(self.progress_file)
            for col in required_columns:
                if col not in df.columns:
                    df[col] = pd.NA
            df.to_csv(self.progress_file, index=False)

    def get_upload_batches(self, chunk_size=10):
        """Yields batches of files needing processing"""
        # Resolve full source paths
        source_pdf_dir = self.config['base_dir'] / self.config['source_pdf']
        source_txt_dir = self.config['base_dir'] / self.config['source_txt']


        # Get all PDF files with case-insensitive search
        pdf_files = list(source_pdf_dir.glob("*.pdf"))

        # Load progress data
        try:
            df = pd.read_csv(self.progress_file) if self.progress_file.exists() else pd.DataFrame()
        except pd.errors.EmptyDataError:
            df = pd.DataFrame()

        current_batch = []
        completed_files = set(df[df['Metadata'] == 'Yes']['BaseIdentifier'])

        for pdf_path in pdf_files:
            base_name = self._clean_base_name(pdf_path.stem)

            # Skip completely if already completed
            if base_name in completed_files:
                print(f"⏩ Skipping completed file: {base_name}")
                continue

            txt_filename = f"{base_name}_transcript.txt"
            txt_path = source_txt_dir / txt_filename

            # Skip if TXT file doesn't exist
            if not txt_path.exists():
                print(f"❌ TXT file not found for {base_name}: {txt_path}")
                continue

            current_batch.append((base_name, pdf_path, txt_path))

            if len(current_batch) >= chunk_size:
                yield current_batch
                current_batch = []

        if current_batch:  # Yield remaining files
            yield current_batch

        # If no files to process, print a message
        if not pdf_files or len(pdf_files) == len(completed_files):
            print("✅ All files have been processed.")

    def _clean_base_name(self, stem):
        """Normalize base filename"""
        return stem.replace('_transcript', '').replace('_TRANSCRIPT', '').strip()

    def _get_file_status(self, df, base_name):
        """Get processing status from dataframe"""
        if df.empty:
            return 'new'

        record = df[df['BaseIdentifier'] == base_name]
        if record.empty:
            return 'new'

        if record['Metadata'].values[0] == 'Yes':
            return 'completed'

        return 'failed'
    def mark_completed(self, base_name, pdf_path, txt_path):
        """Update progress for successful file_uploader"""
        try:
            # Move files first
            processed_dir = self.config['base_dir'] / self.config['processed_dir']
            processed_dir.mkdir(parents=True, exist_ok=True)

            pdf_dest = processed_dir / "pdf" / pdf_path.name
            txt_dest = processed_dir / "txt" / txt_path.name
            pdf_dest.parent.mkdir(parents=True, exist_ok=True)
            txt_dest.parent.mkdir(parents=True, exist_ok=True)

            pdf_path.rename(pdf_dest)
            txt_path.rename(txt_dest)

            # Update CSV
            timestamp = datetime.now().isoformat()
            new_data = {
                'BaseIdentifier': base_name,
                'PDF': 'Yes',
                'TXT': 'Yes',
                'Metadata': 'Yes',
                'Timestamp': timestamp,
                'Attempts': 1,
                'LastError': ''
            }

            # Read or create DF
            if self.progress_file.exists():
                df = pd.read_csv(self.progress_file)
            else:
                df = pd.DataFrame(columns=new_data.keys())
                print("DF creation error")
            # Remove existing entry if present
            df = df[df['BaseIdentifier'] != base_name]

            # Add new entry
            df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
            df.to_csv(self.progress_file, index=False)

            print(f"✅ Marked {base_name} as completed")
            return True
        except Exception as e:
            print(f"❌ Failed to mark {base_name} as completed: {str(e)}")
            if 'BaseIdentifier' in str(e):
                print("⚠️ Check CSV column headers match: BaseIdentifier, PDF, TXT, Metadata, Timestamp, Attempts, LastError")

    def validate_csv_structure(self):
        """Ensure CSV has correct columns"""
        required_columns = [
            'BaseIdentifier', 'PDF', 'TXT', 'Metadata',
            'Timestamp', 'Attempts', 'LastError'
        ]

        if self.progress_file.exists():
            df = pd.read_csv(self.progress_file)
            if not all(col in df.columns for col in required_columns):
                print("⚠️ Fixing CSV structure...")
                for col in required_columns:
                    if col not in df.columns:
                        df[col] = pd.NA
                df.to_csv(self.progress_file, index=False)
    def generate_report(self):
        """Generate summary report of file_uploader operations"""
        try:
            if not self.progress_file.exists():
                print("ℹ️ No progress data available for reporting")
                return

            df = pd.read_csv(self.progress_file)
            if df.empty:
                print("📊 Report: No files processed yet")
                return

            # Calculate metrics
            total = len(df)
            completed = df[df['Metadata'] == 'Yes'].shape[0]
            failed = total - completed
            success_rate = (completed / total) * 100 if total > 0 else 0

            # Generate report content
            report = [
                "\n=== UPLOAD PROCESSING REPORT ===",
                f"Total files processed: {total}",
                f"Successfully completed: {completed}",
                f"Failed uploads: {failed}",
                f"Success rate: {success_rate:.2f}%",
                "\nFailed items:"
            ]

            # Add failed item details
            failed_items = df[df['Metadata'] != 'Yes']
            if not failed_items.empty:
                for _, row in failed_items.iterrows():
                    report.append(
                        f"- {row['BaseIdentifier']}: "
                        f"Attempts {row['Attempts']}, "
                        f"Last error: {row['LastError']}"
                    )
            else:
                report.append("None")

            # Print to console
            print("\n".join(report))

            # Save to file
            report_path = self.config['base_dir'] / "docs/upload_report.txt"
            with open(report_path, 'w') as f:
                f.write("\n".join(report))
            print(f"\n📄 Full report saved to: {report_path}")

        except Exception as e:
            print(f"❌ Failed to generate report: {str(e)}")

    def mark_failed(self, base_name, error_message=""):
        """Update progress for failed file_uploader"""
        try:
            df = pd.read_csv(self.progress_file) if self.progress_file.exists() else pd.DataFrame()

            # Update existing record or create new
            if base_name in df['BaseIdentifier'].values:
                df.loc[df['BaseIdentifier'] == base_name, 'Attempts'] += 1
                df.loc[df['BaseIdentifier'] == base_name, 'LastError'] = str(error_message)[:500]  # Truncate long errors
            else:
                new_entry = pd.DataFrame([{
                    'BaseIdentifier': base_name,
                    'PDF': 'No',
                    'TXT': 'No',
                    'Metadata': 'No',
                    'Timestamp': datetime.now().isoformat(),
                    'Attempts': 1,
                    'LastError': str(error_message)[:500]
                }])
                df = pd.concat([df, new_entry], ignore_index=True)

            df.to_csv(self.progress_file, index=False)
            print(f"⚠️ Marked {base_name} as failed")

        except Exception as e:
            print(f"❌ Failed to record failure for {base_name}: {str(e)}")

if __name__ == "__main__":
    print("=== STARTING UPLOAD PROCESS ===")
    process_uploads()
    print("=== PROCESS COMPLETED ===")