"""
EMAS 3 UI (emas3.ui.ac.id) Open-Source Web Scraper
Author: Farrell & Assistant
Description:
    A Python-based scraper for extracting enrolled courses, weekly materials,
    assignments, and upcoming deadlines from EMAS Universitas Indonesia (Moodle-based).
"""

import os
import sys
import time
import json
import argparse
from urllib.parse import urljoin, parse_qs, urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("[ERROR] Required packages not found. Please run:")
    print("        pip install requests beautifulsoup4")
    sys.exit(1)

# Optional python-dotenv support
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_URL = "https://emas3.ui.ac.id"


class EmasScraper:
    def __init__(self, session_cookie: str, delay: float = 1.0):
        """
        Initialize the EMAS scraper session.
        :param session_cookie: The value of the 'MoodleSession' cookie.
        :param delay: Politeness delay in seconds between HTTP requests.
        """
        self.session = requests.Session()
        self.session_cookie = session_cookie.strip()
        self.delay = delay

        # Configure session cookie
        self.session.cookies.set("MoodleSession", self.session_cookie, domain="emas3.ui.ac.id")

        # Set standard browser headers to avoid basic bot detection
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
            "Referer": BASE_URL,
        })

    def _get(self, url: str) -> requests.Response:
        """Helper to send rate-limited GET requests."""
        if not url.startswith("http"):
            url = urljoin(BASE_URL, url)
        
        time.sleep(self.delay)
        response = self.session.get(url, allow_redirects=True)
        response.raise_for_status()
        return response

    def check_auth(self) -> dict:
        """
        Verifies if the MoodleSession cookie is valid.
        Returns user info dictionary if authenticated, raises PermissionError otherwise.
        """
        res = self._get(f"{BASE_URL}/my/")
        soup = BeautifulSoup(res.text, "html.parser")

        # Check if redirected to login page
        if "login" in res.url.lower() or soup.find("input", {"id": "username"}):
            raise PermissionError(
                "Invalid or expired MoodleSession cookie.\n"
                "Please log in to https://emas3.ui.ac.id in your browser, "
                "copy your 'MoodleSession' cookie, and update your configuration."
            )

        # Extract logged in user's name
        user_name = "Authenticated Student"
        user_meta = soup.select_one(".userbutton .usertext, .usertext, .logininfo a")
        if user_meta:
            user_name = user_meta.get_text(strip=True)

        return {
            "status": "authenticated",
            "user_name": user_name
        }

    def get_enrolled_courses(self) -> list:
        """
        Scrapes enrolled courses from the Moodle dashboard (/my/).
        """
        res = self._get(f"{BASE_URL}/my/")
        soup = BeautifulSoup(res.text, "html.parser")

        courses = []
        seen_ids = set()

        # Find course links across different Moodle themes (cards, overview lists)
        course_anchors = soup.select("a[href*='/course/view.php?id=']")

        for a in course_anchors:
            href = a.get("href", "")
            title = a.get_text(strip=True)

            parsed = urlparse(href)
            query_params = parse_qs(parsed.query)
            course_id = query_params.get("id", [None])[0]

            # Filter out utility links or empty titles
            if not course_id or course_id in seen_ids or not title:
                continue

            # Ignore generic navigation anchors
            if title.lower() in ["view course", "course", "enter", "grades"]:
                continue

            seen_ids.add(course_id)
            courses.append({
                "id": course_id,
                "title": title,
                "url": f"{BASE_URL}/course/view.php?id={course_id}"
            })

        return courses

    def get_course_details(self, course_id_or_url: str) -> dict:
        """
        Scrapes weekly topics/sections, resources, and assignments for a course.
        """
        if str(course_id_or_url).isdigit():
            url = f"{BASE_URL}/course/view.php?id={course_id_or_url}"
        else:
            url = course_id_or_url

        res = self._get(url)
        soup = BeautifulSoup(res.text, "html.parser")

        # Course Title
        page_title = soup.select_one(".page-header-headings h1, h1.h2")
        course_name = page_title.get_text(strip=True) if page_title else "Course " + str(course_id_or_url)

        sections = []

        # Moodle organizes content into <li class="section ..."> or <div class="course-section">
        section_elements = soup.select("li.section, div.course-section, ul.weeks > li, ul.topics > li")

        for s_idx, sec in enumerate(section_elements, 1):
            name_el = sec.select_one(".sectionname, .section-title, h3.sectionname")
            section_title = name_el.get_text(strip=True) if name_el else f"Section {s_idx}"

            activities = []
            for act in sec.select("li.activity"):
                # Clean up accessibility hidden labels like "Assignment" or "File"
                for hidden in act.select(".accesshide, .sr-only"):
                    hidden.decompose()

                link_el = act.select_one("a.aalink, a")
                name_el = act.select_one(".instancename") or link_el

                if not link_el or not name_el:
                    continue

                act_title = name_el.get_text(strip=True)
                act_url = link_el.get("href", "")

                # Detect activity type via CSS class (modtype_assign, modtype_resource, etc.)
                classes = " ".join(act.get("class", []))
                act_type = "other"
                if "mod_assign" in classes:
                    act_type = "assignment"
                elif "mod_resource" in classes:
                    act_type = "file/resource"
                elif "mod_quiz" in classes:
                    act_type = "quiz"
                elif "mod_forum" in classes:
                    act_type = "forum"
                elif "mod_url" in classes:
                    act_type = "external_link"

                activities.append({
                    "type": act_type,
                    "title": act_title,
                    "url": act_url
                })

            if activities:
                sections.append({
                    "section": section_title,
                    "activities": activities
                })

        return {
            "course_title": course_name,
            "url": url,
            "sections": sections
        }

    def get_upcoming_deadlines(self) -> list:
        """
        Scrapes the upcoming events directly from Moodle's calendar view.
        """
        calendar_url = f"{BASE_URL}/calendar/view.php?view=upcoming"
        res = self._get(calendar_url)
        soup = BeautifulSoup(res.text, "html.parser")

        events = []
        for item in soup.select(".event[data-event-id]"):
            title_el = item.select_one("h3")
            date_el = item.select_one("div.row, div.col-11")
            course_el = item.select_one(".course-name, .course")
            link_el = item.select_one("a[href*='/mod/']")

            if title_el:
                events.append({
                    "title": title_el.get_text(strip=True),
                    "due_date": date_el.get_text(strip=True) if date_el else "Unknown Date", 
                    "course": course_el.get_text(strip=True) if course_el else "General",
                    "url": link_el.get("href", "") if link_el else ""
                })

        return events


