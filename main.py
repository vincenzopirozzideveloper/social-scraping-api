from playwright.sync_api import sync_playwright, TimeoutError
import signal
import sys
import json

def signal_handler(sig, frame):
    print('\nClean exit.')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def handle_cookie_banner(page):
    try:
        print('Looking for cookie banner...')
        page.wait_for_selector('button._a9--._ap36._asz1', timeout=5000)
        page.click('button._a9--._ap36._asz1')
        print('✓ Cookie banner closed')
        return True
    except TimeoutError:
        print('Cookie banner not found')
        return False

def perform_login(page):
    try:
        with open('credentials.json', 'r') as f:
            creds = json.load(f)
        
        print('Filling username field...')
        page.fill('input[name="username"]', creds['email'])
        print('✓ Username entered')
        
        print('Filling password field...')
        page.fill('input[name="password"]', creds['password'])
        print('✓ Password entered')
        
        print('Clicking login button...')
        page.click('#loginForm button[type="submit"]')
        print('✓ Login form submitted')
        
        print('Waiting for login to process...')
        return True
    except Exception as e:
        print(f'Login error: {e}')
        return False

def main():
    while True:
        choice = input('\n1: Login\n0: Exit\n> ')
        if choice == '0':
            break
        elif choice == '1':
            with sync_playwright() as p:
                print('Starting browser...')
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                
                print('Navigating to Instagram login...')
                page.goto('https://www.instagram.com/accounts/login/')
                
                handle_cookie_banner(page)
                
                page.wait_for_timeout(1000)
                
                perform_login(page)
                
                input('\nPress enter to close browser...')
                browser.close()
                print('Browser closed')

if __name__ == '__main__':
    main()