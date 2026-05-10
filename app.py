import re
import time
from io import BytesIO
from urllib.parse import urljoin, urlparse, quote_plus, parse_qs, unquote

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup


st.set_page_config(page_title="Business Data Scraper", layout="wide")
st.title("Business Data Scraper")

source_url = st.text_input("Category / website URL", "https://vadodara.idbf.in/academy")
city = st.text_input("City", "Vadodara")
category = st.text_input("Category keyword", "academy")
max_results = st.number_input("Maximum records", min_value=5, max_value=100, value=25, step=5)
delay = st.number_input("Delay between requests", min_value=0.0, max_value=5.0, value=1.0, step=0.5)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def get_html(url):
    try:
        r = requests.get(url, headers=headers, timeout=20)
        return r.status_code, r.text
    except Exception:
        return 0, ""


def extract_email(text):
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    bad = ["example.com", "email.com", "domain.com"]
    emails = [e.lower() for e in emails if not any(b in e.lower() for b in bad)]
    return ", ".join(sorted(set(emails))[:5])


def extract_phone(text):
    phones = re.findall(
        r"(?:\+91[\s-]?)?[6-9]\d{9}|\b0[0-9]{2,5}[\s-]?[0-9]{6,8}\b",
        text,
    )
    return ", ".join(sorted(set(clean_text(p) for p in phones))[:5])


def extract_address(text):
    patterns = [
        r"Address[:\s]+(.{10,350}?)(?:Phone|Mobile|Email|Website|Contact|$)",
        r"(.{10,250}(Vadodara|Baroda|Gujarat|390\d{3}).{0,160})",
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return clean_text(m.group(1))[:350]

    return ""


def extract_socials(soup, base_url):
    data = {
        "Facebook": "",
        "Instagram": "",
        "LinkedIn": "",
        "YouTube": "",
        "X / Twitter": "",
    }

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        low = href.lower()

        if "facebook.com" in low and not data["Facebook"]:
            data["Facebook"] = href
        elif "instagram.com" in low and not data["Instagram"]:
            data["Instagram"] = href
        elif "linkedin.com" in low and not data["LinkedIn"]:
            data["LinkedIn"] = href
        elif "youtube.com" in low and not data["YouTube"]:
            data["YouTube"] = href
        elif ("twitter.com" in low or "x.com" in low) and not data["X / Twitter"]:
            data["X / Twitter"] = href

    return data


def get_domain(url):
    return urlparse(url).netloc.lower().replace("www.", "")


def find_external_website(soup, page_url):
    page_domain = get_domain(page_url)
    ignore = ["facebook", "instagram", "linkedin", "youtube", "twitter", "x.com", "google", "wa.me", "whatsapp"]

    for a in soup.find_all("a", href=True):
        href = urljoin(page_url, a["href"])
        domain = get_domain(href)

        if domain and domain != page_domain and not any(x in domain for x in ignore):
            return href

    return ""


def extract_name_from_soup(soup):
    for selector in ["h1", "h2", ".entry-title", ".post-title", ".business-title", ".listing-title"]:
        item = soup.select_one(selector)
        if item:
            value = clean_text(item.get_text(" "))
            if value:
                return value[:200]

    if soup.title:
        return clean_text(soup.title.get_text(" "))[:200]

    return ""


def find_links_from_page(base_url, html):
    soup = BeautifulSoup(html, "html.parser")
    root_domain = get_domain(base_url)
    links = []

    skip = ["login", "register", "privacy", "terms", "contact", "about", "facebook", "instagram", "youtube", "linkedin"]

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).rstrip("/")

        if get_domain(href) != root_domain:
            continue

        if href == base_url.rstrip("/"):
            continue

        if any(x in href.lower() for x in skip):
            continue

        text = clean_text(a.get_text(" "))
        if len(text) > 1:
            links.append(href)

    return sorted(set(links))


def duckduckgo_search(query, limit=10):
    search_url = "https://duckduckgo.com/html/?q=" + quote_plus(query)
    status, html = get_html(search_url)

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    results = []

    for a in soup.select("a.result__a"):
        href = a.get("href", "")
        title = clean_text(a.get_text(" "))

        if "uddg=" in href:
            qs = parse_qs(urlparse(href).query)
            if "uddg" in qs:
                href = unquote(qs["uddg"][0])

        if href.startswith("http"):
            results.append({"title": title, "url": href})

        if len(results) >= limit:
            break

    return results


