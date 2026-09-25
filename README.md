# EMAS 3 UI Web Scraper

An open-source Python scraper for [emas3.ui.ac.id](https://emas3.ui.ac.id) (Universitas Indonesia Moodle LMS) to extract enrolled courses, weekly materials, assignments, and upcoming deadlines.

## Features

- **Authentication via Session Cookie:** Bypasses complex SSO/MFA redirects by using the active `MoodleSession` cookie.
- **Course Discovery:** Scrapes all enrolled courses and IDs from the dashboard.
- **Course Content Extractor:** Parses weekly sections, assignments, lecture slides/files, quizzes, and external links.
- **Deadlines & Calendar:** Extracts upcoming deadlines directly from the Moodle calendar.
- **Exporting:** Supports exporting scraped data directly to JSON.
- **Politeness / Rate Limiting:** Built-in delays to respect campus servers.

## Quick Setup

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Authentication:**
   - Log into [emas3.ui.ac.id](https://emas3.ui.ac.id) in your browser.
   - Open DevTools (`F12`) -> **Application** (or **Storage**) -> **Cookies** -> `https://emas3.ui.ac.id`.
   - Copy the value of `MoodleSession`.
   - Copy `.env.example` to `.env` and paste your cookie:
     ```bash
     cp .env.example .env
     ```

## Usage

- **Interactive run (prompts for cookie if not in `.env`):**
  ```bash
  python emas_scraper.py
  ```

- **Pass cookie directly via CLI:**
  ```bash
  python emas_scraper.py --cookie "YOUR_COOKIE"
  ```

- **Fetch upcoming deadlines only:**
  ```bash
  python emas_scraper.py --deadlines
  ```

- **Scrape a specific course in detail:**
  ```bash
  python emas_scraper.py --course-id 12345
  ```

- **Scrape all enrolled courses and export to JSON:**
  ```bash
  python emas_scraper.py --all --export emas_data.json
  ```
