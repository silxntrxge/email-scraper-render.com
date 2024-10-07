#tompithsatom/qifshamotrenemail:0.1.0 - works perfectly
#still stable 0.1.1
import sys
import os
import json
import time
import re
import requests
from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from functools import wraps
import threading
import validators
import random
from urllib.parse import unquote
from collections import Counter

app = Flask(__name__)

def get_emails(text, driver):
    # More comprehensive regex pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b'
    potential_emails = re.findall(email_pattern, text)
    
    # Search for emails in href attributes
    links = driver.find_elements_by_xpath("//a[contains(@href, 'mailto:')]")
    for link in links:
        href = link.get_attribute('href')
        if href.startswith('mailto:'):
            potential_emails.append(unquote(href[7:]))  # Remove 'mailto:' and decode
    
    # Additional validation and filtering
    valid_emails = []
    for email in potential_emails:
        if validators.email(email):
            # Check if it's a Gmail address (modify if you want to include other domains)
            if email.lower().endswith('@gmail.com'):
                valid_emails.append(email.lower())  # Convert to lowercase for consistency
    
    return list(set(valid_emails))  # Remove duplicates

def save_emails(emails, output_file='emails.txt'):
    print(f"Saving {len(emails)} emails to {output_file}...")
    try:
        with open(output_file, 'w') as f:
            for email in emails:
                f.write(email + '\n')
        print("Emails saved successfully.")
    except Exception as e:
        print(f"Error saving emails: {e}")

def send_to_webhook(emails, webhook_url, record_id):
    print(f"Sending {len(emails)} emails to webhook: {webhook_url}")
    try:
        # Remove any potential duplicates and sort the emails
        unique_emails = sorted(set(emails))
        
        # Format the emails as a single comma-separated string
        formatted_emails = ', '.join(unique_emails)
        
        payload = {
            'emails': formatted_emails,
            'recordId': record_id
        }
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        print("Emails and recordId sent to webhook successfully.")
    except Exception as e:
        print(f"Error sending data to webhook: {e}")

def initialize_driver():
    print("Initializing Selenium WebDriver...")
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.binary_location = "/usr/bin/google-chrome-stable"
        
        driver = webdriver.Chrome(options=chrome_options)
        print("WebDriver initialized successfully.")
        return driver
    except Exception as e:
        print(f"Error initializing WebDriver: {e}")
        sys.exit(1)

def generate_urls(names, domain, niches, num_pages=5):
    print("Generating URLs...")
    urls = []
    for name in names:
        for niche in niches:
            for page in range(1, num_pages + 1):
                url = f"https://www.google.com/search?q=%22{name}%22+%22{domain}%22+%22{niche}%22&start={page}"
                urls.append(url)
    print(f"Generated {len(urls)} URLs.")
    return urls

def scrape_emails_from_url(driver, url, email_counter):
    print(f"Scraping emails from URL: {url}")
    driver.get(url)
    
    # Add a small random delay after loading the page
    time.sleep(random.uniform(1, 3))  # Random delay between 1 and 3 seconds
    
    page_source = driver.page_source
    emails = get_emails(page_source, driver)
    
    # Update the counter with new emails
    for email in emails:
        email_counter[email] += 1
    
    unique_emails = set(emails)
    print(f"Found {len(unique_emails)} unique emails on this page.")
    return unique_emails

def scrape_emails(names, domain, niches, webhook_url=None, record_id=None):
    print("Starting the scraper...")
    driver = initialize_driver()
    
    all_emails = set()
    email_counter = Counter()
    
    total_combinations = len(names) * len(niches)
    completed_combinations = 0
    
    for name in names:
        for niche in niches:
            urls = generate_urls([name], domain, [niche])
            consecutive_zero_count = 0
            max_consecutive_zero = 5  # Threshold for consecutive zero results
            waited_once = False

            for url in urls:
                try:
                    emails = scrape_emails_from_url(driver, url, email_counter)
                    if not emails:
                        consecutive_zero_count += 1
                        print(f"No emails found. Consecutive zero count: {consecutive_zero_count}")
                        if consecutive_zero_count >= max_consecutive_zero:
                            if not waited_once:
                                print("Reached maximum consecutive zero results. Waiting for 2 minutes...")
                                time.sleep(120)  # Wait for 2 minutes (120 seconds)
                                waited_once = True
                                consecutive_zero_count = 0  # Reset the counter after waiting
                            else:
                                print(f"Still no results after waiting. Moving to next word combination.")
                                break  # Exit the inner loop and move to the next word combination
                    else:
                        all_emails.update(emails)
                        consecutive_zero_count = 0  # Reset the counter when emails are found
                        waited_once = False  # Reset the wait flag when emails are found
                    
                    # Implement rate limiting
                    delay = random.uniform(3, 7)  # Random delay between 3 and 7 seconds
                    print(f"Waiting for {delay:.2f} seconds before the next request...")
                    time.sleep(delay)
                except Exception as e:
                    print(f"Error scraping URL {url}: {e}")
            
            completed_combinations += 1
            progress = (completed_combinations / total_combinations) * 100
            if progress % 20 < (1 / total_combinations) * 100:  # Check if we've crossed a 20% threshold
                print(f"Search progress: {progress:.2f}% completed")
    
    driver.quit()
    print("WebDriver closed.")
    
    email_list = list(all_emails)
    save_emails(email_list)
    
    if webhook_url:
        send_to_webhook(email_list, webhook_url, record_id)
    
    print(f"Scraper finished successfully. Total unique emails collected: {len(email_list)}")
    print("Email frequency:")
    for email, count in email_counter.most_common():
        print(f"{email}: {count} times")
    
    return email_list

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key and api_key == os.environ.get('GOOGLE_API_KEY'):
            return f(*args, **kwargs)
        return jsonify({"error": "Unauthorized"}), 401
    return decorated

def background_scrape(names_list, domain, niches_list, webhook_url, record_id):
    emails = scrape_emails(names_list, domain, niches_list, webhook_url, record_id)
    print(f"Background scraping completed. Emails found: {len(emails)}")

@app.route('/scrape', methods=['POST'])
@require_api_key
def scrape():
    data = request.json
    names = data.get('names', '')
    domain = data.get('domain', '')
    niches = data.get('niche', '')
    webhook_url = data.get('webhook', '')
    record_id = data.get('recordId', '')

    names_list = [name.strip() for name in names.split(',') if name.strip()]
    niches_list = [niche.strip() for niche in niches.split(',') if niche.strip()]

    # Start the scraping process in a background thread
    thread = threading.Thread(target=background_scrape, args=(names_list, domain, niches_list, webhook_url, record_id))
    thread.start()
    
    return jsonify({'message': 'Scraping started, will be send to:', 'recordId': record_id}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))