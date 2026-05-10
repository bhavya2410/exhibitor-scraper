import re
import time
import sys
import subprocess
from io import BytesIO
from urllib.parse import urljoin, urlparse, quote_plus

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


st.set_page_config(page_title="Custom Business Scraper", layout="wide")
st.title("Custom Business Scraper")


@st.cache_resource
def install_playwright_browser():
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=False
    )


install_playwright_browser()


category_url = st.text_input(
    "Category page URL",
    "https://vadodara.idbf.in/academy"
)

max_listings = st.number_input(
    "Maximum listings to scrape",
    min_value=1,
    max_value=500,
    value=50,
    step=10
)

delay = st.number_input(
    "Delay between pages",
    min_value=0.0,
    max_value=5.0,
    value=1.0,
    step=0.5
)

use_enrichment = st.checkbox(
    "Search website/web if data is missing",
    value=True
)


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def get_domain(url):
    return urlparse(url).netloc.lower().replace("www.", "")


def extract_email(text):
    emails = re.findall(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text
    )
    return ", ".join(sorted(set(email.lower() for email in emails))[:10])


def extract_phone(text):
    phones = re.findall(
        r"(?:\+91[\s-]?)?[6-9]\d{9}|\b0[0-9]{2,5}[\s-]?[0-9]{6,8}\b",
        text
    )
    return ", ".join(sorted(set(clean_text(phone) for phone in phones))[:10])


def extract_name(soup):
    selectors = [
        "h1",
        "h2",
        ".entry-title",
        ".post-title",
        ".listing-title",
        ".business-title"
    ]

    for selector in selectors:
        item = soup.select_one(selector)
        if item:
            name = clean_text(item.get_text(" "))
            if len(name) > 2:
                return name[:200]

    if soup.title:
        return clean_text(soup.title.get_text(" "))[:200]

    return ""


def extract_address(text):
    patterns = [
        r"Address[:\s]+(.{10,350}?)(?:Phone|Mobile|Email|Website|Contact|$)",
        r"(.{10,250}(Vadodara|Baroda|Gujarat|390\d{3}).{0,180})"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return clean_text(match.group(1))[:350]

    return ""


def extract_website(soup, page_url):
    page_domain = get_domain(page_url)

    ignore = [
        "facebook",
        "instagram",
        "linkedin",
        "youtube",
        "twitter",
        "x.com",
        "google",
        "wa.me",
        "whatsapp"
    ]

    for a in soup.find_all("a", href=True):
        href = urljoin(page_url, a["href"])
        domain = get_domain(href)

        if domain and domain != page_domain:
            if not any(item in domain for item in ignore):
                return href

    return ""


def extract_socials(soup, page_url):
    socials = {
        "Facebook": "",
        "Instagram": "",
        "LinkedIn": "",
        "YouTube": "",
        "X / Twitter": ""
    }

    for a in soup.find_all("a", href=True):
        href = urljoin(page_url, a["href"])
        low = href.lower()

        if "facebook.com" in low and not socials["Facebook"]:
            socials["Facebook"] = href
        elif "instagram.com" in low and not socials["Instagram"]:
            socials["Instagram"] = href
        elif "linkedin.com" in low and not socials["LinkedIn"]:
            socials["LinkedIn"] = href
        elif "youtube.com" in low and not socials["YouTube"]:
            socials["YouTube"] = href
        elif ("twitter.com" in low or "x.com" in low) and not socials["X / Twitter"]:
            socials["X / Twitter"] = href

    return socials


def find_listing_links(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    root_domain = get_domain(base_url)
    links = []

    skip_words = [
        "login",
        "register",
        "privacy",
        "terms",
        "contact",
        "about",
        "facebook",
        "instagram",
        "linkedin",
        "youtube",
        "twitter",
        "whatsapp",
        "category"
    ]

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).rstrip("/")
        domain = get_domain(href)

        if domain != root_domain:
            continue

        if href == base_url.rstrip("/"):
            continue

        if any(word in href.lower() for word in skip_words):
            continue

        link_text = clean_text(a.get_text(" "))

        if len(link_text) > 1:
            links.append(href)

    return sorted(set(links))


def browser_get_html(page, url):
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(1)
        return page.content()
    except Exception:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(1)
            return page.content()
        except Exception:
            return ""


def scrape_business_html(html, page_url, category_name):
    soup = BeautifulSoup(html, "html.parser")
    text = clean_text(soup.get_text(" "))
    socials = extract_socials(soup, page_url)

    phone = extract_phone(text)

    return {
        "Name": extract_name(soup),
        "Category": category_name,
        "Address": extract_address(text),
        "Contact Number": phone,
        "Phone Number": phone,
        "Email Address": extract_email(text),
        "Web Address": extract_website(soup, page_url),
        "Facebook": socials["Facebook"],
        "Instagram": socials["Instagram"],
        "LinkedIn": socials["LinkedIn"],
        "YouTube": socials["YouTube"],
        "X / Twitter": socials["X / Twitter"],
        "Source URL": page_url,
        "Status": "Auto extracted. Verify manually."
    }


def merge_missing(old_value, new_value):
    if old_value and str(old_value).strip():
        return old_value
    return new_value


def search_duckduckgo(query):
    try:
        url = "https://duckduckgo.com/html/?q=" + quote_plus(query)
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=20)

        soup = BeautifulSoup(response.text, "html.parser")

        for a in soup.select("a.result__a"):
            href = a.get("href", "")
            if href.startswith("http"):
                return href
    except Exception:
        return ""

    return ""


