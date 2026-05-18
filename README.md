# Exhibitor Scraper

Exhibitor Scraper is a Streamlit app for collecting publicly available business and exhibitor contact data from category pages, listing websites, and search results. It helps turn scattered web pages into a structured table that can be reviewed, cleaned, and exported to Excel.

The app is useful when event directories, local business listings, or exhibitor pages do not provide a clean downloadable spreadsheet. It crawls candidate listing pages, extracts common contact fields, enriches missing details through search, and presents the results in a spreadsheet-style view.

## Features

- Scrapes listing/category pages for internal business links
- Falls back to DuckDuckGo search when a source page does not expose usable links
- Extracts business names, addresses, phone numbers, email addresses, website links, and social profiles
- Enriches missing fields from additional public web results
- Exports results to an Excel workbook
- Runs locally with a simple Streamlit interface

## Use Cases

- Building a first-pass exhibitor contact table from an event website
- Collecting local business directory entries for manual verification
- Converting public listing pages into a structured spreadsheet
- Researching public contact information before outreach or data cleanup

## Requirements

- Python 3.10 or newer
- `pip`

## Installation

Clone the repository:

```bash
git clone https://github.com/bhavya2410/exhibitor-scraper.git
cd exhibitor-scraper
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Start the app:

```bash
streamlit run app.py
```

Then open the local Streamlit URL shown in your terminal.

In the app:

1. Enter a category or directory URL.
2. Enter the city to use for search enrichment.
3. Enter a category keyword, such as `academy`, `manufacturer`, or `restaurant`.
4. Choose the maximum number of records to inspect.
5. Choose a delay between requests.
6. Click **Start**.
7. Review the extracted table.
8. Download the Excel file.

## Example

Input:

```text
Category / website URL: https://vadodara.idbf.in/academy
City: Vadodara
Category keyword: academy
Maximum records: 25
Delay between requests: 1.0
```

Sample output:

| Name | Category | Address | Contact Number | Email Address | Web Address | Source URL | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Example Academy | Academy | Vadodara, Gujarat | +91 9876543210 | info@exampleacademy.com | https://exampleacademy.com | https://example.com/listing/example-academy | Auto extracted. Verify manually. |
| Sample Learning Center | Academy | Alkapuri, Vadodara | 0265 1234567 | contact@samplelearning.in | https://samplelearning.in | https://example.com/listing/sample-learning | Extracted + enriched from web search. Verify manually. |

A CSV version of this example is available at [`examples/sample_output.csv`](examples/sample_output.csv).

## Output Columns

- `Name`
- `Category`
- `Address`
- `Contact Number`
- `Phone Number`
- `Email Address`
- `Web Address`
- `Facebook`
- `Instagram`
- `LinkedIn`
- `YouTube`
- `X / Twitter`
- `Source URL`
- `Status`

## Notes On Accuracy

This tool extracts public information using regular expressions and HTML parsing. Web pages vary a lot, so the output should be treated as a starting point, not as final verified data. Always review the table before using it for outreach, publishing, or business decisions.

## Responsible Use

Please use this project respectfully:

- Scrape only public pages you are allowed to access.
- Follow each website's terms of service and robots guidance.
- Use a reasonable delay between requests.
- Verify contact data manually before acting on it.
- Do not use the tool for spam or abusive outreach.

## Roadmap

- Add configurable output columns
- Improve address extraction for more Indian cities
- Add tests for extractors
- Add support for uploading a list of URLs
- Improve deduplication across similar business names

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE) for details.
