from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from file_uploader import DigitalLibraryUploader
from selenium.webdriver.common.by import By
import configparser
import csv
import re



class UUIDMapper:
    def __init__(self):
        config = configparser.ConfigParser()
        config.read('../docs/config.ini')
        self.driver = DigitalLibraryUploader(headless=True).driver
        self.base_url = config['Credentials']['base_url']
        self.collection_url = config['Credentials']['collection_url']
        self.output_file = "../docs/uuid_mapping.csv"
        self.fieldnames = ['OriginalIdentifier', 'BaseIdentifier', 'UUID']

    def _get_uuid_from_url(self, url):
        """Extract UUID from item URL"""
        return url.split('/')[-1]

    def _extract_identifier(self):
        """Extract both original and base identifier from item page"""
        try:
            element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[@property='dcterms:identifier']"))
            )
            full_identifier = element.text.strip()

            # Extract base identifier (mvp_x.x_xxx format)
            base_identifier = None

            match = re.search(r'(mvp_[\d\.]+_\d+)', full_identifier)
            if match:
                base_identifier = match.group(1)

            return {
                'original': full_identifier,
                'base': base_identifier
            }
        except Exception as e:
            print(f"Identifier not found: {str(e)}")
            return {'original': 'unknown', 'base': 'unknown'}

    def _process_page(self, writer):
        """Process all items on a single page with error handling"""
        try:
            # Get fresh list of items each time
            view_buttons = WebDriverWait(self.driver, 20).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.btn.ghost[rel='bookmark']"))
            )

            print(f"Found {len(view_buttons)} items on this page")

            for idx in range(len(view_buttons)):
                try:
                    # Re-find buttons to avoid staleness
                    current_buttons = self.driver.find_elements(By.CSS_SELECTOR, "a.btn.ghost[rel='bookmark']")
                    button = current_buttons[idx]

                    item_url = button.get_attribute('href')
                    uuid = self._get_uuid_from_url(item_url)

                    # Open in new tab to maintain page state
                    self.driver.execute_script("window.open(arguments[0]);", item_url)
                    self.driver.switch_to.window(self.driver.window_handles[1])

                    # Extract identifiers
                    identifier_data = self._extract_identifier()

                    # Write to CSV
                    writer.writerow({
                        'OriginalIdentifier': identifier_data['original'],
                        'BaseIdentifier': identifier_data['base'],
                        'UUID': uuid
                    })
                    print(f"Processed {idx+1}/{len(view_buttons)}: {identifier_data['base']}")

                    # Close tab and return to main window
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])

                except Exception as e:
                    print(f"Error processing item {idx+1}: {str(e)}")
                    # Reset to collection page
                    self.driver.get(self.collection_url)

        except Exception as page_error:
            print(f"Page processing error: {str(page_error)}")

    def map_uuids(self):
        """Main mapping function with proper CSV setup"""
        with open(self.output_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
            writer.writeheader()

            self.driver.get(self.collection_url)
            page_num = 0

            while True:
                print(f"\nProcessing page {page_num + 1}")
                self._process_page(writer)

                # Pagination with retries
                try:
                    next_btn = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "li.pager__item--next a")))
                    next_btn.click()

                    # Wait for page load using URL update
                    page_num += 1
                    WebDriverWait(self.driver, 10).until(
                        EC.url_contains(f"page={page_num}"))

                    # Wait for items to load
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "a.btn.ghost[rel='bookmark']"))
                    )
                except Exception as e:
                    print("No more pages found")
                    break

        print(f"Mapping complete. Saved to {self.output_file}")
        self.driver.quit()

if __name__ == "__main__":
    mapper = UUIDMapper()
    mapper.map_uuids()