def enrich_row(row, page):
    needs_help = not row["Email Address"] or not row["Contact Number"] or not row["Address"]

    if not needs_help:
        return row

    website = row["Web Address"]

    if not website and row["Name"]:
        query = f'{row["Name"]} {row["Category"]} Vadodara official website contact'
        website = search_duckduckgo(query)
        if website:
            row["Web Address"] = website

    if not website:
        return row

    pages_to_try = [
        website,
        urljoin(website, "/contact"),
        urljoin(website, "/contact-us"),
        urljoin(website, "/about"),
        urljoin(website, "/about-us")
    ]

    combined_text = ""

    for url in pages_to_try:
        html = browser_get_html(page, url)
        if html:
            soup = BeautifulSoup(html, "html.parser")
            combined_text += " " + clean_text(soup.get_text(" "))

    found_email = extract_email(combined_text)
    found_phone = extract_phone(combined_text)
    found_address = extract_address(combined_text)

    row["Email Address"] = merge_missing(row["Email Address"], found_email)
    row["Contact Number"] = merge_missing(row["Contact Number"], found_phone)
    row["Phone Number"] = merge_missing(row["Phone Number"], found_phone)
    row["Address"] = merge_missing(row["Address"], found_address)

    if found_email or found_phone or found_address:
        row["Status"] = "Auto extracted + enriched. Verify manually."

    return row


def convert_to_excel(df):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Business Data")

    return output.getvalue()


if st.button("Start Scraping"):
    category_name = urlparse(category_url).path.strip("/").replace("-", " ").title()

    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
        )

        st.write("Opening category page with browser...")
        category_html = browser_get_html(page, category_url)

        st.write("HTML length:", len(category_html))

        if len(category_html) < 1000:
            st.error("The website is not giving the real page to Streamlit Cloud. Try running locally or check if the site blocks cloud servers.")
            browser.close()
            st.stop()

        listing_links = find_listing_links(category_html, category_url)

        st.write("Listing links found:", len(listing_links))

        if not listing_links:
            st.error("No listing links found. This website may need custom link selectors.")
            browser.close()
            st.stop()

        listing_links = listing_links[:max_listings]

        progress = st.progress(0)
        status_box = st.empty()

        for index, link in enumerate(listing_links, start=1):
            status_box.write(f"Scraping {index}/{len(listing_links)}: {link}")

            html = browser_get_html(page, link)

            if html:
                row = scrape_business_html(html, link, category_name)

                if use_enrichment:
                    row = enrich_row(row, page)

                has_data = (
                    row["Name"]
                    or row["Address"]
                    or row["Contact Number"]
                    or row["Email Address"]
                    or row["Web Address"]
                )

                if has_data:
                    rows.append(row)

            progress.progress(index / len(listing_links))
            time.sleep(delay)

        browser.close()

    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.drop_duplicates(subset=["Name", "Contact Number", "Source URL"])

    st.success(f"Done. Found {len(df)} records.")
    st.dataframe(df, use_container_width=True)

    if not df.empty:
        excel_file = convert_to_excel(df)

        st.download_button(
            label="Download Excel",
            data=excel_file,
            file_name="business_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
