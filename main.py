from playwright.sync_api import sync_playwright, TimeoutError
import signal
import sys
import json
import time
from typing import Optional

from ig_scraper.api import Endpoints, GraphQLClient, GraphQLInterceptor
from ig_scraper.auth import SessionManager
from ig_scraper.scrapers.following import FollowingScraper
from ig_scraper.scrapers.explore import ExploreScraper
from ig_scraper.actions import UnfollowAction, ActionManager
from ig_scraper.config import ConfigManager

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

def handle_2fa_with_backup(page, creds):
    """Handle 2FA using backup codes (supports multiple codes)"""
    try:
        print('\n' + '='*50)
        print('HANDLING 2FA WITH BACKUP CODES')
        print('='*50)
        
        # Get backup codes from credentials
        backup_codes = creds.get('backup-code', creds.get('backup_code', []))
        
        # Convert to list if it's a single string
        if isinstance(backup_codes, str):
            backup_codes = [backup_codes]
        
        if not backup_codes:
            print('✗ No backup codes found in credentials.json')
            print('  Please add "backup-code" field to credentials.json')
            return False
        
        print(f'→ Found {len(backup_codes)} backup code(s) to try')
        
        # Wait for 2FA page to load
        page.wait_for_timeout(2000)
        
        # Navigate to backup code option (only once)
        backup_button_selector = 'button:has-text("Try Another Way"), button:has-text("Use Backup Code")'
        try:
            page.wait_for_selector(backup_button_selector, timeout=5000)
            page.click(backup_button_selector)
            print('✓ Clicked on backup code option')
            page.wait_for_timeout(1000)
        except:
            print('→ Backup code option not found, might already be on backup page')
        
        # Look for the specific button to switch to backup codes
        specific_button = 'div.x889kno.xyri2b.x1a8lsjc.x1c1uobl > form > div:nth-child(5) > button'
        try:
            if page.query_selector(specific_button):
                page.click(specific_button)
                print('✓ Switched to backup code entry')
                page.wait_for_timeout(1000)
        except:
            pass
        
        # Try each backup code
        for i, code in enumerate(backup_codes, 1):
            print(f'\n→ Attempt {i}/{len(backup_codes)}: Using code {code[:4]}****')
            
            # Find and fill the backup code input
            code_input_selectors = [
                'input[name="verificationCode"]',
                'input[aria-label*="code"]',
                'input[aria-label*="Code"]',
                'input[type="tel"]',
                'input[type="text"][maxlength="8"]',
                'input[placeholder*="code"]'
            ]
            
            filled = False
            for selector in code_input_selectors:
                try:
                    input_field = page.query_selector(selector)
                    if input_field:
                        # Clear the field first
                        input_field.click()
                        page.keyboard.press('Control+A')
                        page.keyboard.press('Delete')
                        # Fill with new code
                        page.fill(selector, code)
                        print(f'  ✓ Code entered')
                        filled = True
                        break
                except:
                    continue
            
            if not filled:
                print('  ✗ Could not find backup code input field')
                continue
            
            # Submit the backup code and wait for response
            try:
                # Listen for the verification response
                with page.expect_response("**/accounts/login/ajax/two_factor/**", timeout=10000) as response_info:
                    # Submit the code
                    submit_selectors = [
                        'button:has-text("Confirm")',
                        'button:has-text("Submit")',
                        'button:has-text("Verify")',
                        'button[type="button"]:not(:disabled)',
                        'form button[type="button"]'
                    ]
                    
                    submitted = False
                    for selector in submit_selectors:
                        try:
                            button = page.query_selector(selector)
                            if button and button.is_enabled():
                                button.click()
                                print('  ✓ Code submitted')
                                submitted = True
                                break
                        except:
                            continue
                    
                    if not submitted:
                        print('  → Trying Enter key')
                        page.keyboard.press('Enter')
                
                # Check the response
                verification_response = response_info.value
                response_data = verification_response.json()
                
                if response_data.get('authenticated') or response_data.get('status') == 'ok':
                    print('  ✓ SUCCESS! Backup code accepted')
                    return True
                elif response_data.get('error_type') in ['invalid_verification_code', 'invalid_verficaition_code']:
                    # Note: Instagram has a typo in their error type (verficaition)
                    print(f'  ✗ Invalid code: {response_data.get("message", "Code rejected")}')
                    
                    # Wait and check if we're actually logged in (sometimes the error is misleading)
                    page.wait_for_timeout(2000)
                    if page.query_selector('svg[aria-label="Profile"]') or page.query_selector('svg[aria-label="Home"]'):
                        print('  ✓ Actually logged in despite error message!')
                        return True
                    
                    if i < len(backup_codes):
                        print(f'  → Waiting 3 seconds before next attempt...')
                        page.wait_for_timeout(3000)
                    continue
                else:
                    print(f'  ⚠ Unexpected response: {response_data}')
                    # Still check if we're logged in
                    page.wait_for_timeout(2000)
                    if page.query_selector('svg[aria-label="Profile"]') or page.query_selector('svg[aria-label="Home"]'):
                        print('  ✓ Login successful despite unexpected response!')
                        return True
                    
            except Exception as e:
                # No response or timeout, check if we're logged in
                page.wait_for_timeout(3000)
                if page.query_selector('svg[aria-label="Profile"]') or page.query_selector('span[role="link"][tabindex="0"]'):
                    print('  ✓ SUCCESS! Login detected')
                    return True
                else:
                    print(f'  ✗ Code might have failed: {str(e)[:100]}')
                    if i < len(backup_codes):
                        print(f'  → Waiting 3 seconds before next attempt...')
                        page.wait_for_timeout(3000)
        
        print('\n✗ All backup codes exhausted. Manual intervention required.')
        return False
        
    except Exception as e:
        print(f'✗ Error handling 2FA: {e}')
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
            
            # Check if we have backup codes and try to use them
            if creds.get('backup-code') or creds.get('backup_code'):
                print('→ Attempting to use backup code...')
                if handle_2fa_with_backup(page, creds):
                    print('✓ 2FA completed successfully with backup code!')
                    # Set authenticated flag since we completed 2FA
                    data['authenticated'] = True
                    data['status'] = 'ok'
                    return 'success', data
                else:
                    print('⚠ All backup codes failed, manual 2FA required')
                    return '2fa', data
            else:
                print('  No backup code in credentials, manual 2FA required')
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

