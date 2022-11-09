import argparse
import csv
import datetime
import glob
import os
import time
import sys

import dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
# from webdriver_manager.chrome import ChromeDriverManager



# This is for load all env file
def load_env():
    global dotenv_file
    dotenv_file = dotenv.find_dotenv()
    dotenv.load_dotenv(dotenv_file)


def parse_args():
    global FROM_DATE, TO_DATE
    parser = argparse.ArgumentParser(
        description="A script to web scrape HDFC Netbanking Transactions and add them to Google Sheets")
    parser.add_argument('-f', '--from-date', help='transactions will be fetched from this date, format= dd/mm/YYYY')
    parser.add_argument('-t', '--to-date', help='transactions will be fetched to this date, format=dd/mm/YYYY')
    args = parser.parse_args()
    FROM_DATE = args.from_date
    TO_DATE = args.to_date

    if FROM_DATE is None:
        FROM_DATE = os.getenv('LAST_RUN')
    if TO_DATE is None:
        TO_DATE = datetime.datetime.today().strftime('%d/%m/%Y')
    return FROM_DATE, TO_DATE


def init_webdriver():
    global driver
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920x1080")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--verbose')
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": os.getenv('DOWNLOAD_DEFAULT_DIRECTORY'),
        "download.prompt_for_download": False
    })
    # return webdriver.Chrome(service=ChromeService(executable_path=os.getenv('WEBDRIVER_PATH')),
    #                         options=chrome_options)
    return webdriver.Chrome(executable_path=os.getenv('WEBDRIVER_PATH'))




def navigate_to_login_page():
    driver.get("https://netbanking.hdfcbank.com/netbanking/")
    driver.implicitly_wait(0.5)


def login():
    driver.switch_to.frame("login_page")
    customer_id = driver.find_element(by=By.NAME, value='fldLoginUserId')
    CUSTOMER_ID = os.getenv('CUSTOMER_ID')
    customer_id.send_keys(CUSTOMER_ID)
    continue_btn = driver.find_element(by=By.XPATH,
                                       value='/html/body/div[1]/form/div[3]/div/div/div[2]/div[2]/div[2]/div[2]/a')
                                    #    //*[@id="pageBody"]
    continue_btn.click()
    password = driver.find_element(by=By.NAME, value='fldPassword')
    PASSWORD = os.getenv('PASSWORD')
    password.send_keys(PASSWORD)
    verify_secure_access_btn=driver.find_element(by=By.NAME, value='chkrsastu')
    verify_secure_access_btn.click()


    login_btn = driver.find_element(by=By.XPATH,
                                    value='/html/body/form/div/div[3]/div/div[1]/div[2]/div[1]/div[4]/div[2]/a')
    login_btn.click()


# SELECT A/c Statement Current & Previous month from Enquire tab. 
def get_current_month_account_statement():
    driver.implicitly_wait(0.5)
    driver.switch_to.frame("left_menu")
    enquire_btn = driver.find_element(by=By.XPATH, value='//*[@id="enquiryatag"]')
    enquire_btn.click()
    ac_statement_current_month = driver.find_element(by=By.XPATH, value='//*[@id="SIN_nohref"]/a')
    ac_statement_current_month.click()
    driver.switch_to.default_content()
    driver.switch_to.frame("main_part")
    account_type = driver.find_element(by=By.XPATH, value='/html/body/form/table[1]/tbody/tr[1]/td[2]/select/option[2]')
    account_type.click()
    account_number = driver.find_element(by=By.XPATH, value='//*[@id="first"]/td[2]/select/option[2]')
    account_number.click()
    select_period = driver.find_element(by=By.XPATH, value='//*[@id="hideradio"]/span')
    select_period.click()
    from_date = driver.find_element(by=By.XPATH, value='//*[@id="frmDatePicker"]')
    from_date.send_keys(FROM_DATE)
    to_date = driver.find_element(by=By.XPATH, value='//*[@id="toDatePicker"]')
    to_date.send_keys(TO_DATE)
    per_page_transactions = driver.find_element(by=By.XPATH,
                                                value='/html/body/form/table[1]/tbody/tr[6]/td[2]/div[3]/select/option[4]')
    per_page_transactions.click()
    view_btn = driver.find_element(by=By.XPATH, value='/html/body/form/table[1]/tbody/tr[7]/td/a')
    view_btn.click()


