from typing import Optional
from pathlib import Path
import json
import time
from datetime import datetime
from ig_scraper.auth import SessionManager
from ig_scraper.api import Endpoints, GraphQLClient, GraphQLInterceptor
from ig_scraper.browser import BrowserManager
from ig_scraper.browser.manager import ProfileLockError
from ig_scraper.scrapers.following import FollowingScraper
from ig_scraper.scrapers.explore import ExploreScraper
from ig_scraper.scrapers.followers import FollowersScraper
from ig_scraper.actions import UnfollowAction, ActionManager
from ig_scraper.config import ConfigManager
from ig_scraper.config.env_config import CREDENTIALS_PATH, HEADLESS_MODE
from ig_scraper.core.handlers import (
    handle_cookie_banner,
    handle_2fa_with_backup,
    perform_login,
    click_post_login_button
)


class Commands:
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
    
    def select_profile(self) -> Optional[str]:
        profiles = self.session_manager.list_profiles()
        
        if not profiles:
            print("No saved profiles found. Please login first (option 1)")
            return None
        
        print("\n" + "="*50)
        print("SAVED PROFILES")
        print("="*50)
        
        for i, profile in enumerate(profiles, 1):
            info = self.session_manager.get_profile_info(profile)
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
    
    def login_new(self, playwright):
        try:
            print('Starting new browser for login...')
            
            launch_args = {
                'headless': HEADLESS_MODE,
            }
            
            # Always use Docker-optimized args
            launch_args['args'] = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
            
            browser = playwright.chromium.launch(**launch_args)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                locale='en-US',
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()
            
            interceptor = GraphQLInterceptor()
            interceptor.setup_interception(page)
            
            print('Navigating to Instagram login...')
            page.goto(Endpoints.LOGIN_PAGE)
            
            handle_cookie_banner(page)
            page.wait_for_timeout(1000)
            
            login_status, response_data = perform_login(page)
            
            if login_status == 'success':
                click_post_login_button(page)
            
            print('\nCapturing GraphQL metadata...')
            page.wait_for_timeout(3000)
            
            username = None
            cookies = context.cookies()
            for cookie in cookies:
                if cookie['name'] == 'ds_user_id':
                    user_id = cookie['value']
                    graphql_client = GraphQLClient(page, None)
                    response_data = graphql_client.get_profile_info(user_id)
                    if response_data:
                        username = graphql_client.extract_username(response_data)
                    break
            
            if not username and response_data:
                username = response_data.get('username')
            
            if not username:
                username = input("\nEnter your Instagram username (without @): ").strip()
            
            print(f"\n✓ Profile detected: @{username}")
            
            graphql_data = interceptor.get_session_data()
            
            print(f'\nSaving session for @{username}...')
            self.session_manager.save_context_state(context, username, graphql_data)
            
            print('\nLogin successful! Session saved.')
            print('Waiting 10 seconds before closing...')
            page.wait_for_timeout(10000)
            
            context.close()
            browser.close()
            print('Browser closed')
            
        except FileNotFoundError:
            print('Error: credentials.json not found')
        except Exception as e:
            print(f'Error: {e}')
    
    def login_saved(self, playwright):
        username = self.select_profile()
        if not username:
            return
        
        self.test_saved_session(username, playwright)
    
    def test_saved_session(self, username, playwright):
        try:
            print(f'[{username}] Getting browser page...')
            page = BrowserManager.get_new_page(username, self.session_manager, playwright)
            
            print(f'[{username}] Using saved session, checking if still logged in...')
            page.goto(Endpoints.BASE_URL)
            page.wait_for_timeout(3000)
            
            if page.query_selector('svg[aria-label="Profile"]') or page.query_selector('span[role="link"][tabindex="0"]'):
                print(f'[{username}] ✓ Still logged in with saved session!')
                
                if HEADLESS_MODE:
                    screenshots_dir = Path('/app/screenshots')  # Always Docker path
                    screenshots_dir.mkdir(exist_ok=True)
                    
                    print(f'\n[{username}] Screenshot Options:')
                    print('1. Current page (Home)')
                    print('2. My profile')
                    print('3. Specific user profile')
                    print('4. Skip screenshot')
                    
                    screenshot_choice = input('Select option (1-4): ')
                    
                    if screenshot_choice != '4':
                        if screenshot_choice == '2':
                            print(f'[{username}] Navigating to your profile...')
                            page.goto(f'https://www.instagram.com/{username}/')
                            page.wait_for_timeout(2000)
                        elif screenshot_choice == '3':
                            target_user = input('Enter username to visit: @')
                            print(f'[{username}] Navigating to @{target_user}...')
                            page.goto(f'https://www.instagram.com/{target_user}/')
                            page.wait_for_timeout(2000)
                        
                        from datetime import datetime
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        screenshot_path = screenshots_dir / f'{username}_{timestamp}.png'
                        
                        print(f'[{username}] Taking screenshot...')
                        page.screenshot(path=str(screenshot_path), full_page=True)
                        print(f'[{username}] ✓ Screenshot saved: {screenshot_path}')
                        
                        viewport_path = screenshots_dir / f'{username}_{timestamp}_viewport.png'
                        page.screenshot(path=str(viewport_path), full_page=False)
                        print(f'[{username}] ✓ Viewport screenshot saved: {viewport_path}')
                
                print(f'[{username}] Session active! Press Ctrl+C to return to menu...')
                
                import time
                for i in range(5, 0, -1):
                    print(f'  Closing in {i} seconds...', end='\r')
                    time.sleep(1)
                
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
    
    def clear_sessions(self):
        profiles = self.session_manager.list_profiles()
        if not profiles:
            print("No saved profiles to clear")
            return
        
        print("\n1: Clear specific profile")
        print("2: Clear all profiles")
        sub_choice = input("Select option: ")
        
        if sub_choice == '1':
            username = self.select_profile()
            if username:
                confirm = input(f"Are you sure you want to clear @{username}? (y/n): ")
                if confirm.lower() == 'y':
                    self.session_manager.clear_session(username)
        elif sub_choice == '2':
            confirm = input(f"Are you sure you want to clear ALL {len(profiles)} profiles? (y/n): ")
            if confirm.lower() == 'y':
                self.session_manager.clear_all_sessions()
    
    def first_automation(self, playwright):
        try:
            username = self.select_profile()
            if not username:
                return
            
            print('Getting browser page...')
            try:
                page = BrowserManager.get_new_page(username, self.session_manager, playwright)
            except ProfileLockError as e:
                print(f'\n❌ {e}')
                print(f'Profile @{username} is already open in another window.')
                print('Please close the other window or choose a different profile.')
                return
            
            print('Loading Instagram...')
            page.goto(Endpoints.BASE_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            
            if not (page.query_selector('svg[aria-label="Profile"]') or page.query_selector('span[role="link"][tabindex="0"]')):
                print("Session expired. Please login again (option 1)")
                BrowserManager.close_page(username, page)
                return
            
            print('✓ Logged in successfully with saved session!')
            
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
            
            saved_info = self.session_manager.load_session_info(username)
            graphql_metadata = None
            if saved_info and 'graphql' in saved_info:
                graphql_metadata = saved_info['graphql']
                print(f"Loaded saved GraphQL metadata with {len(graphql_metadata.get('doc_ids', {}))} endpoints")
            
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
    
    def scrape_following(self, playwright):
        try:
            username = self.select_profile()
            if not username:
                return
            
            print('Getting browser page...')
            try:
                page = BrowserManager.get_new_page(username, self.session_manager, playwright)
            except ProfileLockError as e:
                print(f'\n❌ {e}')
                print(f'Profile @{username} is already open in another window.')
                print('Please close the other window or choose a different profile.')
                return
            
            print('Loading Instagram...')
            page.goto(Endpoints.BASE_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            
            scraper = FollowingScraper(page, self.session_manager, username)
            
            if not scraper.verify_login_with_graphql():
                print("\n✗ Login verification failed. Please login again (option 1)")
                BrowserManager.close_page(username, page)
                return
            
            print("\n✓ Login verified! Ready for following scraping...")
            
            # Ask for target username
            target_username = input("\nEnter username to scrape following from (press Enter for your own): @").strip().replace('@', '')
            if not target_username:
                target_username = username
                print(f"Using your own profile: @{target_username}")
            
            # Get user ID for the target
            if target_username == username:
                # Use our own user ID from cookies
                cookies = page.context.cookies()
                user_id = None
                for cookie in cookies:
                    if cookie['name'] == 'ds_user_id':
                        user_id = cookie['value']
                        break
                if not user_id:
                    print("✗ Could not find user ID")
                    BrowserManager.close_page(username, page)
                    return
            else:
                # Navigate to target user profile to get their ID
                print(f"\nNavigating to @{target_username}'s profile...")
                page.goto(f"https://www.instagram.com/{target_username}/", wait_until='domcontentloaded')
                page.wait_for_timeout(3000)
                
                # Try to get user ID from page
                print("Getting user ID...")
                user_id = None
                
                try:
                    user_id = page.evaluate("""
                        () => {
                            // Try from meta tag
                            const meta = document.querySelector('meta[property="instapp:owner_user_id"]');
                            if (meta) return meta.content;
                            
                            // Try from script tags
                            const scripts = Array.from(document.querySelectorAll('script'));
                            for (const script of scripts) {
                                const text = script.textContent;
                                if (text.includes('profilePage_')) {
                                    const match = text.match(/profilePage_(\\d+)/);
                                    if (match) return match[1];
                                }
                                if (text.includes('"user_id":"')) {
                                    const match = text.match(/"user_id":"(\\d+)"/);
                                    if (match) return match[1];
                                }
                            }
                            return null;
                        }
                    """)
                except:
                    pass
                
                if not user_id:
                    print("✗ Could not find user ID. User might not exist or be blocked.")
                    BrowserManager.close_page(username, page)
                    return
            
            print(f"✓ Found user ID: {user_id}")
            
            # Get configuration
            config_manager = ConfigManager()
            config = config_manager.load_config(username)
            following_config = config.get('scraping', {}).get('following', {})
            
            max_count = following_config.get('max_count', 200)
            auto_pagination = following_config.get('auto_pagination', True)
            max_pages = following_config.get('max_pages', 10)
            page_delay_min = following_config.get('page_delay_min', 3)
            page_delay_max = following_config.get('page_delay_max', 8)
            
            print(f"\n{'='*50}")
            print(f"FOLLOWING SCRAPING")
            print(f"{'='*50}")
            print(f"Target: @{target_username}")
            print(f"Following per page: {max_count}")
            print(f"Auto-pagination: {auto_pagination}")
            if auto_pagination:
                print(f"Max pages: {max_pages}")
            print(f"{'='*50}")
            
            # Create scraping session in database
            session_id = scraper.create_scraping_session(target_username)
            if not session_id:
                print("✗ Failed to create scraping session")
                BrowserManager.close_page(username, page)
                return
            
            total_following = 0
            last_max_id = None
            page_number = 0
            
            try:
                while True:
                    page_number += 1
                    
                    if auto_pagination and page_number > max_pages:
                        print(f"\n✓ Reached max pages limit ({max_pages})")
                        break
                    
                    print(f"\n{'='*50}")
                    print(f"PAGE #{page_number}")
                    print(f"{'='*50}")
                    
                    # Get following with target user ID
                    following_data = scraper.get_following_for_user(user_id, target_username, count=max_count, max_id=last_max_id)
                    
                    if not following_data:
                        print("✗ Failed to get following")
                        break
                    
                    users = following_data.get('users', [])
                    if not users:
                        print("✓ No more following")
                        break
                    
                    # Display following
                    scraper.display_following(following_data)
                    
                    # Save to database
                    saved = scraper.save_following(session_id, users, page_number)
                    total_following += saved
                    
                    # Check for next page
                    next_max_id = following_data.get('next_max_id')
                    if not next_max_id:
                        print("\n✓ No more pages available")
                        break
                    
                    last_max_id = next_max_id
                    
                    if auto_pagination:
                        # Random delay between pages
                        import random
                        delay = random.uniform(page_delay_min, page_delay_max)
                        print(f"\n⏳ Waiting {delay:.1f}s before next page...")
                        page.wait_for_timeout(int(delay * 1000))
                    else:
                        # Manual pagination
                        choice = input(f"\nLoad more following? (Page {page_number + 1}) (y/n): ")
                        if choice.lower() != 'y':
                            print("✓ Stopped by user")
                            break
            
            finally:
                # Close scraping session
                scraper.close_scraping_session(session_id)
            
            print(f"\n{'='*50}")
            print(f"SCRAPING COMPLETE")
            print(f"{'='*50}")
            print(f"Target: @{target_username}")
            print(f"Total following saved: {total_following}")
            print(f"Total pages: {page_number}")
            print(f"{'='*50}")
            
            print('\nWaiting 10 seconds before closing tab...')
            page.wait_for_timeout(10000)
            
            BrowserManager.close_page(username, page)
            print('Tab closed')
                
        except Exception as e:
            print(f'Error in scrape_following: {e}')
    
    def scrape_explore(self, playwright):
        try:
            username = self.select_profile()
            if not username:
                return
            
            print('Getting browser page...')
            try:
                page = BrowserManager.get_new_page(username, self.session_manager, playwright)
            except ProfileLockError as e:
                print(f'\n❌ {e}')
                print(f'Profile @{username} is already open in another window.')
                print('Please close the other window or choose a different profile.')
                return
            
            print('Loading Instagram...')
            page.goto(Endpoints.BASE_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            
            scraper = ExploreScraper(page, self.session_manager, username)
            
            if not scraper.verify_login_with_graphql():
                print("\n✗ Login verification failed. Please login again (option 1)")
                BrowserManager.close_page(username, page)
                return
            
            print("\n✓ Login verified! Ready for explore search...")
            
            # Check if there's a saved state to resume from
            state_file = Path('explore_state.json')
            resume_state = None
            if state_file.exists():
                try:
                    with open(state_file, 'r') as f:
                        saved_state = json.load(f)
                    print(f"\n📂 Found saved state from {saved_state['timestamp']}")
                    print(f"   Query: {saved_state['query']}")
                    print(f"   Page: {saved_state['page_count']}")
                    resume = input("Resume from saved state? (y/n): ")
                    if resume.lower() == 'y':
                        resume_state = saved_state
                except:
                    pass
            
            if resume_state:
                query = resume_state.get('query', '')
                initial_page = resume_state['page_count']
                if query:
                    print(f"\n▶️  Resuming search for '{query}' from page {initial_page}")
                    explore_data = scraper.search_explore(query, next_max_id=resume_state.get('next_max_id'))
                else:
                    print(f"\n▶️  Resuming general explore from page {initial_page}")
                    explore_data = scraper.get_general_explore(max_id=resume_state.get('next_max_id'))
            else:
                query = input("\nEnter search query (press Enter for general explore): ").strip()
                if not query:
                    print("📍 Using general explore (no search query)")
                    explore_data = scraper.get_general_explore()
                else:
                    print(f"🔍 Searching for: {query}")
                    explore_data = scraper.search_explore(query)
                initial_page = 0
            
            if not explore_data:
                print("✗ Failed to get explore results")
            else:
                scraper.display_results(explore_data)
                
                # Check if auto-pagination is enabled
                explore_config = scraper.config['scraping']['explore']
                auto_pagination = explore_config.get('auto_pagination', False)
                infinite_pagination = explore_config.get('infinite_pagination', False)
                max_pages = explore_config.get('max_pages', 999)
                page_delay_min = explore_config.get('page_delay_min', 15)
                page_delay_max = explore_config.get('page_delay_max', 30)
                hourly_request_limit = explore_config.get('hourly_request_limit', 200)
                pause_on_limit_minutes = explore_config.get('pause_on_limit_minutes', 60)
                
                page_count = initial_page + 1 if resume_state else 1
                
                # Get profile ID for rate limiting
                from ig_scraper.database import DatabaseManager
                db = DatabaseManager()
                profile = db.get_profile_by_username(username)
                if not profile:
                    profile_id = db.get_or_create_profile(username)
                else:
                    profile_id = profile['id']
                
                if auto_pagination:
                    if infinite_pagination:
                        print(f"\n♾️  Infinite pagination enabled")
                        print(f"📊 Rate limit: {hourly_request_limit} requests/hour (database controlled)")
                        print(f"⏸️  Will pause {pause_on_limit_minutes} minutes if limit reached")
                    else:
                        print(f"\n🔄 Auto-pagination enabled (max {max_pages} pages)")
                    
                    while True:
                        # Check hourly rate limit using database
                        can_proceed, current_count = db.check_and_increment_hourly_limit(profile_id, hourly_request_limit)
                        
                        if not can_proceed:
                            print(f"\n⚠️ HOURLY LIMIT REACHED! ({current_count}/{hourly_request_limit})")
                            print(f"⏸️  Must wait until next hour or pause for {pause_on_limit_minutes} minutes...")
                            
                            # Save state for resuming
                            if explore_config.get('save_pagination_state', True):
                                state = {
                                    'query': query,
                                    'next_max_id': explore_data.get('next_max_id') or explore_data.get('media_grid', {}).get('next_max_id'),
                                    'page_count': page_count,
                                    'timestamp': datetime.now().isoformat()
                                }
                                state_file = Path('explore_state.json')
                                with open(state_file, 'w') as f:
                                    import json
                                    json.dump(state, f, indent=2)
                                print(f"💾 State saved to {state_file}")
                            
                            # Pause
                            page.wait_for_timeout(pause_on_limit_minutes * 60 * 1000)
                            
                            print("\n▶️  Resuming pagination after pause...")
                            continue  # Try again after pause
                        
                        # Check page limit (only if not infinite)
                        if not infinite_pagination and page_count >= max_pages:
                            print(f"\n✓ Reached max pages limit ({max_pages})")
                            break
                        
                        next_max_id = explore_data.get('next_max_id') or explore_data.get('media_grid', {}).get('next_max_id')
                        if not next_max_id:
                            print("\n✓ No more pages available - reached the end!")
                            break
                        
                        # Random delay between pages
                        import random
                        delay = random.uniform(page_delay_min, page_delay_max)
                        print(f"\n⏳ Waiting {delay:.1f}s before loading page {page_count + 1}...")
                        print(f"📊 Requests this hour: {current_count}/{hourly_request_limit}")
                        page.wait_for_timeout(int(delay * 1000))
                        
                        print(f"\n{'='*50}")
                        print(f"Fetching page {page_count + 1}...")
                        
                        # Use appropriate method based on whether we have a query
                        if query:
                            explore_data = scraper.search_explore(query, next_max_id=next_max_id)
                        else:
                            explore_data = scraper.get_general_explore(max_id=next_max_id)
                        
                        if not explore_data:
                            print("✗ Failed to get next page")
                            break
                        
                        scraper.display_results(explore_data)
                        page_count += 1
                else:
                    # Manual pagination
                    while True:
                        next_max_id = explore_data.get('next_max_id') or explore_data.get('media_grid', {}).get('next_max_id')
                        if not next_max_id:
                            print("\n✓ No more pages available")
                            break
                        
                        print("\n" + "="*50)
                        choice = input(f"Load more results? (Page {page_count + 1}) (y/n): ")
                        if choice.lower() != 'y':
                            print("✓ Stopped pagination by user")
                            break
                        
                        print(f"\nFetching page {page_count + 1}...")
                        # Use appropriate method based on whether we have a query
                        if query:
                            explore_data = scraper.search_explore(query, next_max_id=next_max_id)
                        else:
                            explore_data = scraper.get_general_explore(max_id=next_max_id)
                        
                        if not explore_data:
                            print("✗ Failed to get next page")
                            break
                        
                        scraper.display_results(explore_data)
                        page_count += 1
                    
                print(f"\n✓ Total pages loaded: {page_count}")
                
                # Close the search session in database
                scraper.close_search_session()
            
            print('\nWaiting 10 seconds before closing tab...')
            page.wait_for_timeout(10000)
            
            BrowserManager.close_page(username, page)
            print('Tab closed')
                
        except Exception as e:
            print(f'Error in scrape_explore: {e}')
    
    def scrape_followers(self, playwright):
        try:
            username = self.select_profile()
            if not username:
                return
            
            print('Getting browser page...')
            try:
                page = BrowserManager.get_new_page(username, self.session_manager, playwright)
            except ProfileLockError as e:
                print(f'\n❌ {e}')
                print(f'Profile @{username} is already open in another window.')
                print('Please close the other window or choose a different profile.')
                return
            
            print('Loading Instagram...')
            page.goto(Endpoints.BASE_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            
            scraper = FollowersScraper(page, self.session_manager, username)
            
            if scraper.verify_login and not scraper.verify_login_with_graphql():
                print("\n✗ Login verification failed. Please login again (option 1)")
                BrowserManager.close_page(username, page)
                return
            
            print("\n✓ Login verified! Ready for followers scraping...")
            
            # Ask for target username
            target_username = input("\nEnter username to scrape followers from: @").strip().replace('@', '')
            if not target_username:
                print("No username provided")
                BrowserManager.close_page(username, page)
                return
            
            # Navigate to user profile to get their ID
            print(f"\nNavigating to @{target_username}'s profile...")
            page.goto(f"https://www.instagram.com/{target_username}/", wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            
            # Try to get user ID from page
            print("Getting user ID...")
            user_id = None
            
            # Method 1: Try from page HTML
            try:
                user_id = page.evaluate("""
                    () => {
                        // Try from meta tag
                        const meta = document.querySelector('meta[property="instapp:owner_user_id"]');
                        if (meta) return meta.content;
                        
                        // Try from script tags
                        const scripts = Array.from(document.querySelectorAll('script'));
                        for (const script of scripts) {
                            const text = script.textContent;
                            if (text.includes('profilePage_')) {
                                const match = text.match(/profilePage_(\\d+)/);
                                if (match) return match[1];
                            }
                            if (text.includes('"user_id":"')) {
                                const match = text.match(/"user_id":"(\\d+)"/);
                                if (match) return match[1];
                            }
                        }
                        return null;
                    }
                """)
            except:
                pass
            
            if not user_id:
                print("✗ Could not find user ID. User might not exist or be blocked.")
                BrowserManager.close_page(username, page)
                return
            
            print(f"✓ Found user ID: {user_id}")
            
            # Create scraping session
            session_id = scraper.create_scraping_session(target_username, user_id)
            
            # Show session info
            if session_id:
                # Get session number from database
                try:
                    with scraper.db.get_cursor() as cursor:
                        cursor.execute("""
                            SELECT session_number 
                            FROM followers_scraping_sessions 
                            WHERE id = %s
                        """, (session_id,))
                        result = cursor.fetchone()
                        session_number = result['session_number'] if result else 1
                        print(f"\n📦 Session created: {target_username}->scraping-followers-{session_number:03d}")
                except:
                    pass
            
            # Configuration
            config_manager = ConfigManager()
            config = config_manager.load_config(username)
            followers_config = config.get('scraping', {}).get('followers', {})
            
            max_count = followers_config.get('max_count', 12)
            auto_pagination = followers_config.get('auto_pagination', True)
            max_pages = followers_config.get('max_pages', 9999)
            page_delay_min = followers_config.get('page_delay_min', 3)
            page_delay_max = followers_config.get('page_delay_max', 8)
            pause_after_pages = followers_config.get('pause_after_pages', 50)
            pause_duration_min = followers_config.get('pause_duration_min', 60)
            pause_duration_max = followers_config.get('pause_duration_max', 120)
            
            print(f"\n{'='*50}")
            print(f"FOLLOWERS SCRAPING SETTINGS")
            print(f"{'='*50}")
            print(f"Target: @{target_username}")
            print(f"Followers per page: {max_count}")
            print(f"Auto-pagination: {auto_pagination}")
            if auto_pagination:
                print(f"Max pages: {max_pages}")
                print(f"Pause every: {pause_after_pages} pages")
                print(f"Pause duration: {pause_duration_min}-{pause_duration_max}s")
            print(f"{'='*50}")
            
            total_followers = 0
            last_max_id = None
            page_number = 0
            
            while True:
                page_number += 1
                
                if auto_pagination and page_number > max_pages:
                    print(f"\n✓ Reached max pages limit ({max_pages})")
                    break
                
                print(f"\n{'='*50}")
                print(f"PAGE #{page_number}")
                print(f"{'='*50}")
                
                # Get followers
                followers_data = scraper.get_followers(user_id, count=max_count, max_id=last_max_id)
                
                if not followers_data:
                    print("✗ Failed to get followers")
                    break
                
                users = followers_data.get('users', [])
                if not users:
                    print("✓ No more followers")
                    break
                
                # Display followers
                scraper.display_followers(followers_data, page_number)
                
                # Save to database
                saved = scraper.save_followers(users, page_number)
                print(f"\n✓ Saved {saved} followers to database")
                
                total_followers += len(users)
                
                # Check for next page
                next_max_id = followers_data.get('next_max_id')
                if not next_max_id:
                    print("\n✓ No more pages available")
                    break
                
                last_max_id = next_max_id
                
                if auto_pagination:
                    # Check if we need a long pause
                    if page_number % pause_after_pages == 0:
                        import random
                        pause_duration = random.uniform(pause_duration_min, pause_duration_max)
                        print(f"\n{'='*50}")
                        print(f"⏸️  PAUSE AFTER {pause_after_pages} PAGES")
                        print(f"{'='*50}")
                        print(f"Scraped so far: {total_followers} followers")
                        print(f"Taking a break for {pause_duration:.0f} seconds...")
                        print(f"{'='*50}")
                        page.wait_for_timeout(int(pause_duration * 1000))
                        print("\n▶️  Resuming scraping...")
                    else:
                        # Normal delay between pages
                        import random
                        delay = random.uniform(page_delay_min, page_delay_max)
                        print(f"\n⏳ Waiting {delay:.1f}s before next page...")
                        page.wait_for_timeout(int(delay * 1000))
                else:
                    # Manual pagination
                    choice = input(f"\nLoad more followers? (Page {page_number + 1}) (y/n): ")
                    if choice.lower() != 'y':
                        print("✓ Stopped by user")
                        break
            
            # Close scraping session
            scraper.close_scraping_session()
            
            print(f"\n{'='*50}")
            print(f"SCRAPING COMPLETE")
            print(f"{'='*50}")
            print(f"Target: @{target_username}")
            print(f"Total followers scraped: {total_followers}")
            print(f"Total pages: {page_number}")
            print(f"Session: {target_username}->scraping-followers-{session_number:03d}")
            print(f"Session ID: #{scraper.scraping_session_id}")
            print(f"{'='*50}")
            
            print('\nWaiting 10 seconds before closing tab...')
            page.wait_for_timeout(10000)
            
            BrowserManager.close_page(username, page)
            print('Tab closed')
                
        except Exception as e:
            print(f'Error in scrape_followers: {e}')
    
    def massive_unfollow(self, playwright):
        try:
            username = self.select_profile()
            if not username:
                return
            
            config_manager = ConfigManager()
            config = config_manager.load_config(username)
            
            unfollow_config = config['actions']['unfollow']
            batch_size = unfollow_config['batch_size']
            safe_list = unfollow_config['safe_list']
            pause_between = unfollow_config['pause_between_batches']
            stop_on_error = unfollow_config['stop_on_error']
            auto_confirm = unfollow_config['auto_confirm']
            aggressive_mode = unfollow_config.get('aggressive_mode', False)
            aggressive_retries = unfollow_config.get('aggressive_retries', 3)
            
            following_config = config['scraping']['following']
            max_count = following_config['max_count']
            
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
            try:
                page = BrowserManager.get_new_page(username, self.session_manager, playwright)
            except ProfileLockError as e:
                print(f'\n❌ {e}')
                print(f'Profile @{username} is already open in another window.')
                print('Please close the other window or choose a different profile.')
                return
            
            print('Loading Instagram...')
            page.goto(Endpoints.BASE_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            
            scraper = FollowingScraper(page, self.session_manager, username)
            
            if not scraper.verify_login_with_graphql():
                print("\n✗ Login verification failed. Please login again (option 1)")
                BrowserManager.close_page(username, page)
                return
            
            print("\n✓ Login verified! Starting massive unfollow...")
            
            total_unfollowed = 0
            total_failed = 0
            total_skipped = 0
            batch_number = 0
            
            action_manager = ActionManager(page, self.session_manager, username)
            unfollow_action = UnfollowAction(page, self.session_manager, username)
            
            last_max_id = None
            pagination_attempts = 0
            max_pagination_attempts = 10
            consecutive_empty_responses = 0
            max_empty_responses = 3
            aggressive_null_retries = 0
            
            page_number = 0
            while True:
                page_number += 1
                print(f"\n{'='*50}")
                print(f"PAGE #{page_number} - Loading up to {max_count} users")
                print(f"{'='*50}")
                
                following_data = scraper.get_following(count=max_count, max_id=last_max_id)
                
                if not following_data:
                    consecutive_empty_responses += 1
                    print(f"\n✗ No response from API")
                    
                    if last_max_id and consecutive_empty_responses == 1:
                        print(f"\n⚠ STOP ERROR DETECTED - Retrying without max_id")
                        page.wait_for_timeout(pause_between * 1000)
                        
                        retry_data = scraper.get_following(count=max_count, max_id=None)
                        
                        if retry_data and retry_data.get('users'):
                            print(f"✓ RETRY SUCCESS! Got {len(retry_data['users'])} users without max_id")
                            following_data = retry_data
                            consecutive_empty_responses = 0
                            last_max_id = None
                    
                    if not following_data:
                        if consecutive_empty_responses >= max_empty_responses:
                            break
                        
                        page.wait_for_timeout(5000)
                        continue
                
                consecutive_empty_responses = 0
                
                if not following_data.get('users'):
                    if following_data.get('status') == 'ok' and following_data.get('users') == []:
                        print("✓ API returned empty users list with OK status - end of following list")
                        break
                    else:
                        print("⚠ Unexpected response structure - may be an error")
                        break
                
                all_users = following_data['users']
                total_count = following_data.get('count', len(all_users))
                print(f"\n✓ Retrieved {len(all_users)} users from this page")
                print(f"Total following count: ~{total_count}")
                
                filtered_users = []
                skipped_in_page = 0
                
                for user in all_users:
                    username_to_check = user.get('username')
                    if username_to_check in safe_list:
                        print(f"  → Skipping @{username_to_check} (in safe list)")
                        total_skipped += 1
                        skipped_in_page += 1
                    else:
                        filtered_users.append(user)
                
                if not filtered_users:
                    if aggressive_mode and len(all_users) == 0 and aggressive_null_retries < aggressive_retries:
                        aggressive_null_retries += 1
                        print(f"\n⚠ AGGRESSIVE MODE: Empty user list but will retry ({aggressive_null_retries}/{aggressive_retries})")
                        
                        if pause_between > 0:
                            print(f"⏸ Pausing {pause_between}s before aggressive retry...")
                            page.wait_for_timeout(pause_between * 1000)
                        continue
                    
                    if following_data.get('next_max_id'):
                        last_max_id = following_data.get('next_max_id')
                        aggressive_null_retries = 0
                        continue
                    else:
                        print("✓ No more pages available - complete!")
                        break
                
                print(f"\n{'='*50}")
                print(f"Processing {len(filtered_users)} users in batches of {batch_size}")
                print(f"{'='*50}")
                
                users_processed_in_page = 0
                while filtered_users and users_processed_in_page < len(all_users):
                    batch_number += 1
                    
                    current_batch = filtered_users[:batch_size]
                    filtered_users = filtered_users[batch_size:]
                    
                    print(f"\n{'='*50}")
                    print(f"BATCH #{batch_number} (Page {page_number})")
                    print(f"{'='*50}")
                    print(f"Processing {len(current_batch)} users")
                    print(f"Remaining in page: {len(filtered_users)}")
                    
                    for user in current_batch:
                        action_manager.add_action(
                            unfollow_action,
                            target_id=str(user.get('id', user.get('pk'))),
                            target_username=user.get('username')
                        )
                    
                    print(f"\nExecuting batch #{batch_number}...")
                    results = action_manager.execute_queue(delay_between=True, save_progress=True)
                    
                    successful = sum(1 for r in results if r.success)
                    failed = len(results) - successful
                    total_unfollowed += successful
                    total_failed += failed
                    users_processed_in_page += len(current_batch)
                    
                    print(f"\nBatch #{batch_number} complete:")
                    print(f"  ✓ Unfollowed: {successful}")
                    print(f"  ✗ Failed: {failed}")
                    print(f"  Total unfollowed so far: {total_unfollowed}")
                    
                    if failed > 0 and stop_on_error:
                        print(f"\n✗ Stopping due to errors (stop_on_error is enabled)")
                        filtered_users = []
                        break
                    
                    if filtered_users and pause_between > 0:
                        print(f"\n⏸ Pausing {pause_between}s between batches...")
                        print("Press Ctrl+C to stop...")
                        try:
                            page.wait_for_timeout(pause_between * 1000)
                        except KeyboardInterrupt:
                            print("\n⚠ Stopped by user")
                            filtered_users = []
                            break
                
                next_max_id = following_data.get('next_max_id')
                if next_max_id:
                    if next_max_id != last_max_id:
                        last_max_id = next_max_id
                        pagination_attempts = 0
                        aggressive_null_retries = 0
                        print(f"\n➡ Moving to next page with max_id: {next_max_id}")
                        
                        if pause_between > 0:
                            print(f"\n⏸ Pausing {pause_between}s before loading next page...")
                            print("Press Ctrl+C to stop...")
                            try:
                                page.wait_for_timeout(pause_between * 1000)
                            except KeyboardInterrupt:
                                print("\n⚠ Stopped by user")
                                break
                        continue
                    else:
                        pagination_attempts += 1
                        if pagination_attempts >= max_pagination_attempts:
                            break
                else:
                    if aggressive_mode and aggressive_null_retries < aggressive_retries:
                        aggressive_null_retries += 1
                        print(f"\n⚠ AGGRESSIVE MODE: max_id is null but will retry ({aggressive_null_retries}/{aggressive_retries})")
                        
                        if pause_between > 0:
                            print(f"\n⏸ Pausing {pause_between}s before aggressive retry...")
                            page.wait_for_timeout(pause_between * 1000)
                        continue
                    else:
                        if aggressive_mode:
                            print(f"\n✓ Max aggressive retries reached ({aggressive_retries})")
                        else:
                            print(f"\n✓ No more pages available (no next_max_id)")
                        break
                
                if following_data.get('big_list') == False:
                    print(f"\n✓ Reached end of following list (big_list is False)")
                    break
            
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
            
            BrowserManager.close_page(username, page)
            print('Tab closed (browser remains open for other operations)')
            
        except KeyboardInterrupt:
            print("\n\n⚠ Operation interrupted by user")
            print(f"Unfollowed {total_unfollowed} users before stopping")
        except Exception as e:
            print(f'Error in massive_unfollow: {e}')
    
    def explore_automation(self, playwright):
        from ig_scraper.automation.explore_api_db import ExploreAPIAutomationDB
        
        try:
            username = self.select_profile()
            if not username:
                return
            
            print('Getting browser page...')
            try:
                page = BrowserManager.get_new_page(username, self.session_manager, playwright)
            except ProfileLockError as e:
                print(f'\n❌ {e}')
                print(f'Profile @{username} is already open in another window.')
                print('Please close the other window or choose a different profile.')
                return
            
            print('Loading Instagram...')
            page.goto(Endpoints.BASE_URL, wait_until='domcontentloaded')
            page.wait_for_timeout(3000)
            
            automation = ExploreAPIAutomationDB(page, self.session_manager, username)
            
            if not automation.verify_login():
                print("\n✗ Login verification failed. Please login again (option 1)")
                BrowserManager.close_page(username, page)
                return
            
            print('✓ Login verified!')
            
            print("\n" + "="*50)
            print("EXPLORE AUTOMATION OPTIONS")
            print("="*50)
            print("1. General explore (trending)")
            print("2. Search specific topic")
            print("="*50)
            
            explore_choice = input("Select option (1-2): ")
            search_query = None
            
            if explore_choice == '2':
                search_query = input("Enter search query (e.g. 'news', 'tech', 'food'): ").strip()
                if not search_query:
                    print("No query provided, using general explore")
            
            stats = automation.run_automation(search_query)
            
            print('\nWaiting 10 seconds before closing tab...')
            page.wait_for_timeout(10000)
            
            BrowserManager.close_page(username, page)
            print('Tab closed')
            
        except KeyboardInterrupt:
            print("\n\n⚠ Operation interrupted by user")
            if 'page' in locals():
                BrowserManager.close_page(username, page)
        except Exception as e:
            print(f'Error in explore automation: {e}')
            if 'page' in locals():
                BrowserManager.close_page(username, page)
    
    def view_screenshots(self):
        screenshots_dir = Path('/app/screenshots')  # Always Docker path
        
        if not screenshots_dir.exists():
            print("No screenshots directory found")
            return
        
        screenshots = sorted(screenshots_dir.glob('*.png'), key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not screenshots:
            print("No screenshots found")
            return
        
        print(f"\n📸 SCREENSHOTS ({len(screenshots)} files)")
        print("="*60)
        
        for i, screenshot in enumerate(screenshots[:20], 1):
            size_kb = screenshot.stat().st_size / 1024
            print(f"{i:2}. {screenshot.name} ({size_kb:.1f} KB)")
        
        print("="*60)
        print(f"Screenshots directory: {screenshots_dir}")
        
        print("\nTo view screenshots from host:")
        print("docker cp instagram_scraper:/app/screenshots ./")