def first_automation(session_manager, playwright):
    """First automation: Login with saved session and make GraphQL request"""
    from ig_scraper.browser import BrowserManager
    from ig_scraper.browser.manager import ProfileLockError
    
    try:
        # Select profile
        username = select_profile(session_manager)
        if not username:
            return
        
        print('Getting browser page...')
        # Use BrowserManager to get a page
        try:
            page = BrowserManager.get_new_page(username, session_manager, playwright)
        except ProfileLockError as e:
            print(f'\n❌ {e}')
            print(f'Profile @{username} is already open in another window.')
            print('Please close the other window or choose a different profile.')
            return
        
        print('Loading Instagram...')
        page.goto(Endpoints.BASE_URL, wait_until='domcontentloaded')
        page.wait_for_timeout(3000)
        
        # Check if logged in
        if not (page.query_selector('svg[aria-label="Profile"]') or page.query_selector('span[role="link"][tabindex="0"]')):
            print("Session expired. Please login again (option 1)")
            BrowserManager.close_page(username, page)
            return
        
        print('✓ Logged in successfully with saved session!')
        
        # Get user ID from saved session
        cookies = page.context.cookies()
        user_id = None
        for cookie in cookies:
            if cookie['name'] == 'ds_user_id':
                user_id = cookie['value']
                break
        
        if not user_id:
            print("Could not find user ID in cookies")
            BrowserManager.close_page(username, page)
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
        
        print('\nWaiting 10 seconds before closing tab...')
        page.wait_for_timeout(10000)
        
        BrowserManager.close_page(username, page)
        print('Tab closed')
            
    except Exception as e:
        print(f'Error in first_automation: {e}')