def prompt_for_cookie() -> str:
    """Prompts the user interactively to paste their MoodleSession cookie."""
    print("=" * 60)
    print("  EMAS 3 UI - Authentication Required")
    print("=" * 60)
    print("1. Open Chrome/Firefox and log in to: https://emas3.ui.ac.id")
    print("2. Press F12 -> Go to 'Application' (or 'Storage') -> 'Cookies'")
    print("3. Click 'https://emas3.ui.ac.id' and copy the value of 'MoodleSession'")
    print("=" * 60)
    cookie = input("Paste your MoodleSession cookie value here: ").strip()
    return cookie


def main():
    parser = argparse.ArgumentParser(
        description="Open Source Web Scraper for emas3.ui.ac.id"
    )
    parser.add_argument("--cookie", help="MoodleSession cookie value")
    parser.add_argument("--course-id", help="Scrape content for a specific course ID")
    parser.add_argument("--deadlines", action="store_true", help="Fetch upcoming assignment deadlines")
    parser.add_argument("--export", help="Save scraped results to a JSON file (e.g. emas_output.json)")
    parser.add_argument("--all", action="store_true", help="Scrape all enrolled courses and their sections")

    args = parser.parse_args()

    # Determine session cookie
    cookie = args.cookie or os.getenv("MOODLE_SESSION")
    if not cookie:
        cookie = prompt_for_cookie()

    if not cookie:
        print("[!] No cookie provided. Exiting.")
        sys.exit(1)

    print("\n[*] Initializing EMAS Scraper...")
    scraper = EmasScraper(session_cookie=cookie)

    # 1. Verify authentication
    try:
        auth_info = scraper.check_auth()
        print(f"[+] Login successful! Logged in as: {auth_info['user_name']}\n")
    except PermissionError as err:
        print(f"[!] Authentication failed: {err}")
        sys.exit(1)

    result_data = {
        "user": auth_info["user_name"],
        "courses": [],
        "upcoming_deadlines": []
    }

    # 2. Upcoming deadlines
    if args.deadlines or not args.course_id:
        print("[*] Fetching upcoming deadlines / calendar events...")
        try:
            deadlines = scraper.get_upcoming_deadlines()
            result_data["upcoming_deadlines"] = deadlines
            print(f"    Found {len(deadlines)} upcoming deadline(s):")
            for d in deadlines:
                print(f"    - [{d['due_date']}] {d['title']} ({d['course']})")
            print()
        except Exception as e:
            print(f"    [!] Could not fetch deadlines: {e}\n")

    # 3. Courses
    print("[*] Fetching enrolled courses...")
    courses = scraper.get_enrolled_courses()
    result_data["courses"] = courses
    print(f"    Found {len(courses)} enrolled course(s):")
    for idx, c in enumerate(courses, 1):
        print(f"    {idx}. [{c['id']}] {c['title']}")
    print()

    # 4. Scrape course details if requested
    if args.course_id:
        print(f"[*] Scraping details for Course ID: {args.course_id}...")
        course_details = scraper.get_course_details(args.course_id)
        result_data["course_details"] = course_details

        print(f"\n--- {course_details['course_title']} ---")
        for s in course_details["sections"]:
            print(f"\nSection: {s['section']}")
            for a in s["activities"]:
                print(f"  [{a['type']}] {a['title']}")
                print(f"    URL: {a['url']}")

    elif args.all:
        print("[*] Scraping details for all enrolled courses (this may take a moment)...")
        all_details = []
        for c in courses:
            print(f"    Fetching: {c['title']}...")
            details = scraper.get_course_details(c["id"])
            all_details.append(details)
        result_data["detailed_courses"] = all_details

    # 5. Export results
    if args.export:
        output_file = args.export
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)
        print(f"\n[+] Scraped data exported successfully to: {output_file}")


if __name__ == "__main__":
    main()
