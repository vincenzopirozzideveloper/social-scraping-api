from typing import Optional
from ig_scraper.auth import SessionManager
from ig_scraper.browser import BrowserManager
from .commands import Commands


class Menu:
    def __init__(self):
        self.session_manager = SessionManager()
        self.commands = Commands(self.session_manager)
        self.playwright = None
    
    def initialize_playwright(self):
        from playwright.sync_api import sync_playwright
        self.playwright = sync_playwright().start()
        
        import atexit
        def cleanup():
            BrowserManager.close_all()
            if self.playwright:
                self.playwright.stop()
        atexit.register(cleanup)
    
    def show_active_browsers(self):
        active = BrowserManager.get_active_profiles()
        if active:
            print("\n📱 Active browsers:")
            for profile in active:
                print(f"  → @{profile['username']}: {profile['tabs']} tabs")
    
    def display_menu(self) -> str:
        self.show_active_browsers()
        
        print('\n' + '='*50)
        print('INSTAGRAM SCRAPER')
        print('='*50)
        print('1: Login (new or add profile)')
        print('2: Login with saved session')
        print('3: Clear saved sessions')
        print('4: First Automation (GraphQL test)')
        print('5: Scrape Following')
        print('6: Explore Search')
        print('7: Massive Unfollow (ALL)')
        print('8: Explore Automation (Like & Comment)')
        print('9: Scrape Followers')
        print('10: Browser Status')
        print('11: Close All Browsers')
        print('S: View Screenshots')
        print('0: Exit')
        print('='*50)
        
        return input('> ')
    
    def run(self):
        self.initialize_playwright()
        
        while True:
            try:
                choice = self.display_menu()
                
                if choice == '0':
                    break
                elif choice == '1':
                    self.commands.login_new(self.playwright)
                elif choice == '2':
                    self.commands.login_saved(self.playwright)
                elif choice == '3':
                    self.commands.clear_sessions()
                elif choice == '4':
                    self.commands.first_automation(self.playwright)
                elif choice == '5':
                    self.commands.scrape_following(self.playwright)
                elif choice == '6':
                    self.commands.scrape_explore(self.playwright)
                elif choice == '7':
                    self.commands.massive_unfollow(self.playwright)
                elif choice == '8':
                    self.commands.explore_automation(self.playwright)
                elif choice == '9':
                    self.commands.scrape_followers(self.playwright)
                elif choice == '10':
                    BrowserManager.status()
                elif choice == '11':
                    print("\nClosing all browsers...")
                    BrowserManager.close_all()
                    print("✓ All browsers closed")
                elif choice.upper() == 'S':
                    self.commands.view_screenshots()
                else:
                    print("Invalid choice. Please try again.")
                    
            except KeyboardInterrupt:
                print("\n↩ Returning to menu...")
                continue