def scrape_following(session_manager, playwright):
    """Scrape following list"""
    from ig_scraper.browser import BrowserManager
    from ig_scraper.browser.manager import ProfileLockError
    
    try:
        # Select profile
        username = select_profile(session_manager)
        if not username:
            return
        
        print('Getting browser page...')
        # Use BrowserManager to get a page
        try:
            page = BrowserManager.get_new_page(username, session_manager, playwright)
        except ProfileLockError as e:
            print(f'\n❌ {e}')
            print(f'Profile @{username} is already open in another window.')
            print('Please close the other window or choose a different profile.')
            return
        
        print('Loading Instagram...')
        page.goto(Endpoints.BASE_URL, wait_until='domcontentloaded')
        page.wait_for_timeout(3000)
        
        # Create following scraper
        scraper = FollowingScraper(page, session_manager, username)
        
        # Verify login with GraphQL test
        if not scraper.verify_login_with_graphql():
            print("\n✗ Login verification failed. Please login again (option 1)")
            BrowserManager.close_page(username, page)
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
        
        print('\nWaiting 10 seconds before closing tab...')
        page.wait_for_timeout(10000)
        
        BrowserManager.close_page(username, page)
        print('Tab closed')
            
    except Exception as e:
        print(f'Error in scrape_following: {e}')

def scrape_explore(session_manager, playwright):
    """Scrape explore/search results"""
    from ig_scraper.browser import BrowserManager
    from ig_scraper.browser.manager import ProfileLockError
    
    try:
        # Select profile
        username = select_profile(session_manager)
        if not username:
            return
        
        print('Getting browser page...')
        # Use BrowserManager to get a page
        try:
            page = BrowserManager.get_new_page(username, session_manager, playwright)
        except ProfileLockError as e:
            print(f'\n❌ {e}')
            print(f'Profile @{username} is already open in another window.')
            print('Please close the other window or choose a different profile.')
            return
        
        print('Loading Instagram...')
        page.goto(Endpoints.BASE_URL, wait_until='domcontentloaded')
        page.wait_for_timeout(3000)
        
        # Create explore scraper
        scraper = ExploreScraper(page, session_manager, username)
            
        # Verify login with GraphQL test
        if not scraper.verify_login_with_graphql():
            print("\n✗ Login verification failed. Please login again (option 1)")
            BrowserManager.close_page(username, page)
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
            
            print('\nWaiting 10 seconds before closing tab...')
            page.wait_for_timeout(10000)
            
            BrowserManager.close_page(username, page)
            print('Tab closed')
            
    except Exception as e:
        print(f'Error in scrape_explore: {e}')

def select_profile(session_manager) -> Optional[str]:
    """Let user select a profile from saved sessions"""
    profiles = session_manager.list_profiles()
    
    if not profiles:
        print("No saved profiles found. Please login first (option 1)")
        return None
    
    print("\n" + "="*50)
    print("SAVED PROFILES")
    print("="*50)
    
    for i, profile in enumerate(profiles, 1):
        info = session_manager.get_profile_info(profile)
        if info:
            print(f"{i}. @{profile}")
            print(f"   Last saved: {info['last_saved']}")
            print(f"   GraphQL data: {'Yes' if info['has_graphql'] else 'No'}")
    
    print("="*50)
    
    try:
        choice = input(f"\nSelect profile (1-{len(profiles)}) or 0 to cancel: ")
        if choice == '0':
            return None
        
        idx = int(choice) - 1
        if 0 <= idx < len(profiles):
            selected = profiles[idx]
            print(f"\n✓ Selected profile: @{selected}")
            return selected
        else:
            print("Invalid selection")
            return None
    except ValueError:
        print("Invalid input")
        return None

def test_saved_session(username, session_manager, playwright):
    """Test saved session - can run in background"""
    from ig_scraper.browser import BrowserManager
    from ig_scraper.browser.manager import ProfileLockError
    
    try:
        print(f'[{username}] Getting browser page...')
        page = BrowserManager.get_new_page(username, session_manager, playwright)
        
        print(f'[{username}] Using saved session, checking if still logged in...')
        page.goto(Endpoints.BASE_URL)
        page.wait_for_timeout(3000)
        
        # Check if we're logged in
        if page.query_selector('svg[aria-label="Profile"]') or page.query_selector('span[role="link"][tabindex="0"]'):
            print(f'[{username}] ✓ Still logged in with saved session!')
            print(f'[{username}] Session active! Keeping tab open for 30 seconds...')
            page.wait_for_timeout(30000)
            
            # Close tab
            BrowserManager.close_page(username, page)
            print(f'[{username}] Tab closed')
            return True
        else:
            print(f'[{username}] Session expired, need to login again')
            BrowserManager.close_page(username, page)
            return False
    except ProfileLockError as e:
        print(f'\n❌ {e}')
        print(f'Profile @{username} is already open in another window.')
        print('Please close the other window or choose a different profile.')
        return False
    except Exception as e:
        print(f'[{username}] Error testing session: {e}')
        return False

