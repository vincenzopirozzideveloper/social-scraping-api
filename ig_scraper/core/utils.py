import signal
import sys
import os
import subprocess
from pathlib import Path


def signal_handler(sig, frame):
    print('\n\n🛑 INTERRUPT DETECTED - Force cleaning...')
    
    print('  → Killing browser processes...')
    subprocess.run(['pkill', '-9', '-f', 'chrome'], capture_output=True)
    subprocess.run(['pkill', '-9', '-f', 'chromium'], capture_output=True)
    
    print('  → Cleaning lock files...')
    try:
        lock_files = Path('/var/www/app/browser_sessions').glob('*/.lock')
        for lock_file in lock_files:
            try:
                lock_file.unlink()
                print(f'    ✓ Removed lock: {lock_file.parent.name}')
            except:
                pass
    except:
        subprocess.run(['find', '/var/www/app/browser_sessions', '-name', '.lock', '-delete'], capture_output=True)
    
    try:
        from ig_scraper.browser import BrowserManager
        BrowserManager._instances.clear()
        BrowserManager._locks.clear()
        BrowserManager._lock_files.clear()
        print('  → Browser manager cleaned')
    except:
        pass
    
    print('\n✓ Cleanup complete. Restarting...\n')
    os.execv(sys.executable, ['python3'] + sys.argv)


def setup_signal_handler():
    signal.signal(signal.SIGINT, signal_handler)