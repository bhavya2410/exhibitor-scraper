import streamlit as st
import requests
import re
import time
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
from io import BytesIO
from collections import deque

st.set_page_config(page_title="Vadodara IDBF Scraper", layout="wide")

st.title("Vadodara IDBF Business Scraper")

start_url = st.text_input(
    "Website URL",
    "https://vadodara.idbf.in/"
)

max_pages = st.number_input(
    "Maximum pages to scan",
    min_value=10,
    max_value=2000,
    value=300,
    step=50
)

delay = st.number_input(
    "Delay between pages in seconds",
    min_value=0.0,
    max_value=5.0,
    value=0.5,
    step=0.1
)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
}

def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()

def safe_get(url):
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200 and "text/html" in r.headers.get("Content-Type", ""):
            return r.text
    except Exception:
        return ""
    return ""

def same_domain(url, root_domain):
    return urlparse(url).netloc.replace("www.", "") == root_domain

def normalize_url(url):
    url, _ = urldefrag(url)
    return url.rstrip("/")

def extract_emails(text):
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return ", ".join(sorted(set(e.lower() for e in emails))[:5])

def extract_phones(text):
    phones = re.findall(r"(?:\+91[\s-]?)?[6-9]\d{9}|\b0[0-9]{2,5}[\s-]?[0-9]{6,8}\b", text)
    phones = [clean_text(p) for p in phones]
    return ", ".join(sorted(set(phones))[:5])

def extract_social_links(soup, base_url):
    socials = {
        "Facebook": "",
        "Instagram": "",
        "LinkedIn": "",
        "X / Twitter": "",
        "YouTube": ""
    }

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        low = href.lower()

        if "facebook.com" in low and not socials["Facebook"]:
            socials["Facebook"] = href
        elif "instagram.com" in low and not socials["Instagram"]:
            socials["Instagram"] = href
        elif "linkedin.com" in low and not socials["LinkedIn"]:
            socials["LinkedIn"] = href
        elif ("twitter.com" in low or "x.com" in low) and not socials["X / Twitter"]:
            socials["X / Twitter"] = href
        elif "youtube.com" in low and not socials["YouTube"]:
            socials["YouTube"] = href

    return socials

def extract_external_website(soup, root_domain, base_url):
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        parsed = urlparse(href)

        if parsed.scheme in ["http", "https"]:
            domain = parsed.netloc.replace("www.", "").lower()

            if domain and domain != root_domain:
                if not any(x in domain for x in ["facebook", "instagram", "linkedin", "youtube", "twitter", "x.com", "google", "wa.me", "whatsapp"]):
                    return href

    return ""

def guess_name(soup):
    for tag in ["h1", "h2", "h3"]:
        item = soup.find(tag)
        if item:
            txt = clean_text(item.get_text(" "))
            if len(txt) > 2:
                return txt[:150]

    if soup.title:
        return clean_text(soup.title.get_text(" "))[:150]

    return ""

def guess_category(soup):
    crumbs = soup.find_all(["a", "span"], class_=re.compile("breadcrumb|category|cat", re.I))
    text = " | ".join(clean_text(c.get_text(" ")) for c in crumbs if clean_text(c.get_text(" ")))
    return text[:300]

def guess_address(text):
    match = re.search(r"(.{0,120}(Vadodara|Gujarat|390\d{3}).{0,160})", text, re.I)
    if match:
        return clean_text(match.group(1))[:300]
    return ""

def page_to_row(url, html, root_domain):
    soup = BeautifulSoup(html, "html.parser")
    text = clean_text(soup.get_text(" "))

    emails = extract_emails(text)
    phones = extract_phones(text)
    socials = extract_social_links(soup, url)

    return {
        "Business Name": guess_name(soup),
        "Category": guess_category(soup),
        "Phone": phones,
        "Email": emails,
        "Website": extract_external_website(soup, root_domain, url),
        "Address": guess_address(text),
        "Facebook": socials["Facebook"],
        "Instagram": socials["Instagram"],
        "LinkedIn": socials["LinkedIn"],
        "X / Twitter": socials["X / Twitter"],
        "YouTube": socials["YouTube"],
        "Source Page": url,
        "Notes": "Auto extracted. Verify manually."
    }

def find_internal_links(url, html, root_domain):
    soup = BeautifulSoup(html, "html.parser")
    links = []

    skip_ext = [".jpg", ".jpeg", ".png", ".gif", ".pdf", ".zip", ".webp", ".svg", ".css", ".js"]

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()

        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue

        full = normalize_url(urljoin(url, href))
        parsed = urlparse(full)

        if parsed.scheme not in ["http", "https"]:
            continue

        if not same_domain(full, root_domain):
            continue

        if any(full.lower().endswith(ext) for ext in skip_ext):
            continue

        links.append(full)

    return sorted(set(links))

def convert_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Vadodara IDBF")
    return output.getvalue()

if st.button("Start Scraping"):
    root_domain = urlparse(start_url).netloc.replace("www.", "").lower()

    queue = deque([normalize_url(start_url)])
    visited = set()
    rows = []

    progress = st.progress(0)
    status = st.empty()

    while queue and len(visited) < max_pages:
        url = queue.popleft()

        if url in visited:
            continue

        visited.add(url)
        status.write(f"Scanning page {len(visited)}/{max_pages}: {url}")

        html = safe_get(url)

        if html:
            row = page_to_row(url, html, root_domain)

            has_useful_data = row["Phone"] or row["Email"] or row["Address"] or row["Website"]

            if has_useful_data:
                rows.append(row)

            new_links = find_internal_links(url, html, root_domain)

            for link in new_links:
                if link not in visited and link not in queue:
                    queue.append(link)

        progress.progress(min(len(visited) / max_pages, 1.0))
        time.sleep(delay)

    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.drop_duplicates(subset=["Business Name", "Phone", "Email", "Source Page"])

    st.success(f"Done. Scanned {len(visited)} pages and found {len(df)} possible business records.")

    st.dataframe(df, use_container_width=True)

    excel_file = convert_to_excel(df)

    st.download_button(
        label="Download Excel",
        data=excel_file,
        file_name="vadodara_idbf_business_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
