import streamlit as st
import requests
import re
import time
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from io import BytesIO

st.set_page_config(page_title="Custom Business Scraper", layout="wide")

st.title("Custom Business Scraper")

category_url = st.text_input(
    "Category page URL",
    "https://vadodara.idbf.in/academy"
)

max_listings = st.number_input(
    "Maximum listings to scrape",
    min_value=1,
    max_value=1000,
    value=100,
    step=10
)

delay = st.number_input(
    "Delay between requests",
    min_value=0.0,
    max_value=5.0,
    value=1.0,
    step=0.5
)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()

def get_html(url):
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            return response.text, response.status_code
        return "", response.status_code
    except Exception:
        return "", 0

def extract_email(text):
    emails = re.findall(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        text
    )
    return ", ".join(sorted(set(emails)))

def extract_phone(text):
    phones = re.findall(
        r"(?:\+91[\s-]?)?[6-9]\d{9}|\b0[0-9]{2,5}[\s-]?[0-9]{6,8}\b",
        text
    )
    return ", ".join(sorted(set(clean_text(p) for p in phones)))

def extract_website(soup, page_url):
    page_domain = urlparse(page_url).netloc.replace("www.", "")

    ignore = [
        "facebook.com",
        "instagram.com",
        "linkedin.com",
        "youtube.com",
        "twitter.com",
        "x.com",
        "whatsapp.com",
        "wa.me",
        "google.com"
    ]

    for a in soup.find_all("a", href=True):
        href = urljoin(page_url, a["href"])
        domain = urlparse(href).netloc.replace("www.", "").lower()

        if domain and domain != page_domain:
            if not any(bad in domain for bad in ignore):
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

def extract_name(soup):
    for selector in ["h1", "h2", ".entry-title", ".post-title", ".listing-title", ".business-title"]:
        item = soup.select_one(selector)
        if item:
            name = clean_text(item.get_text(" "))
            if len(name) > 2:
                return name
    return ""

def extract_category(soup, fallback_url):
    category_parts = []

    for selector in [".breadcrumb", ".breadcrumbs", ".category", ".cat-links", "[rel='category tag']"]:
        for item in soup.select(selector):
            text = clean_text(item.get_text(" "))
            if text:
                category_parts.append(text)

    if category_parts:
        return " | ".join(sorted(set(category_parts)))

    path = urlparse(fallback_url).path.strip("/")
    if path:
        return path.split("/")[0].replace("-", " ").title()

    return ""

def extract_address(text):
    patterns = [
        r"Address[:\s]+(.{10,300}?)(?:Phone|Mobile|Email|Website|Contact|$)",
        r"(.{10,250}(Vadodara|Baroda|Gujarat|390\d{3}).{0,150})"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return clean_text(match.group(1))[:300]

    return ""

def find_listing_links(category_url, html):
    soup = BeautifulSoup(html, "html.parser")
    root_domain = urlparse(category_url).netloc.replace("www.", "")
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
        "whatsapp"
    ]

    for a in soup.find_all("a", href=True):
        href = urljoin(category_url, a["href"])
        parsed = urlparse(href)
        domain = parsed.netloc.replace("www.", "")

        if domain != root_domain:
            continue

        if any(word in href.lower() for word in skip_words):
            continue

        if href.rstrip("/") == category_url.rstrip("/"):
            continue

        link_text = clean_text(a.get_text(" "))

        if len(link_text) > 1:
            links.append(href.rstrip("/"))

    return sorted(set(links))

def scrape_business_page(url, category_name):
    html, status = get_html(url)

    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    text = clean_text(soup.get_text(" "))

    socials = extract_socials(soup, url)

    return {
        "Name": extract_name(soup),
        "Category": category_name or extract_category(soup, url),
        "Address": extract_address(text),
        "Contact Number": extract_phone(text),
        "Phone Number": extract_phone(text),
        "Email Address": extract_email(text),
        "Web Address": extract_website(soup, url),
        "Facebook": socials["Facebook"],
        "Instagram": socials["Instagram"],
        "LinkedIn": socials["LinkedIn"],
        "YouTube": socials["YouTube"],
        "X / Twitter": socials["X / Twitter"],
        "Source URL": url,
        "Status": "Auto extracted. Verify manually."
    }

def convert_df_to_excel(df):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Business Data")

    return output.getvalue()

if st.button("Start Scraping"):
    st.write("Opening category page...")

    html, status = get_html(category_url)

    st.write("Page status:", status)
    st.write("HTML length:", len(html))

    if not html:
        st.error("Could not open the page. The website may be blocking the scraper.")
        st.stop()

    category_name = urlparse(category_url).path.strip("/").replace("-", " ").title()

    listing_links = find_listing_links(category_url, html)

    st.write("Listing links found:", len(listing_links))

    if len(listing_links) == 0:
        st.warning("No listing links found. This page may load data using JavaScript or may block scraping.")
        st.stop()

    listing_links = listing_links[:max_listings]

    rows = []
    progress = st.progress(0)
    status_box = st.empty()

    for i, link in enumerate(listing_links, start=1):
        status_box.write(f"Scraping {i}/{len(listing_links)}: {link}")

        row = scrape_business_page(link, category_name)

        if row:
            has_data = (
                row["Name"]
                or row["Address"]
                or row["Contact Number"]
                or row["Email Address"]
                or row["Web Address"]
            )

            if has_data:
                rows.append(row)

        progress.progress(i / len(listing_links))
        time.sleep(delay)

    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.drop_duplicates(subset=["Name", "Contact Number", "Source URL"])

    st.success(f"Done. Found {len(df)} records.")

    st.dataframe(df, use_container_width=True)

    excel_file = convert_df_to_excel(df)

    st.download_button(
        label="Download Excel",
        data=excel_file,
        file_name="business_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
