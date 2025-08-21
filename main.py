from playwright.sync_api import sync_playwright, TimeoutError
import signal
import sys
import json
import time

from ig_scraper.api import Endpoints
from ig_scraper.auth import SessionManager

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
        
        print('Submitting login form and waiting for response...')
        
        # Professional approach: expect_response with the click
        with page.expect_response(Endpoints.LOGIN_AJAX) as response_info:
            page.click('#loginForm button[type="submit"]')
        
        # Get the response
        login_response = response_info.value
        print(f'✓ Login response intercepted (Status: {login_response.status})')
        
        # Parse response
        try:
            data = login_response.json()
            print('\n' + '='*50)
            print('LOGIN RESPONSE:')
            print(json.dumps(data, indent=2))
            print('='*50 + '\n')
        except Exception as e:
            print(f'Warning: Could not parse response body: {e}')
            # Create minimal data from status
            data = {'status': 'ok' if login_response.status == 200 else 'fail', 'authenticated': login_response.status == 200}
        
        # Check login status
        if data.get('authenticated') and data.get('status') == 'ok':
            print('✓ Login successful!')
            user_id = data.get('userId')
            if user_id:
                print(f'  User ID: {user_id}')
            return 'success', data
        elif data.get('two_factor_required'):
            print('⚠ Two-factor authentication required')
            return '2fa', data
        elif data.get('checkpoint_url'):
            print('⚠ Checkpoint challenge required')
            print(f'  Checkpoint URL: {data.get("checkpoint_url")}')
            return 'checkpoint', data
        else:
            print('✗ Login failed')
            if data.get('message'):
                print(f'  Message: {data.get("message")}')
            return 'failed', data
            
    except TimeoutError:
        print('✗ Login timeout - no response received')
        return 'timeout', None
    except Exception as e:
        print(f'✗ Login error: {e}')
        return 'error', None

def click_post_login_button(page):
    """Try to find and click the button that appears after login"""
    try:
        print('\nLooking for post-login button...')
        
        # Wait for page to stabilize after login
        page.wait_for_timeout(2000)
        
        # Try specific selector first
        button_selector = '#mount_0_0_yS > div > div > div.x9f619.x1n2onr6.x1ja2u2z > div > div > div.x78zum5.xdt5ytf.x1t2pt76.x1n2onr6.x1ja2u2z.x10cihs4 > div.html-div.xdj266r.x14z9mp.xat24cr.x1lziwak.xexx8yu.xyri2b.x18d9i69.x1c1uobl.x9f619.x16ye13r.xvbhtw8.x78zum5.x15mokao.x1ga7v0g.x16uus16.xbiv7yw.x1uhb9sk.x1plvlek.xryxfnj.x1c4vz4f.x2lah0s.x1q0g3np.xqjyukv.x1qjc9v5.x1oa3qoh.x1qughib > div.xvc5jky.xh8yej3.x10o80wk.x14k21rp.x17snn68.x6osk4m.x1porb0y.x8vgawa > section > main > div > div > section > div > button'
        
        button = page.query_selector(button_selector)
        
        if not button:
            # Fallback to more general selector
            print('Trying general selector...')
            button = page.query_selector('section button')
        
        if button:
            print('✓ Button found! Clicking...')
            button.click()
            print('✓ Button clicked successfully!')
            return True
        else:
            print('⚠ Button not found')
            return False
            
    except Exception as e:
        print(f'Error clicking button: {e}')
        return False

def main():
    session_manager = SessionManager()
    
    while True:
        choice = input('\n1: Login\n2: Login with saved session\n3: Clear saved sessions\n0: Exit\n> ')
        if choice == '0':
            break
            
        elif choice in ['1', '2']:
            try:
                # Load credentials
                with open('credentials.json', 'r') as f:
                    creds = json.load(f)
                username = creds['email'].split('@')[0]  # Use email prefix as username
                
                with sync_playwright() as p:
                    print('Starting browser...')
                    browser = p.chromium.launch(headless=False)
                    
                    # Create context with storage state
                    context = session_manager.create_browser_context(browser, username)
                    page = context.new_page()
                    
                    # Check if we need to login
                    if choice == '2' and session_manager.has_saved_session(username):
                        print('Using saved session, checking if still logged in...')
                        page.goto(Endpoints.BASE_URL)
                        page.wait_for_timeout(3000)
                        
                        # Check if we're logged in by looking for profile icon or login button
                        if page.query_selector('svg[aria-label="Profile"]') or page.query_selector('span[role="link"][tabindex="0"]'):
                            print('✓ Still logged in with saved session!')
                            print('\nSession active! Waiting 30 seconds...')
                            page.wait_for_timeout(30000)
                        else:
                            print('Session expired, need to login again')
                            choice = '1'  # Force fresh login
                    
                    if choice == '1':
                        print('Navigating to Instagram login...')
                        page.goto(Endpoints.LOGIN_PAGE)
                        
                        handle_cookie_banner(page)
                        page.wait_for_timeout(1000)
                        
                        # Perform login and get result
                        login_status, response_data = perform_login(page)
                        
                        if login_status == 'success':
                            # Try to click the post-login button
                            click_post_login_button(page)
                            
                            # Save the session state
                            print('\nSaving session for future use...')
                            session_manager.save_context_state(context, username)
                            
                            # Wait a bit
                            print('\nLogin successful! Session saved.')
                            print('Waiting 30 seconds before closing...')
                            page.wait_for_timeout(30000)
                            
                        elif login_status == '2fa':
                            print('\nPlease complete 2FA in the browser')
                            input('Press Enter when done...')
                            # Save session after 2FA
                            session_manager.save_context_state(context, username)
                            
                        elif login_status == 'checkpoint':
                            print('\nPlease complete the checkpoint challenge in the browser')
                            input('Press Enter when done...')
                            # Save session after checkpoint
                            session_manager.save_context_state(context, username)
                            
                        else:
                            print('\nLogin was not successful')
                            input('Press Enter to close browser...')
                    
                    context.close()
                    browser.close()
                    print('Browser closed')
                    
            except FileNotFoundError:
                print('Error: credentials.json not found')
            except Exception as e:
                print(f'Error: {e}')
                
        elif choice == '3':
            try:
                with open('credentials.json', 'r') as f:
                    creds = json.load(f)
                username = creds['email'].split('@')[0]
                session_manager.clear_session(username)
            except Exception as e:
                print(f'Error clearing session: {e}')

if __name__ == '__main__':
    main()