def massive_unfollow(session_manager, playwright):
    """Massive unfollow system - unfollows all following"""
    from ig_scraper.browser import BrowserManager
    from ig_scraper.browser.manager import ProfileLockError
    
    try:
        # Select profile
        username = select_profile(session_manager)
        if not username:
            return
        
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.load_config(username)
        
        # Get unfollow settings
        unfollow_config = config['actions']['unfollow']
        batch_size = unfollow_config['batch_size']
        safe_list = unfollow_config['safe_list']
        pause_between = unfollow_config['pause_between_batches']
        stop_on_error = unfollow_config['stop_on_error']
        auto_confirm = unfollow_config['auto_confirm']
        aggressive_mode = unfollow_config.get('aggressive_mode', False)
        aggressive_retries = unfollow_config.get('aggressive_retries', 3)
        
        # Get scraping settings
        following_config = config['scraping']['following']
        max_count = following_config['max_count']
        
        from ig_scraper.browser import BrowserManager
        
        print('\n' + '='*50)
        print('MASSIVE UNFOLLOW SYSTEM')
        print('='*50)
        print(f'Profile: @{username}')
        print(f'Batch size: {batch_size}')
        print(f'Safe list: {len(safe_list)} users')
        print(f'Pause between batches: {pause_between}s')
        print(f'Aggressive mode: {aggressive_mode}')
        if aggressive_mode:
            print(f'  → Will retry {aggressive_retries} times when max_id is null')
        print('='*50)
        
        if not auto_confirm:
            confirm = input("\n⚠ WARNING: This will unfollow ALL users (except safe list). Continue? (yes/no): ")
            if confirm.lower() != 'yes':
                print("✓ Operation cancelled")
                return
        
        print('\nGetting browser page...')
        # Use BrowserManager to get a page (new tab if browser exists)
        try:
            page = BrowserManager.get_new_page(username, session_manager, playwright)
        except ProfileLockError as e:
            print(f'\n❌ {e}')
            print(f'Profile @{username} is already open in another window.')
            print('Please close the other window or choose a different profile.')
            return
        
        print('Loading Instagram...')
        page.goto(Endpoints.BASE_URL, wait_until='domcontentloaded')
        page.wait_for_timeout(3000)
        
        # Create following scraper
        scraper = FollowingScraper(page, session_manager, username)
        
        # Verify login
        if not scraper.verify_login_with_graphql():
            print("\n✗ Login verification failed. Please login again (option 1)")
            BrowserManager.close_page(username, page)
            return
        
        print("\n✓ Login verified! Starting massive unfollow...")
        
        # Statistics
        total_unfollowed = 0
        total_failed = 0
        total_skipped = 0
        batch_number = 0
        
        # Create action manager and unfollow action
        action_manager = ActionManager(page, session_manager, username)
        unfollow_action = UnfollowAction(page, session_manager, username)
        
        # Track pagination state
        last_max_id = None
        pagination_attempts = 0
        max_pagination_attempts = 10  # Safety limit
        consecutive_empty_responses = 0
        max_empty_responses = 3
        aggressive_null_retries = 0  # Track retries when max_id is null in aggressive mode
        
        # Main loop - continue until no more users to unfollow
        page_number = 0
        while True:
            page_number += 1
            print(f"\n{'='*50}")
            print(f"PAGE #{page_number} - Loading up to {max_count} users")
            print(f"{'='*50}")
            print(f"[DEBUG] === START PAGE {page_number} ===")
            print(f"[DEBUG] Pagination state: max_id={last_max_id}, attempts={pagination_attempts}")
            print(f"[DEBUG] Consecutive empty responses: {consecutive_empty_responses}/{max_empty_responses}")
            print(f"[DEBUG] Total unfollowed so far: {total_unfollowed}")
            
            # Get following list (load max_count users at once)
            print(f"\n[DEBUG] Loading page with count={max_count}, max_id={last_max_id}")
            following_data = scraper.get_following(count=max_count, max_id=last_max_id)
            
            # Detailed logging for debugging
            print(f"\n[DEBUG] === API RESPONSE ANALYSIS ===")
            print(f"[DEBUG] Response received: {following_data is not None}")
            if following_data:
                print(f"[DEBUG] Response type: {type(following_data)}")
                print(f"[DEBUG] Response keys: {list(following_data.keys())}")
                print(f"[DEBUG] Has 'users' key: {'users' in following_data}")
                print(f"[DEBUG] Users count: {len(following_data.get('users', []))}")
                print(f"[DEBUG] Total count field: {following_data.get('count', 'not provided')}")
                print(f"[DEBUG] Has next_max_id: {'next_max_id' in following_data}")
                print(f"[DEBUG] next_max_id value: {following_data.get('next_max_id', 'None')}")
                print(f"[DEBUG] big_list field: {following_data.get('big_list', 'not provided')}")
                if 'status' in following_data:
                    print(f"[DEBUG] Response status: {following_data['status']}")
            
            if not following_data:
                consecutive_empty_responses += 1
                print(f"\n✗ No response from API (following_data is None)")
                print(f"[DEBUG] Consecutive empty: {consecutive_empty_responses}/{max_empty_responses}")
                print("[DEBUG] Possible reasons: network error, API limit, session expired")
                
                if consecutive_empty_responses >= max_empty_responses:
                    print(f"[DEBUG] Max empty responses reached ({max_empty_responses}). Stopping.")
                    break
                
                print(f"[DEBUG] Retrying... ({consecutive_empty_responses}/{max_empty_responses})")
                page.wait_for_timeout(5000)  # Wait 5 seconds before retry
                continue
                
            # Reset empty response counter on successful response
            consecutive_empty_responses = 0
                
            if not following_data.get('users'):
                print("\n[DEBUG] Response has no users or empty users list")
                print(f"[DEBUG] Full response keys: {list(following_data.keys())}")
                print(f"[DEBUG] Response status: {following_data.get('status', 'unknown')}")
                
                # Check if this is truly the end or an error
                if following_data.get('status') == 'ok' and following_data.get('users') == []:
                    print("✓ API returned empty users list with OK status - end of following list")
                    break
                else:
                    print("⚠ Unexpected response structure - may be an error")
                    print(f"[DEBUG] Full response (first 500 chars): {str(following_data)[:500]}")
                    break
            
            all_users = following_data['users']
            total_count = following_data.get('count', len(all_users))
            print(f"\n✓ Retrieved {len(all_users)} users from this page")
            print(f"Total following count: ~{total_count}")
            
            # Filter out safe list users from ALL loaded users
            filtered_users = []
            skipped_in_page = 0
            
            print(f"\n[DEBUG] Filtering {len(all_users)} users (removing safe list)...")
            for user in all_users:
                username_to_check = user.get('username')
                if username_to_check in safe_list:
                    print(f"  → Skipping @{username_to_check} (in safe list)")
                    total_skipped += 1
                    skipped_in_page += 1
                else:
                    filtered_users.append(user)
            
            print(f"[DEBUG] Filter complete: {len(filtered_users)} to unfollow, {skipped_in_page} skipped")
            
            if not filtered_users:
                print("\n[DEBUG] No users to unfollow on this page (all were in safe list or empty)")
                
                # In aggressive mode, even if no users, keep trying if we haven't reached limit
                if aggressive_mode and len(all_users) == 0 and aggressive_null_retries < aggressive_retries:
                    aggressive_null_retries += 1
                    print(f"\n⚠ AGGRESSIVE MODE: Empty user list but will retry ({aggressive_null_retries}/{aggressive_retries})")
                    print(f"[DEBUG] Instagram might be hiding users, retrying...")
                    
                    if pause_between > 0:
                        print(f"⏸ Pausing {pause_between}s before aggressive retry...")
                        page.wait_for_timeout(pause_between * 1000)
                    continue
                
                if following_data.get('next_max_id'):
                    print("[DEBUG] But there are more pages to check...")
                    last_max_id = following_data.get('next_max_id')
                    aggressive_null_retries = 0  # Reset counter for new page
                    continue
                else:
                    print("✓ No more pages available - complete!")
                    break
            
            # Process filtered users in mini-batches
            print(f"\n{'='*50}")
            print(f"Processing {len(filtered_users)} users in batches of {batch_size}")
            print(f"{'='*50}")
            
            users_processed_in_page = 0
            while filtered_users and users_processed_in_page < len(all_users):
                batch_number += 1
                
                # Take next mini-batch
                current_batch = filtered_users[:batch_size]
                filtered_users = filtered_users[batch_size:]
                
                print(f"\n{'='*50}")
                print(f"BATCH #{batch_number} (Page {page_number})")
                print(f"{'='*50}")
                print(f"Processing {len(current_batch)} users")
                print(f"Remaining in page: {len(filtered_users)}")
                
                # Queue unfollow actions for this mini-batch
                for user in current_batch:
                    action_manager.add_action(
                        unfollow_action,
                        target_id=str(user.get('id', user.get('pk'))),
                        target_username=user.get('username')
                    )
                
                # Execute the mini-batch
                print(f"\nExecuting batch #{batch_number}...")
                results = action_manager.execute_queue(delay_between=True, save_progress=True)
                
                # Update statistics
                successful = sum(1 for r in results if r.success)
                failed = len(results) - successful
                total_unfollowed += successful
                total_failed += failed
                users_processed_in_page += len(current_batch)
                
                print(f"\nBatch #{batch_number} complete:")
                print(f"  ✓ Unfollowed: {successful}")
                print(f"  ✗ Failed: {failed}")
                print(f"  Total unfollowed so far: {total_unfollowed}")
                
                if failed > 0:
                    print(f"[DEBUG] Failed actions details:")
                    for r in results:
                        if not r.success:
                            print(f"[DEBUG]   - @{r.target_username}: {r.error_message}")
                
                # Check if we should stop on error
                if failed > 0 and stop_on_error:
                    print(f"\n✗ Stopping due to errors (stop_on_error is enabled)")
                    filtered_users = []  # Clear remaining to exit
                    break
                
                # Pause between mini-batches (but not after the last one)
                if filtered_users and pause_between > 0:
                    print(f"\n⏸ Pausing {pause_between}s between batches...")
                    print("Press Ctrl+C to stop...")
                    try:
                        page.wait_for_timeout(pause_between * 1000)
                    except KeyboardInterrupt:
                        print("\n⚠ Stopped by user")
                        filtered_users = []  # Clear remaining to exit
                        break
            
            print(f"\n[DEBUG] Page {page_number} complete. Processed {users_processed_in_page} users")
            
            # After processing all mini-batches from this page, check pagination
            print(f"\n[DEBUG] === PAGINATION DECISION ===")
            print(f"[DEBUG] Page {page_number} fully processed")
            print(f"[DEBUG] Has next_max_id: {following_data.get('next_max_id') is not None}")
            print(f"[DEBUG] big_list flag: {following_data.get('big_list', False)}")
            
            # Check if there are more pages
            next_max_id = following_data.get('next_max_id')
            if next_max_id:
                print(f"[DEBUG] next_max_id exists: {next_max_id}")
                if next_max_id != last_max_id:
                    last_max_id = next_max_id
                    pagination_attempts = 0
                    aggressive_null_retries = 0  # Reset aggressive retries
                    print(f"\n➡ Moving to next page with max_id: {next_max_id}")
                    
                    # Optional pause before loading next page
                    if pause_between > 0:
                        print(f"\n⏸ Pausing {pause_between}s before loading next page...")
                        print("Press Ctrl+C to stop...")
                        try:
                            page.wait_for_timeout(pause_between * 1000)
                        except KeyboardInterrupt:
                            print("\n⚠ Stopped by user")
                            break
                    continue  # Load next page
                else:
                    print(f"[DEBUG] WARNING: next_max_id same as last ({last_max_id})")
                    pagination_attempts += 1
                    if pagination_attempts >= max_pagination_attempts:
                        print(f"[DEBUG] Max pagination attempts reached ({max_pagination_attempts})")
                        break
            else:
                # No next_max_id - Instagram might be limiting us
                print(f"\n[DEBUG] No next_max_id returned")
                
                if aggressive_mode and aggressive_null_retries < aggressive_retries:
                    aggressive_null_retries += 1
                    print(f"\n⚠ AGGRESSIVE MODE: max_id is null but will retry ({aggressive_null_retries}/{aggressive_retries})")
                    print(f"[DEBUG] Instagram might be limiting pagination, but we'll keep trying")
                    
                    # Keep the same last_max_id and try again
                    # This forces re-requesting the same page to see if we get different results
                    print(f"[DEBUG] Retrying with same max_id: {last_max_id}")
                    
                    if pause_between > 0:
                        print(f"\n⏸ Pausing {pause_between}s before aggressive retry...")
                        page.wait_for_timeout(pause_between * 1000)
                    continue  # Try again
                else:
                    if aggressive_mode:
                        print(f"\n✓ Max aggressive retries reached ({aggressive_retries})")
                    else:
                        print(f"\n✓ No more pages available (no next_max_id)")
                    break
            
            # Check big_list flag
            if following_data.get('big_list') == False:
                print(f"\n✓ Reached end of following list (big_list is False)")
                break
        
        # Final statistics
        print(f"\n{'='*50}")
        print(f"MASSIVE UNFOLLOW COMPLETE")
        print(f"{'='*50}")
        print(f"Total unfollowed: {total_unfollowed}")
        print(f"Total failed: {total_failed}")
        print(f"Total skipped (safe list): {total_skipped}")
        print(f"Batches processed: {batch_number}")
        print(f"Success rate: {(total_unfollowed / (total_unfollowed + total_failed) * 100) if (total_unfollowed + total_failed) > 0 else 0:.1f}%")
        print(f"{'='*50}")
        
        print('\nWaiting 10 seconds before closing tab...')
        page.wait_for_timeout(10000)
        
        # Close only the page, not the entire browser
        BrowserManager.close_page(username, page)
        print('Tab closed (browser remains open for other operations)')
        
    except KeyboardInterrupt:
        print("\n\n⚠ Operation interrupted by user")
        print(f"Unfollowed {total_unfollowed} users before stopping")
    except Exception as e:
        print(f'Error in massive_unfollow: {e}')

