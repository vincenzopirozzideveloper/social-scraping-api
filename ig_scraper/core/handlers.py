from playwright.sync_api import TimeoutError, Page
import json
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
from ig_scraper.api import Endpoints
from ig_scraper.config.env_config import CREDENTIALS_PATH


def handle_cookie_banner(page: Page) -> bool:
    try:
        print('Looking for cookie banner...')
        page.wait_for_selector('button._a9--._ap36._asz1', timeout=5000)
        page.click('button._a9--._ap36._asz1')
        print('✓ Cookie banner closed')
        return True
    except TimeoutError:
        print('Cookie banner not found')
        return False


def handle_2fa_with_backup(page: Page, creds: Dict[str, Any]) -> bool:
    try:
        print('\n' + '='*50)
        print('HANDLING 2FA WITH BACKUP CODES')
        print('='*50)
        
        backup_codes = creds.get('backup-code', creds.get('backup_code', []))
        
        if isinstance(backup_codes, str):
            backup_codes = [backup_codes]
        
        if not backup_codes:
            print('✗ No backup codes found in credentials.json')
            print('  Please add "backup-code" field to credentials.json')
            return False
        
        print(f'→ Found {len(backup_codes)} backup code(s) to try')
        
        page.wait_for_timeout(2000)
        
        backup_button_selector = 'button:has-text("Try Another Way"), button:has-text("Use Backup Code")'
        try:
            page.wait_for_selector(backup_button_selector, timeout=5000)
            page.click(backup_button_selector)
            print('✓ Clicked on backup code option')
            page.wait_for_timeout(1000)
        except:
            print('→ Backup code option not found, might already be on backup page')
        
        specific_button = 'div.x889kno.xyri2b.x1a8lsjc.x1c1uobl > form > div:nth-child(5) > button'
        try:
            if page.query_selector(specific_button):
                page.click(specific_button)
                print('✓ Switched to backup code entry')
                page.wait_for_timeout(1000)
        except:
            pass
        
        for i, code in enumerate(backup_codes, 1):
            print(f'\n→ Attempt {i}/{len(backup_codes)}: Using code {code[:4]}****')
            
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
                        input_field.click()
                        page.keyboard.press('Control+A')
                        page.keyboard.press('Delete')
                        page.fill(selector, code)
                        print(f'  ✓ Code entered')
                        filled = True
                        break
                except:
                    continue
            
            if not filled:
                print('  ✗ Could not find backup code input field')
                continue
            
            try:
                with page.expect_response("**/accounts/login/ajax/two_factor/**", timeout=10000) as response_info:
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
                
                verification_response = response_info.value
                response_data = verification_response.json()
                
                if response_data.get('authenticated') or response_data.get('status') == 'ok':
                    print('  ✓ SUCCESS! Backup code accepted')
                    return True
                elif response_data.get('error_type') in ['invalid_verification_code', 'invalid_verficaition_code']:
                    print(f'  ✗ Invalid code: {response_data.get("message", "Code rejected")}')
                    
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
                    page.wait_for_timeout(2000)
                    if page.query_selector('svg[aria-label="Profile"]') or page.query_selector('svg[aria-label="Home"]'):
                        print('  ✓ Login successful despite unexpected response!')
                        return True
                    
            except Exception as e:
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


def perform_login(page: Page) -> Tuple[str, Optional[Dict[str, Any]]]:
    try:
        creds_path = CREDENTIALS_PATH if CREDENTIALS_PATH.exists() else Path('credentials.json')
        with open(creds_path, 'r') as f:
            creds = json.load(f)
        
        print('Filling username field...')
        page.fill('input[name="username"]', creds['email'])
        print('✓ Username entered')
        
        print('Filling password field...')
        page.fill('input[name="password"]', creds['password'])
        print('✓ Password entered')
        
        print('Submitting login form and waiting for response...')
        
        with page.expect_response(Endpoints.LOGIN_AJAX) as response_info:
            page.click('#loginForm button[type="submit"]')
        
        login_response = response_info.value
        print(f'✓ Login response intercepted (Status: {login_response.status})')
        
        try:
            data = login_response.json()
            print('\n' + '='*50)
            print('LOGIN RESPONSE:')
            print(json.dumps(data, indent=2))
            print('='*50 + '\n')
        except Exception as e:
            print(f'Warning: Could not parse response body: {e}')
            data = {'status': 'ok' if login_response.status == 200 else 'fail', 'authenticated': login_response.status == 200}
        
        if data.get('authenticated') and data.get('status') == 'ok':
            print('✓ Login successful!')
            user_id = data.get('userId')
            if user_id:
                print(f'  User ID: {user_id}')
            return 'success', data
        elif data.get('two_factor_required'):
            print('⚠ Two-factor authentication required')
            
            if creds.get('backup-code') or creds.get('backup_code'):
                print('→ Attempting to use backup code...')
                if handle_2fa_with_backup(page, creds):
                    print('✓ 2FA completed successfully with backup code!')
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


def click_post_login_button(page: Page) -> bool:
    try:
        print('\nLooking for post-login button...')
        
        page.wait_for_timeout(2000)
        
        button_selector = '#mount_0_0_yS > div > div > div.x9f619.x1n2onr6.x1ja2u2z > div > div > div.x78zum5.xdt5ytf.x1t2pt76.x1n2onr6.x1ja2u2z.x10cihs4 > div.html-div.xdj266r.x14z9mp.xat24cr.x1lziwak.xexx8yu.xyri2b.x18d9i69.x1c1uobl.x9f619.x16ye13r.xvbhtw8.x78zum5.x15mokao.x1ga7v0g.x16uus16.xbiv7yw.x1uhb9sk.x1plvlek.xryxfnj.x1c4vz4f.x2lah0s.x1q0g3np.xqjyukv.x1qjc9v5.x1oa3qoh.x1qughib > div.xvc5jky.xh8yej3.x10o80wk.x14k21rp.x17snn68.x6osk4m.x1porb0y.x8vgawa > section > main > div > div > section > div > button'
        
        button = page.query_selector(button_selector)
        
        if not button:
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