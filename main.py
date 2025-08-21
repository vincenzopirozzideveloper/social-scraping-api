from playwright.sync_api import sync_playwright, TimeoutError
import signal
import sys

def signal_handler(sig, frame):
    print('\nUscita pulita.')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def gestisci_cookie_banner(page):
    try:
        page.wait_for_selector('button:has-text("Consenti solo i cookie essenziali")', timeout=5000)
        page.click('button:has-text("Consenti solo i cookie essenziali")')
        return True
    except TimeoutError:
        try:
            page.wait_for_selector('button:has-text("Rifiuta i cookie facoltativi")', timeout=2000)
            page.click('button:has-text("Rifiuta i cookie facoltativi")')
            return True
        except TimeoutError:
            return False

def main():
    while True:
        scelta = input('\n1: Login\n0: Exit\n> ')
        if scelta == '0':
            break
        elif scelta == '1':
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                page.goto('https://www.instagram.com/accounts/login/')
                
                if gestisci_cookie_banner(page):
                    print('Cookie banner chiuso.')
                
                input('Premi invio per chiudere il browser...')
                browser.close()

if __name__ == '__main__':
    main()