def scrape_single_page(url, fallback_name="", fallback_category=""):
    status, html = get_html(url)

    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    text = clean_text(soup.get_text(" "))
    socials = extract_socials(soup, url)

    name = extract_name_from_soup(soup) or fallback_name
    website = find_external_website(soup, url)

    return {
        "Name": name,
        "Category": fallback_category,
        "Address": extract_address(text),
        "Contact Number": extract_phone(text),
        "Phone Number": extract_phone(text),
        "Email Address": extract_email(text),
        "Web Address": website,
        "Facebook": socials["Facebook"],
        "Instagram": socials["Instagram"],
        "LinkedIn": socials["LinkedIn"],
        "YouTube": socials["YouTube"],
        "X / Twitter": socials["X / Twitter"],
        "Source URL": url,
        "Status": "Auto extracted. Verify manually.",
    }


def enrich_from_search(row):
    missing = not row["Email Address"] or not row["Contact Number"] or not row["Web Address"]

    if not missing:
        return row

    query = f'{row["Name"]} {row["Category"]} {city} contact website email phone'
    results = duckduckgo_search(query, limit=5)

    for result in results:
        url = result["url"]

        if any(bad in url.lower() for bad in ["facebook.com", "instagram.com", "youtube.com", "linkedin.com"]):
            continue

        extra = scrape_single_page(url, row["Name"], row["Category"])

        if not extra:
            continue

        if not row["Email Address"] and extra["Email Address"]:
            row["Email Address"] = extra["Email Address"]

        if not row["Contact Number"] and extra["Contact Number"]:
            row["Contact Number"] = extra["Contact Number"]
            row["Phone Number"] = extra["Contact Number"]

        if not row["Address"] and extra["Address"]:
            row["Address"] = extra["Address"]

        if not row["Web Address"]:
            row["Web Address"] = url

        if row["Email Address"] or row["Contact Number"] or row["Web Address"]:
            row["Status"] = "Extracted + enriched from web search. Verify manually."
            break

        time.sleep(delay)

    return row


def excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Business Data")
    return output.getvalue()


if st.button("Start"):
    rows = []

    st.write("Step 1: Trying direct page scrape...")
    status, html = get_html(source_url)

    st.write("Page status:", status)
    st.write("HTML length:", len(html))

    links = []

    if html and len(html) > 1000:
        links = find_links_from_page(source_url, html)

    st.write("Direct listing links found:", len(links))

    if not links:
        st.warning("Direct website scrape did not return usable listing links. Switching to free web-search mode.")
        query = f"site:{get_domain(source_url)} {category} {city}"
        search_results = duckduckgo_search(query, limit=max_results)

        for item in search_results:
            links.append(item["url"])

    if not links:
        st.warning("No IDBF links found from search. Searching wider web for businesses.")
        wider_query = f"{category} in {city} contact email phone website"
        search_results = duckduckgo_search(wider_query, limit=max_results)

        for item in search_results:
            links.append(item["url"])

    links = list(dict.fromkeys(links))[:max_results]

    st.write("Total pages to check:", len(links))

    progress = st.progress(0)
    status_box = st.empty()

    for i, link in enumerate(links, start=1):
        status_box.write(f"Checking {i}/{len(links)}: {link}")

        row = scrape_single_page(link, fallback_category=category.title())

        if row:
            row = enrich_from_search(row)

            has_data = row["Name"] or row["Address"] or row["Contact Number"] or row["Email Address"] or row["Web Address"]

            if has_data:
                rows.append(row)

        progress.progress(i / len(links))
        time.sleep(delay)

    df = pd.DataFrame(rows)

    if not df.empty:
        df = df.drop_duplicates(subset=["Name", "Contact Number", "Email Address", "Source URL"])

    st.success(f"Done. Found {len(df)} records.")
    st.dataframe(df, use_container_width=True)

    if not df.empty:
        st.download_button(
            "Download Excel",
            excel_bytes(df),
            "business_data.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
