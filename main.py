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

def first_automation(session_manager):
    """First automation: Login with saved session and make GraphQL request"""
    try:
        # Select profile
        username = select_profile(session_manager)
        if not username:
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
        # Select profile
        username = select_profile(session_manager)
        if not username:
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
        # Select profile
        username = select_profile(session_manager)
        if not username:
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

def massive_unfollow(session_manager):
    """Massive unfollow system - unfollows all following"""
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
        
        # Get scraping settings
        following_config = config['scraping']['following']
        max_count = following_config['max_count']
        
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            print('\n' + '='*50)
            print('MASSIVE UNFOLLOW SYSTEM')
            print('='*50)
            print(f'Profile: @{username}')
            print(f'Batch size: {batch_size}')
            print(f'Safe list: {len(safe_list)} users')
            print(f'Pause between batches: {pause_between}s')
            print('='*50)
            
            if not auto_confirm:
                confirm = input("\n⚠ WARNING: This will unfollow ALL users (except safe list). Continue? (yes/no): ")
                if confirm.lower() != 'yes':
                    print("✓ Operation cancelled")
                    return
            
            print('\nStarting browser...')
            browser = p.chromium.launch(headless=False)
            
            # Create context with saved session
            context = session_manager.create_browser_context(browser, username)
            page = context.new_page()
            
            print('Loading Instagram...')
            page.goto(Endpoints.BASE_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            
            # Create following scraper
            scraper = FollowingScraper(page, session_manager, username)
            
            # Verify login
            if not scraper.verify_login_with_graphql():
                print("\n✗ Login verification failed. Please login again (option 1)")
                context.close()
                browser.close()
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
            
            # Main loop - continue until no more users to unfollow
            while True:
                batch_number += 1
                print(f"\n{'='*50}")
                print(f"BATCH #{batch_number}")
                print(f"{'='*50}")
                
                # Get following list
                print(f"Fetching up to {max_count} following...")
                following_data = scraper.get_following(count=max_count)
                
                if not following_data or not following_data.get('users'):
                    print("✓ No more users to unfollow!")
                    break
                
                all_users = following_data['users']
                total_count = following_data.get('count', len(all_users))
                
                # Filter out safe list users
                users_to_unfollow = []
                for user in all_users:
                    username_to_check = user.get('username')
                    if username_to_check in safe_list:
                        print(f"  → Skipping @{username_to_check} (in safe list)")
                        total_skipped += 1
                    else:
                        users_to_unfollow.append(user)
                        if len(users_to_unfollow) >= batch_size:
                            break
                
                if not users_to_unfollow:
                    print("✓ No more users to unfollow (all remaining are in safe list)")
                    break
                
                print(f"\nProcessing {len(users_to_unfollow)} users...")
                print(f"Total following: ~{total_count}")
                print(f"This batch: {len(users_to_unfollow)}")
                
                # Queue unfollow actions for this batch
                for user in users_to_unfollow:
                    action_manager.add_action(
                        unfollow_action,
                        target_id=str(user.get('id')),
                        target_username=user.get('username')
                    )
                
                # Execute the batch
                print(f"\nExecuting batch #{batch_number}...")
                results = action_manager.execute_queue(delay_between=True, save_progress=True)
                
                # Update statistics
                successful = sum(1 for r in results if r.success)
                failed = len(results) - successful
                total_unfollowed += successful
                total_failed += failed
                
                print(f"\nBatch #{batch_number} complete:")
                print(f"  ✓ Unfollowed: {successful}")
                print(f"  ✗ Failed: {failed}")
                
                # Check if we should stop on error
                if failed > 0 and stop_on_error:
                    print("\n✗ Stopping due to errors (stop_on_error is enabled)")
                    break
                
                # Check if we've reached the end
                if len(users_to_unfollow) < batch_size:
                    print("\n✓ Reached the end of following list")
                    break
                
                # Pause between batches
                if pause_between > 0:
                    print(f"\n⏸ Pausing for {pause_between} seconds between batches...")
                    
                    # Allow user to stop during pause
                    print("Press Ctrl+C to stop...")
                    try:
                        page.wait_for_timeout(pause_between * 1000)
                    except KeyboardInterrupt:
                        print("\n⚠ Stopped by user")
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
            
            print('\nWaiting 10 seconds before closing...')
            page.wait_for_timeout(10000)
            
            context.close()
            browser.close()
            print('Browser closed')
            
    except KeyboardInterrupt:
        print("\n\n⚠ Operation interrupted by user")
        print(f"Unfollowed {total_unfollowed} users before stopping")
    except Exception as e:
        print(f'Error in massive_unfollow: {e}')

def main():
    session_manager = SessionManager()
    
    while True:
        choice = input('\n1: Login (new or add profile)\n2: Login with saved session\n3: Clear saved sessions\n4: First Automation (GraphQL test)\n5: Scrape Following\n6: Explore Search\n7: Massive Unfollow (ALL)\n0: Exit\n> ')
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
                
                with sync_playwright() as p:
                    print('Starting browser...')
                    browser = p.chromium.launch(headless=False)
                    
                    # Create context with storage state (if username is known)
                    if username:
                        context = session_manager.create_browser_context(browser, username)
                    else:
                        # Create clean context for new login
                        context = browser.new_context(
                            viewport={'width': 1920, 'height': 1080},
                            locale='en-US',
                            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        )
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
            first_automation(session_manager)
            
        elif choice == '5':
            scrape_following(session_manager)
            
        elif choice == '6':
            scrape_explore(session_manager)
            
        elif choice == '7':
            massive_unfollow(session_manager)

if __name__ == '__main__':
    main()