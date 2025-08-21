# Project: Instagram Scraper with Playwright

## Overview
This project is an Instagram automation tool built with Playwright in Python. It provides a console-based interface for browser automation and Instagram interactions with professional-grade request interception.

## Project Architecture

### Folder Structure
```
scraper-3/
├── main.py                 # Main entry point with CLI menu
├── credentials.json        # Login credentials (gitignored)
├── requirements.txt        # Python dependencies (playwright)
├── ig_scraper/            # Main package
│   ├── api/              # API endpoints and network logic
│   │   └── endpoints.py  # Centralized Instagram endpoints
│   ├── auth/             # Authentication module (future)
│   ├── cli/              # CLI interface (future)
│   └── browser/          # Browser automation (future)
├── networks/              # Network request/response examples
│   └── login/            # Login flow examples
└── .docs/                # Reference documentation
```

### Current Features
1. **Professional Login Flow**
   - Uses `expect_response` pattern for clean request interception
   - Handles multiple login states: success, 2FA, checkpoint, failed
   - Intercepts and displays login API responses
   - Post-login button detection and clicking

2. **Request Interception**
   - Clean API endpoint management via `Endpoints` class
   - Professional response handling without race conditions
   - Structured return values with status and data

3. **Browser Automation**
   - Cookie banner handling
   - Non-headless browser for visual debugging
   - Signal handling for clean exits (CTRL+C)
   - Timeout management and error handling

## Code Style Guidelines
- **Language**: All code, comments, and console output must be in English
- **Structure**: Minimal, functional approach without boilerplate
- **Error Handling**: Use try/except blocks with clear error messages
- **Console Feedback**: Provide step-by-step feedback for user actions
- **Imports**: Use absolute imports from ig_scraper package

## Important Restrictions
- **NO TESTING**: Do not run `python main.py` or any Python scripts - no environment is set up
- **NO AUTO-COMMITS**: Only create commits when explicitly requested by the user
- **Testing**: User will test manually and provide feedback

## Git Workflow
- Always work on `development` branch
- Create commits only when explicitly requested
- Keep commit messages concise and descriptive
- No references to AI assistance in commits
- Use present tense in commit messages

## Development Workflow
1. Make code changes as requested
2. Wait for user to test manually
3. Create commits only when user asks
4. Keep changes atomic and focused