def main():
    from ig_scraper.browser import BrowserManager
    from playwright.sync_api import sync_playwright
    session_manager = SessionManager()
    
    # Start a single playwright instance for the entire session
    playwright = sync_playwright().start()
    
    # Register cleanup on exit
    import atexit
    def cleanup():
        BrowserManager.close_all()
        playwright.stop()
    atexit.register(cleanup)
    
    while True:
        # Show active browsers if any
        active = BrowserManager.get_active_profiles()
        if active:
            print("\n📱 Active browsers:")
            for profile in active:
                print(f"  → @{profile['username']}: {profile['tabs']} tabs")
        
        
        choice = input('\n1: Login (new or add profile)\n2: Login with saved session\n3: Clear saved sessions\n4: First Automation (GraphQL test)\n5: Scrape Following\n6: Explore Search\n7: Massive Unfollow (ALL)\n8: Browser Status\n9: Close All Browsers\n0: Exit\n> ')
        if choice == '0':
            break
            
        elif choice in ['1', '2']:
            try:
                # For login with saved session, select profile first
                if choice == '2':
                    username = select_profile(session_manager)
                    if not username:
                        continue
                else:
                    username = None  # Will be determined after login
                
                # Option 2: Use BrowserManager for saved sessions
                if choice == '2':
                    # Run in foreground
                    test_saved_session(username, session_manager, playwright)
                    
                    # End of option 2 - continue to next iteration
                    continue
                
                # Option 1: New login needs temporary browser
                if choice == '1':
                    print('Starting new browser for login...')
                    browser = playwright.chromium.launch(headless=False)
                    context = browser.new_context(
                        viewport={'width': 1920, 'height': 1080},
                        locale='en-US',
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    )
                    page = context.new_page()
                    
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
                    
                    # Extract username from cookies or page
                    if not username:
                        # Try to get username from cookies
                        cookies = context.cookies()
                        for cookie in cookies:
                            if cookie['name'] == 'ds_user_id':
                                user_id = cookie['value']
                                # Use GraphQL to get username
                                graphql_client = GraphQLClient(page, None)
                                response_data = graphql_client.get_profile_info(user_id)
                                if response_data:
                                    username = graphql_client.extract_username(response_data)
                                break
                        
                        # If still no username, try from login response
                        if not username and response_data:
                            username = response_data.get('username')
                        
                        # Fallback: ask user
                        if not username:
                            username = input("\nEnter your Instagram username (without @): ").strip()
                        
                        print(f"\n✓ Profile detected: @{username}")
                    
                    # Get captured GraphQL data
                    graphql_data = interceptor.get_session_data()
                    
                    # Save the session state with GraphQL data
                    print(f'\nSaving session for @{username}...')
                    session_manager.save_context_state(context, username, graphql_data)
                    
                    # Wait a bit
                    print('\nLogin successful! Session saved.')
                    print('Waiting 10 seconds before closing...')
                    page.wait_for_timeout(10000)
                    
                elif login_status == '2fa':
                    print('\nPlease complete 2FA in the browser')
                    input('Press Enter when done...')
                    
                    # Extract username after 2FA
                    if not username:
                        cookies = context.cookies()
                        for cookie in cookies:
                            if cookie['name'] == 'ds_user_id':
                                user_id = cookie['value']
                                graphql_client = GraphQLClient(page, None)
                                response_data = graphql_client.get_profile_info(user_id)
                                if response_data:
                                    username = graphql_client.extract_username(response_data)
                                break
                        
                        if not username:
                            username = input("\nEnter your Instagram username (without @): ").strip()
                        
                        print(f"\n✓ Profile detected: @{username}")
                    
                    # Get captured GraphQL data after 2FA
                    graphql_data = interceptor.get_session_data()
                    # Save session after 2FA
                    session_manager.save_context_state(context, username, graphql_data)
                    
                elif login_status == 'checkpoint':
                    print('\nPlease complete the checkpoint challenge in the browser')
                    input('Press Enter when done...')
                    
                    # Extract username after checkpoint
                    if not username:
                        cookies = context.cookies()
                        for cookie in cookies:
                            if cookie['name'] == 'ds_user_id':
                                user_id = cookie['value']
                                graphql_client = GraphQLClient(page, None)
                                response_data = graphql_client.get_profile_info(user_id)
                                if response_data:
                                    username = graphql_client.extract_username(response_data)
                                break
                        
                        if not username:
                            username = input("\nEnter your Instagram username (without @): ").strip()
                        
                        print(f"\n✓ Profile detected: @{username}")
                    
                    # Get captured GraphQL data after checkpoint
                    graphql_data = interceptor.get_session_data()
                    # Save session after checkpoint
                    session_manager.save_context_state(context, username, graphql_data)
                    
                else:
                    print('\nLogin was not successful')
                    input('Press Enter to close browser...')
                    
                    # Cleanup for option 1
                    context.close()
                    browser.close()
                    print('Browser closed')
                    
            except FileNotFoundError:
                print('Error: credentials.json not found')
            except Exception as e:
                print(f'Error: {e}')
                
        elif choice == '3':
            profiles = session_manager.list_profiles()
            if not profiles:
                print("No saved profiles to clear")
                continue
            
            print("\n1: Clear specific profile")
            print("2: Clear all profiles")
            sub_choice = input("Select option: ")
            
            if sub_choice == '1':
                username = select_profile(session_manager)
                if username:
                    confirm = input(f"Are you sure you want to clear @{username}? (y/n): ")
                    if confirm.lower() == 'y':
                        session_manager.clear_session(username)
            elif sub_choice == '2':
                confirm = input(f"Are you sure you want to clear ALL {len(profiles)} profiles? (y/n): ")
                if confirm.lower() == 'y':
                    session_manager.clear_all_sessions()
                
        elif choice == '4':
            first_automation(session_manager, playwright)
            
        elif choice == '5':
            scrape_following(session_manager, playwright)
            
        elif choice == '6':
            scrape_explore(session_manager, playwright)
            
        elif choice == '7':
            massive_unfollow(session_manager, playwright)
        
        elif choice == '8':
            BrowserManager.status()
            
        elif choice == '9':
            print("\nClosing all browsers...")
            BrowserManager.close_all()
            print("✓ All browsers closed")

if __name__ == '__main__':
    main()