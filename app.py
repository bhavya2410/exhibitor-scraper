import streamlit as st
import requests
import re
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from io import BytesIO

st.set_page_config(page_title="Exhibitor Lead Scraper", layout="wide")

st.title("Exhibitor Lead Scraper")

expo_url = st.text_input(
    "Exhibitor page URL",
    "https://smarthomeexpo.in.messefrankfurt.com/mumbai/en/exhibitor-search.html"
)

headers = {
    "User-Agent": "Mozilla/5.0"
}

ignore_domains = [
    "messefrankfurt",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "wa.me",
    "whatsapp.com",
    "google.com"
]

def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()

def get_domain_name(url):
    domain = urlparse(url).netloc.lower()
    domain = domain.replace("www.", "")
    return domain.split(".")[0].replace("-", " ").title()

def safe_get(url):
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
            return response.text
    except:
        return ""
    return ""

def extract_emails(text):
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return sorted(set([email.lower() for email in emails]))

def extract_phones(text):
    phones = re.findall(r"(?:\+91[\s-]?)?[6-9]\d{9}", text)
    return sorted(set(phones))

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

def extract_product_text(soup):
    useful_text = []

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        useful_text.append(meta_desc.get("content"))

    for tag in soup.find_all(["h1", "h2", "h3"]):
        txt = clean_text(tag.get_text(" "))
        if len(txt) > 3:
            useful_text.append(txt)

    return " | ".join(useful_text)[:1000]

def find_contact_person(text):
    patterns = [
        r"Contact Person[:\s]+([A-Z][A-Za-z\s\.]+)",
        r"Sales Manager[:\s]+([A-Z][A-Za-z\s\.]+)",
        r"Manager[:\s]+([A-Z][A-Za-z\s\.]+)"
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return clean_text(match.group(1))[:80]

    return ""

def get_exhibitor_links(expo_url):
    html = safe_get(expo_url)
    soup = BeautifulSoup(html, "html.parser")

    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"]

        if href.startswith("http"):
            domain = urlparse(href).netloc.lower()

            if not any(bad in domain for bad in ignore_domains):
                links.append(href)

    return sorted(set(links))

def scrape_exhibitor(site):
    pages_to_try = [
        site,
        urljoin(site, "/contact"),
        urljoin(site, "/contact-us"),
        urljoin(site, "/about"),
        urljoin(site, "/about-us"),
        urljoin(site, "/products"),
        urljoin(site, "/solutions"),
        urljoin(site, "/support")
    ]

    all_text = ""
    all_emails = []
    all_phones = []
    all_products = []

    social_data = {
        "Facebook": "",
        "Instagram": "",
        "LinkedIn": "",
        "X / Twitter": "",
        "YouTube": ""
    }

    for page in pages_to_try:
        page_html = safe_get(page)

        if page_html:
            page_soup = BeautifulSoup(page_html, "html.parser")
            page_text = clean_text(page_soup.get_text(" "))

            all_text += " " + page_text
            all_emails.extend(extract_emails(page_text))
            all_phones.extend(extract_phones(page_text))

            product_text = extract_product_text(page_soup)
            if product_text:
                all_products.append(product_text)

            socials = extract_social_links(page_soup, site)
            for key, value in socials.items():
                if value and not social_data[key]:
                    social_data[key] = value

    return {
        "Exhibitor Name": get_domain_name(site),
        "Website URL": site,
        "Email": ", ".join(sorted(set(all_emails))[:5]),
        "Phone": ", ".join(sorted(set(all_phones))[:5]),
        "Contact Person": find_contact_person(all_text),
        "Products / Categories": " | ".join(sorted(set(all_products)))[:1500],
        "Facebook": social_data["Facebook"],
        "Instagram": social_data["Instagram"],
        "LinkedIn": social_data["LinkedIn"],
        "X / Twitter": social_data["X / Twitter"],
        "YouTube": social_data["YouTube"],
        "Source": expo_url,
        "Notes": "Auto extracted. Verify manually."
    }

def convert_df_to_excel(df):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Exhibitors")

    return output.getvalue()

if st.button("Start Scraping"):
    with st.spinner("Finding exhibitor websites..."):
        exhibitor_links = get_exhibitor_links(expo_url)

    st.success(f"Found {len(exhibitor_links)} exhibitor websites.")

    rows = []
    progress = st.progress(0)
    status = st.empty()

    for index, site in enumerate(exhibitor_links, start=1):
        status.write(f"Checking {index}/{len(exhibitor_links)}: {site}")
        rows.append(scrape_exhibitor(site))
        progress.progress(index / len(exhibitor_links))

    df = pd.DataFrame(rows)

    st.success("Scraping completed.")
    st.dataframe(df, use_container_width=True)

    excel_file = convert_df_to_excel(df)

    st.download_button(
        label="Download Excel File",
        data=excel_file,
        file_name="smart_home_expo_exhibitors.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
