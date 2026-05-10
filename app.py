import streamlit as st
import pandas as pd
import re
import time
import subprocess
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from io import BytesIO
from playwright.sync_api import sync_playwright

st.set_page_config(page_title="Custom Business Scraper", layout="wide")
st.title("Custom Business Scraper")

category_url = st.text_input("Category page URL", "https://vadodara.idbf.in/academy")
max_listings = st.number_input("Maximum listings", 1, 500, 50)
delay = st.number_input("Delay between pages", 0.0, 5.0, 1.0)

@st.cache_resource
def install_playwright():
    subprocess.run(["playwright", "install", "chromium"], check=False)

install_playwright()

def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()

def extract_email(text):
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return ", ".join(sorted(set(emails)))

def extract_phone(text):
    phones = re.findall(r"(?:\+91[\s-]?)?[6-9]\d{9}|\b0[0-9]{2,5}[\s-]?[0-9]{6,8}\b", text)
    return ", ".join(sorted(set(clean_text(p) for p in phones)))

def extract_name(soup):
    for selector in ["h1", "h2", ".entry-title", ".post-title", ".listing-title", ".business-title"]:
        item = soup.select_one(selector)
        if item:
            text = clean_text(item.get_text(" "))
            if text:
                return text
    return ""

def extract_address(text):
    match = re.search(r"(.{10,250}(Vadodara|Baroda|Gujarat|390\d{3}).{0,150})", text, re.I)
    return clean_text(match.group(1)) if match else ""

def extract_website(soup, page_url):
    current_domain = urlparse(page_url).netloc.replace("www.", "")
    ignore = ["facebook", "instagram", "linkedin", "youtube", "twitter", "x.com", "google", "wa.me", "whatsapp"]

    for a in soup.find_all("a", href=True):
        href = urljoin(page_url, a["href"])
        domain = urlparse(href).netloc.replace("www.", "").lower()

        if domain and domain != current_domain and not any(x in domain for x in ignore):
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
    soup = BeautifulSoup(html, "lxml")
    root_domain = urlparse(base_url).netloc.replace("www.", "")
    links = []

    skip = ["login", "register", "privacy", "terms", "contact", "about"]

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).rstrip("/")
        domain = urlparse(href).netloc.replace("www.", "")

        if domain != root_domain:
            continue

        if href == base_url.rstrip("/"):
            continue

        if any(x in href.lower() for x in skip):
            continue

        text = clean_text(a.get_text(" "))
        if len(text) > 1:
            links.append(href)

    return sorted(set(links))

def scrape_page_with_browser(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        html = page.content()
        browser.close()
        return html

def scrape_business_page(url, category):
    html = scrape_page_with_browser(url)
    soup = BeautifulSoup(html, "lxml")
    text = clean_text(soup.get_text(" "))
    socials = extract_socials(soup, url)

    return {
        "Name": extract_name(soup),
        "Category": category,
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

def convert_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Business Data")
    return output.getvalue()

if st.button("Start Scraping"):
    st.write("Opening page with real browser...")

    html = scrape_page_with_browser(category_url)

    st.write("HTML length:", len(html))

    if len(html) < 1000:
        st.error("Still not getting the real page. Website may be blocking Streamlit Cloud.")
        st.stop()

    listing_links = find_listing_links(html, category_url)

    st.write("Listing links found:", len(listing_links))

    if not listing_links:
        st.error("No listing links found. The page structure may need custom selectors.")
        st.stop()

    category_name = urlparse(category_url).path.strip("/").replace("-", " ").title()
    listing_links = listing_links[:max_listings]

    rows = []
    progress = st.progress(0)
    status = st.empty()

    for i, link in enumerate(listing_links, start=1):
        status.write(f"Scraping {i}/{len(listing_links)}: {link}")
        row = scrape_business_page(link, category_name)
        rows.append(row)
        progress.progress(i / len(listing_links))
        time.sleep(delay)

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["Name", "Contact Number", "Source URL"])

    st.success(f"Done. Found {len(df)} records.")
    st.dataframe(df, use_container_width=True)

    excel = convert_to_excel(df)

    st.download_button(
        "Download Excel",
        excel,
        "business_data.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
