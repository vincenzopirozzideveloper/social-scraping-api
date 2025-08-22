from playwright.sync_api import sync_playwright, TimeoutError
import signal
import sys
import json
import time

from ig_scraper.api import Endpoints, GraphQLClient, GraphQLInterceptor
from ig_scraper.auth import SessionManager
from ig_scraper.scrapers.following import FollowingScraper
from ig_scraper.scrapers.explore import ExploreScraper

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

def first_automation(session_manager):
    """First automation: Login with saved session and make GraphQL request"""
    try:
        # Load credentials to get username
        with open('credentials.json', 'r') as f:
            creds = json.load(f)
        username = creds['email'].split('@')[0]
        
        # Check if we have a saved session
        if not session_manager.has_saved_session(username):
            print("No saved session found. Please login first (option 1)")
            return
        
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            print('Starting browser with saved session...')
            browser = p.chromium.launch(headless=False)
            
            # Create context with saved session
            context = session_manager.create_browser_context(browser, username)
            page = context.new_page()
            
            print('Loading Instagram...')
            page.goto(Endpoints.BASE_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            
            # Check if logged in
            if not (page.query_selector('svg[aria-label="Profile"]') or page.query_selector('span[role="link"][tabindex="0"]')):
                print("Session expired. Please login again (option 1)")
                context.close()
                browser.close()
                return
            
            print('✓ Logged in successfully with saved session!')
            
            # Get user ID from saved session
            cookies = context.cookies()
            user_id = None
            for cookie in cookies:
                if cookie['name'] == 'ds_user_id':
                    user_id = cookie['value']
                    break
            
            if not user_id:
                print("Could not find user ID in cookies")
                context.close()
                browser.close()
                return
            
            print(f'User ID from cookies: {user_id}')
            
            # Load saved GraphQL metadata if available
            saved_info = session_manager.load_session_info(username)
            graphql_metadata = None
            if saved_info and 'graphql' in saved_info:
                graphql_metadata = saved_info['graphql']
                print(f"Loaded saved GraphQL metadata with {len(graphql_metadata.get('doc_ids', {}))} endpoints")
            
            # Create GraphQL client and make request
            print('\n' + '='*50)
            print('EXECUTING GRAPHQL REQUEST')
            print('='*50)
            
            graphql_client = GraphQLClient(page, graphql_metadata)
            response_data = graphql_client.get_profile_info(user_id)
            
            if response_data:
                username_from_api = graphql_client.extract_username(response_data)
                
                print('\n' + '='*50)
                print('RESULT')
                print('='*50)
                
                if username_from_api:
                    print(f'✓ USERNAME RETRIEVED: {username_from_api}')
                    
                    # Show more profile info if available
                    try:
                        user_data = response_data['data']['user']
                        print(f'  Full Name: {user_data.get("full_name", "N/A")}')
                        print(f'  Bio: {user_data.get("biography", "N/A")[:100]}...')
                        print(f'  Followers: {user_data.get("follower_count", "N/A")}')
                        print(f'  Following: {user_data.get("following_count", "N/A")}')
                        print(f'  Posts: {user_data.get("media_count", "N/A")}')
                        print(f'  Verified: {user_data.get("is_verified", False)}')
                    except:
                        pass
                else:
                    print('✗ Could not extract username from response')
                
                print('='*50)
            else:
                print('✗ GraphQL request failed')
            
            print('\nWaiting 10 seconds before closing...')
            page.wait_for_timeout(10000)
            
            context.close()
            browser.close()
            print('Browser closed')
            
    except Exception as e:
        print(f'Error in first_automation: {e}')

def scrape_following(session_manager):
    """Scrape following list"""
    try:
        # Load credentials to get username
        with open('credentials.json', 'r') as f:
            creds = json.load(f)
        username = creds['email'].split('@')[0]
        
        # Check if we have a saved session
        if not session_manager.has_saved_session(username):
            print("No saved session found. Please login first (option 1)")
            return
        
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            print('Starting browser with saved session...')
            browser = p.chromium.launch(headless=False)
            
            # Create context with saved session
            context = session_manager.create_browser_context(browser, username)
            page = context.new_page()
            
            print('Loading Instagram...')
            page.goto(Endpoints.BASE_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            
            # Create following scraper
            scraper = FollowingScraper(page, session_manager, username)
            
            # Verify login with GraphQL test
            if not scraper.verify_login_with_graphql():
                print("\n✗ Login verification failed. Please login again (option 1)")
                context.close()
                browser.close()
                return
            
            print("\n✓ Login verified! Proceeding with following scrape...")
            page.wait_for_timeout(2000)
            
            # Get following list
            following_data = scraper.get_following(count=12)
            
            if following_data:
                # Display the results
                scraper.display_following(following_data)
                
                # Check if there are more pages
                if following_data.get('next_max_id'):
                    print("\n" + "="*50)
                    choice = input("Load more following? (y/n): ")
                    if choice.lower() == 'y':
                        # Get next page
                        print("\nFetching next page...")
                        next_data = scraper.get_following(count=12, max_id=following_data['next_max_id'])
                        if next_data:
                            scraper.display_following(next_data)
            else:
                print("✗ Failed to get following list")
            
            print('\nWaiting 10 seconds before closing...')
            page.wait_for_timeout(10000)
            
            context.close()
            browser.close()
            print('Browser closed')
            
    except Exception as e:
        print(f'Error in scrape_following: {e}')

def scrape_explore(session_manager):
    """Scrape explore/search results"""
    try:
        # Load credentials to get username
        with open('credentials.json', 'r') as f:
            creds = json.load(f)
        username = creds['email'].split('@')[0]
        
        # Check if we have a saved session
        if not session_manager.has_saved_session(username):
            print("No saved session found. Please login first (option 1)")
            return
        
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            print('Starting browser with saved session...')
            browser = p.chromium.launch(headless=False)
            
            # Create context with saved session
            context = session_manager.create_browser_context(browser, username)
            page = context.new_page()
            
            print('Loading Instagram...')
            page.goto(Endpoints.BASE_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            
            # Create explore scraper
            scraper = ExploreScraper(page, session_manager, username)
            
            # Verify login with GraphQL test
            if not scraper.verify_login_with_graphql():
                print("\n✗ Login verification failed. Please login again (option 1)")
                context.close()
                browser.close()
                return
            
            print("\n✓ Login verified! Ready for explore search...")
            
            # Get search query from user
            query = input("\nEnter search query (e.g. 'news', 'tech', 'food'): ").strip()
            if not query:
                print("No query provided, using default: 'news'")
                query = "news"
            
            # Perform initial search
            explore_data = scraper.search_explore(query)
            
            if not explore_data:
                print("✗ Failed to get explore results")
            else:
                # Display the results
                scraper.display_results(explore_data)
                
                # Pagination loop
                page_count = 1
                while True:
                    # Check if there are more results (in root or media_grid)
                    next_max_id = explore_data.get('next_max_id') or explore_data.get('media_grid', {}).get('next_max_id')
                    if not next_max_id:
                        print("\n✓ No more pages available")
                        break
                    
                    print("\n" + "="*50)
                    choice = input(f"Load more results? (Page {page_count + 1}) (y/n): ")
                    if choice.lower() != 'y':
                        print("✓ Stopped pagination by user")
                        break
                    
                    # Get next page
                    print(f"\nFetching page {page_count + 1}...")
                    explore_data = scraper.search_explore(query, next_max_id=next_max_id)
                    
                    if not explore_data:
                        print("✗ Failed to get next page")
                        break
                    
                    # Display the new results
                    scraper.display_results(explore_data)
                    page_count += 1
                    
                print(f"\n✓ Total pages loaded: {page_count}")
            
            print('\nWaiting 10 seconds before closing...')
            page.wait_for_timeout(10000)
            
            context.close()
            browser.close()
            print('Browser closed')
            
    except Exception as e:
        print(f'Error in scrape_explore: {e}')

def main():
    session_manager = SessionManager()
    
    while True:
        choice = input('\n1: Login\n2: Login with saved session\n3: Clear saved sessions\n4: First Automation (GraphQL test)\n5: Scrape Following\n6: Explore Search\n0: Exit\n> ')
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
                        # Set up GraphQL interceptor
                        interceptor = GraphQLInterceptor()
                        interceptor.setup_interception(page)
                        
                        print('Navigating to Instagram login...')
                        page.goto(Endpoints.LOGIN_PAGE)
                        
                        handle_cookie_banner(page)
                        page.wait_for_timeout(1000)
                        
                        # Perform login and get result
                        login_status, response_data = perform_login(page)
                        
                        if login_status == 'success':
                            # Try to click the post-login button
                            click_post_login_button(page)
                            
                            # Wait a bit for more GraphQL requests to be captured
                            print('\nCapturing GraphQL metadata...')
                            page.wait_for_timeout(3000)
                            
                            # Get captured GraphQL data
                            graphql_data = interceptor.get_session_data()
                            
                            # Save the session state with GraphQL data
                            print('\nSaving session for future use...')
                            session_manager.save_context_state(context, username, graphql_data)
                            
                            # Wait a bit
                            print('\nLogin successful! Session saved.')
                            print('Waiting 10 seconds before closing...')
                            page.wait_for_timeout(10000)
                            
                        elif login_status == '2fa':
                            print('\nPlease complete 2FA in the browser')
                            input('Press Enter when done...')
                            # Get captured GraphQL data after 2FA
                            graphql_data = interceptor.get_session_data()
                            # Save session after 2FA
                            session_manager.save_context_state(context, username, graphql_data)
                            
                        elif login_status == 'checkpoint':
                            print('\nPlease complete the checkpoint challenge in the browser')
                            input('Press Enter when done...')
                            # Get captured GraphQL data after checkpoint
                            graphql_data = interceptor.get_session_data()
                            # Save session after checkpoint
                            session_manager.save_context_state(context, username, graphql_data)
                            
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
                
        elif choice == '4':
            first_automation(session_manager)
            
        elif choice == '5':
            scrape_following(session_manager)
            
        elif choice == '6':
            scrape_explore(session_manager)

if __name__ == '__main__':
    main()