def download_file():
    delimited_file_format = None
    try:
        delimited_file_format = driver.find_element(by=By.CSS_SELECTOR,
                                                    value='body > form > table.formtable > tbody > tr:nth-child(1) > '
                                                          'td:nth-child(2) > select > option:nth-child(3)')
    except NoSuchElementException as err:
        print('No transactions found')
        exit(0)

    delimited_file_format.click()
    download_btn = driver.find_element(by=By.CSS_SELECTOR,
                                       value='body > form > table.formtable > tbody > tr:nth-child(2) > td > a')
    download_btn.click()


def parse_transactions():
    file_transactions = []
    path = os.getenv('TRANSACTIONS_FILE_PATH')
    for filename in glob.glob(os.path.join(path, '*.txt')):
        with open(os.path.join(os.getcwd(), filename), 'r') as csv_file:  # open in readonly mode
            temp=["Date","Title","Debit amount","Credit amount","Transaction ID","Closing Balance"]
            file_transactions.append(temp)
            try:
                reader = csv.reader(csv_file)
                next(reader)  # skip empty row
                # next(reader)  # skip header row
                
                print("***********************************")
                print(reader)
                for row in reader:
                    """
                    Custom parsing of transactions according to desired format.
                    """
                    transaction = [row[0],row[1],row[3],row[4],row[5],row[6]]
                    file_transactions.append(transaction)
                    # print("++++")
                    # print(transaction)
                if len(file_transactions) == 0:
                    print('No transactions found')
                    exit(0)
            except Exception as e:
                print("---")
                print(e)
    return file_transactions


def update_sheet(parsed_transactions):
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    # The ID and range of a sample spreadsheet.
    SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
    READ_RANGE_NAME = f'A6:A{int(os.getenv("MAX_ROWS"))}'
    CREDENTIAL_FILE=os.getenv('CREDENTIAL_PATH')
    creds = None
    """
     The file token.json stores the user's access and refresh tokens, and is
     created automatically when the authorization flow completes for the first
     time.
    """
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIAL_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    try:
        service = build('sheets', 'v4', credentials=creds)
        # Call the Sheets API
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID,
                                    range=READ_RANGE_NAME).execute()
        values = result.get('values', [])
        if not values:
            print('No data found.')
        start_row = len(values) + int(os.environ['ROW_OFFSET'])
        print(f"Last populated index should be {start_row - 1}. Updating transactions...")
        WRITE_RANGE_NAME = f'A{start_row}:K{int(os.getenv("MAX_ROWS"))}'
        values = parsed_transactions
        body = {
            'values': values
        }
        for val in values:
            print(val)
        result = service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID, range=WRITE_RANGE_NAME,
            valueInputOption="USER_ENTERED", body=body).execute()
        print(f"{result.get('updatedCells')} cells updated.")

    except HttpError as err:
        print(err)
        exit(-1)


def remove_transactions_file():
    """
    Remove downloaded transactions file
    :return:
    """
    print("Removing transaction file...")
    files = glob.glob(os.getenv('TRANSACTIONS_FILE_PATH') + '*.txt')
    for f in files:
        os.remove(f)


# This func is for update FROM_DATE to today's date, when process is completes succesfully.
def update_last_run_time():
    os.environ["LAST_RUN"] = datetime.datetime.today().strftime('%d/%m/%Y')
    dotenv.set_key(dotenv_file, "LAST_RUN", os.environ["LAST_RUN"])


print("Loading environment variables from .env")
load_env()
print("Parsing arguments")
FROM_DATE, TO_DATE = parse_args()
print("Initializing Webdriver")
driver = init_webdriver()
print("Navigating to HDFC Netbanking Login Page")
navigate_to_login_page()
print("Logging in")
login()
print(f"Fetching transactions from {FROM_DATE} to {TO_DATE}")
get_current_month_account_statement()
driver.implicitly_wait(4)
download_file()
time.sleep(2.5)
driver.quit()
print("Parsing Transactions according to custom format")
transactions = parse_transactions()
print("Updating Google Sheet")
update_sheet(transactions)
print("Removing transactions file")
remove_transactions_file()
print("Updating Last Run Time for script. Will fetch transactions from today the next time.")
update_last_run_time()
print("Congrats, You have updated sheets according to your account transaction successfully.....")
