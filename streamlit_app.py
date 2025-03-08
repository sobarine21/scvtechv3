import streamlit as st 
import requests
from bs4 import BeautifulSoup, Comment
import json
import random
import re
from requests_html import HTMLSession
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from langdetect import detect, LangDetectException
import validators
import pandas as pd
import io
from concurrent.futures import ThreadPoolExecutor
from textblob import TextBlob
import time
import plotly.express as px

from langdetect import DetectorFactory
DetectorFactory.seed = 0

def get_random_user_agent():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
        'Mozilla/5.0 (Linux; Android 10; SM-G960F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Mobile Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36 Edge/16.16299'
    ]
    
    return random.choice(user_agents)

def is_valid_url(url):
    return validators.url(url)

def is_scraping_allowed(url):
    parsed_url = urlparse(url)
    robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        return rp.can_fetch("*", url)
    except:
        return False
        
def detect_language(text):
    if not text or len(text.split()) < 3:
        return "Insufficient text for detection"
    try:
        return detect(text)
    except LangDetectException:
        return "Detection failed"

def extract_meta_tags(soup):
    meta_info = {}
    for tag in soup.find_all("meta"):
        if tag.get("name"):
            meta_info[tag.get("name")] = tag.get("content")
        elif tag.get("property"):
            meta_info[tag.get("property")] = tag.get("content")
    return meta_info

def extract_links(url, soup):
    internal_links, external links = [], []
    for link in soup.find_all("a", href=True):
        if link["href"].startswith("http"):
            if url in link["href"]:
                internal_links.append(link["href"])
            else:
                external_links.append(link["href"])
    return internal_links, external_links

def extract_json_ld(soup):
    json_ld_data = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            json_ld_data.append(json.loads(script.string))
        except json.JSONDecodeError:
            continue
    return json_ld_data

def extract_forms(soup):
    forms = []
    for form in soup.find_all("form"):
        form_data = {
            "action": form.get("action"),
            "method": form.get("method"),
            "inputs": []
        }
        for input_tag in form.find_all("input"):
            input_data = {
                "type": input_tag.get("type"),
                "name": input_tag.get("name"),
                "value": input_tag.get("value")
            }
            form_data["inputs"].append(input_data)
        forms.append(form_data)
    return forms

def extract_scripts_and_tracking(soup):
    tracking_scripts = []
    for script in soup.find_all("script"):
        src = script.get("src")
        if src:
            if "analytics" in src or "tracking" in src:
                tracking_scripts.append(src)
    return tracking_scripts

def extract_media(soup):
    media_data = []
    images = [{"src": img.get("src"), "alt": img.get("alt", "No alt text")} for img in soup.find_all("img", src=True)]
    media_data.extend(images)
    videos = [{"src": video.get("src")} for video in soup.find_all("video", src=True)]
    media_data.extend(videos)
    return media_data

def extract_comments(soup):
    comments = []
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comments.append(comment)
    return comments

def extract_http_info(url):
    try:
        response = requests.get(url)
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers)
        }
    except requests.RequestException as e:
        return {"error": str(e)}

def extract_tables(soup):
    tables = []
    for table in soup.find_all("table"):
        table_data = [[cell.get_text() for cell in row.find_all(["th", "td"])] for row in table.find_all("tr")]
        tables.append(table_data)
    return tables

def extract_headings(soup):
    headings = {}
    for level in range(1, 7):
        headings[f"h{level}"] = [h.get_text() for h in soup.find_all(f"h{level}")]
    return headings

def extract_social_media_links(external_links):
    social_links = []
    social_media domains = ["facebook", "twitter", "instagram", "linkedin", "youtube"]
    for link in external links:
        if any domain in link for domain in social_media domains):
            social_links.append(link)
    return social_links

def extract_audio_files(soup):
    audio_files = []
    for audio in soup.find_all("audio"):
        src = audio.get("src")
        if src:
            audio_files.append(src)
    return audio_files

def extract_stylesheets(soup):
    stylesheets = []
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href")
        if href:
            stylesheets.append(href)
    return stylesheets

def extract_iframes(soup):
    iframes = []
    for iframe in soup.find_all("iframe"):
        src = iframe.get("src")
        if src:
            iframes.append(src)
    return iframes

def extract_external_js(soup):
    external_js = []
    for script in soup.find_all("script", src=True):
        external_js.append(script.get("src"))
    return external_js

def extract_http_response_time(url):
    try:
        response = requests.get(url)
        return response.elapsed.total_seconds()
    except requests.RequestException as e:
        return {"error": str(e)}

def check_broken_images(media):
    broken_images = []
    for media_item in media:
        if media_item.get("src"):
            try:
                response = requests.head(media_item["src"], timeout=5)
                if response.status_code != 200:
                    broken_images.append(media_item["src"])
            except:
                broken_images.append(media_item["src"])
    return broken_images

def extract_meta_keywords(soup):
    meta_keywords = []
    meta_tags = soup.find_all("meta", {"name": "keywords"})
    for meta_tag in meta_tags:
        if meta_tag.get("content"):
            meta_keywords.extend(meta_tag["content"].split(","))
    return meta_keywords

def extract_contact_info(soup):
    contact_info = {
        "emails": [],
        "phone_numbers": [],
        "contact_forms": []
    }

    emails = set(re.findall(r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', str(soup)))
    contact_info["emails"] = list(emails)

    phone_numbers = set(re.findall(r'(\+?\(?\d{1,4}\)?[\s\-]?\d{1,3}[\s\-]?\d{3}[\s\-]?\d{4})', str(soup)))
    contact_info["phone_numbers"] = list(phone_numbers)

    for form in soup.find_all("form"):
        action = form.get("action", "").lower()
        if "contact" in action:
            contact_info["contact_forms"].append(form)

    return contact_info

def analyze_word_count_and_density(content):
    words = content.split()
    word_count = len(words)
    keyword_density = {}
    for word in words:
        word = word.lower()
        if word in keyword_density:
            keyword_density[word] += 1
        else:
            keyword_density[word] = 1
    for word in keyword_density:
        keyword_density[word] = (keyword_density[word] / word_count) * 100
    return word_count, keyword_density

def analyze_sentiment(content):
    blob = TextBlob(content)
    return blob.sentiment.polarity, blob.sentiment.subjectivity

def check_viewport_meta(soup):
    viewport = soup.find("meta", attrs={"name": "viewport"})
    return viewport["content"] if viewport else "Not found"

def extract_canonical_link(soup):
    canonical = soup.find("link", rel="canonical")
    return canonical["href"] if canonical else "Not found"

def check_favicon(soup):
    favicon = soup.find("link", rel="icon")
    return favicon["href"] if favicon else "Not found"

def extract_schema_markup(soup):
    schema_data = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            schema_data.append(json.loads(script.string))
        except json.JSONDecodeError:
            continue
    return schema_data

def score_website(data):
    score = 0
    max_score = 100
    
    if data.get("Meta Tags"):
        score += 10
    if data.get("Detected Language") != "Detection failed":
        score += 10
    if data.get("Internal Links"):
        score += 10
    if data.get("External Links"):
        score += 10
    if data.get("Forms"):
        score += 10
    if data.get("Media"):
        score += 10
    if data.get("Tables"):
        score += 10
    if data.get("Headings"):
        score += 10
    if data.get("Social Media Links"):
        score += 10
    if data.get("HTTP Info") and data["HTTP Info"].get("status_code") == 200:
        score += 10
    
    return score, max_score

def scrape_website(url):
    session = HTMLSession()
    headers = {"User-Agent": get_random_user_agent()}
    start_time = time.time()
    response = session.get(url, headers=headers)
    load_time = time.time() - start_time
    soup = BeautifulSoup(response.content, "html.parser")
    
    data = {}

    data["Meta Tags"] = extract_meta_tags(soup)
    content = " ".join([p.get_text() for p in soup.find_all("p")])
    data["Main Content"] = content[:1000] + "..."
    data["Detected Language"] = detect_language(content)
    internal links, external links = extract_links(url, soup)
    data["Internal Links"] = internal links
    data["External Links"] = external links
    data["JSON-LD Data"] = extract_json_ld(soup)
    data["Forms"] = extract_forms(soup)
    data["Tracking Scripts"] = extract_scripts_and_tracking(soup)
    data["Media"] = extract_media(soup)
    data["Comments"] = extract_comments(soup)
    data["HTTP Info"] = extract_http_info(url)
    data["Tables"] = extract_tables(soup)
    data["Headings"] = extract_headings(soup)
    data["Social Media Links"] = extract_social_media_links(external links)
    data["Audio Files"] = extract_audio_files(soup)
    data["Stylesheets"] = extract_stylesheets(soup)
    data["iFrames"] = extract_iframes(soup)
    data["External JavaScript"] = extract_external_js(soup)
    data["HTTP Response Time"] = extract_http_response_time(url)
    data["Broken Images"] = check_broken_images(data.get("Media", []))
    data["Meta Keywords"] = extract_meta_keywords(soup)
    data["Contact Info"] = extract_contact_info(soup)
    
    word_count, keyword_density = analyze_word_count_and_density(content)
    sentiment_polarity, sentiment_subjectivity = analyze_sentiment(content)
    data["Word Count"] = word_count
    data["Keyword Density"] = keyword_density
    data["Sentiment Polarity"] = sentiment_polarity
    data["Sentiment Subjectivity"] = sentiment_subjectivity
    data["Page Load Time"] = load_time
    data["Viewport Meta Tag"] = check_viewport_meta(soup)
    data["Canonical Link"] = extract_canonical_link(soup)
    data["Favicon"] = check_favicon(soup)
    data["Schema Markup"] = extract_schema_markup(soup)

    data["Score"], data["Max Score"] = score_website(data)

    return data

def compare_websites(scraped_data):
    comparison = {}
    keys = scraped_data[list(scraped_data.keys())[0]].keys()
    
    for key in keys:
        comparison[key] = {url: data.get(key, None) for url, data in scraped_data.items()}
        
    return comparison

def convert_to_json(data):
    return json.dumps(data, indent=4)

def convert_to_csv(data):
    output = io.StringIO()
    df = pd.json_normalize(data)
    df.to_csv(output, index=False)
    return output.getvalue()

def convert_to_excel(data):
    output = io.BytesIO()
    df = pd.json_normalize(data)
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

st.set_page_config(page_title="Comprehensive Web Scraping Tool", layout="wide", initial_sidebar_state="expanded")

hide_streamlit_style = """
    <style>
        .css-1r6p8d1 {display: none;} 
        .css-1v3t3fg {display: none;} 
        .css-1r6p8d1 .st-ae {display: none;} 
        header {visibility: hidden;} 
        .css-1tqja98 {visibility: hidden;} 
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.markdown("""
    <style>
        .main {
            background-color: #1e1e1e;
            color: #ffffff;
            padding: 2rem;
            border-radius: 10px;
        }
        .stButton>button {
            background-color: #0078d4;
            color: white;
            border-radius: 5px;
            padding: 0.5rem 1rem;
            font-size: 1rem;
        }
        .stTextInput>div>div>input {
            background-color: #333333;
            color: #ffffff;
            border: 1px solid #555555;
            padding: 0.5rem;
            border-radius: 5px;
        }
        .stAlert {
            border-radius: 5px;
        }
        .css-1aumxhk {
            padding-top: 2rem;
        }
        .reportview-container .main footer {
            visibility: hidden;
        }
    </style>
""", unsafe_allow_html=True)

st.title("Comprehensive Web Scraping Tool")
st.subheader("Analyze and extract detailed information from any web page")

url1 = st.text_input("Enter the first URL for analysis", placeholder="https://example.com", key="url1")
url2 = st.text_input("Enter the second URL for analysis (optional)", placeholder="https://example.com", key="url2")
url3 = st.text_input("Enter the third URL for analysis (optional)", placeholder="https://example.com", key="url3")

urls = [url1, url2, url3]
urls = [url for url in urls if url]

def analyze_urls(urls):
    if len(urls) > 3:
        st.error("Please enter up to 3 URLs only.")
        return

    invalid_urls = [url for url in urls if not is_valid_url(url)]
    if invalid_urls:
        st.error(f"Invalid URLs: {', '.join(invalid_urls)}")
        return

    disallowed_urls = [url for url in urls if not is_scraping_allowed(url)]
    if disallowed_urls:
        st.warning(f"Scraping not allowed on: {', '.join(disallowed_urls)}")
        return

    results = {}
    with ThreadPoolExecutor(max_workers=len(urls)) as executor:
        future_to_url = {executor.submit(scrape_website, url): url for url in urls}
        for future in future_to_url:
            url = future_to_url[future]
            try:
                result = future.result()
                results[url] = result
            except Exception as e:
                results[url] = {"error": str(e)}

    return results

if st.button("Analyze"):
    if not urls:
        st.error("Please enter at least one URL.")
    else:
        with st.spinner("Scraping and analyzing..."):
            scraped_data = analyze_urls(urls)
            if scraped_data:
                st.success("Scraping completed successfully!")
                
                comparison = compare_websites(scraped_data)
                st.header("Comparison Results")
                st.json(comparison)
                
                st.download_button(
                    label="Download Comparison JSON",
                    data=convert_to_json(comparison),
                    file_name='comparison_data.json',
                    mime='application/json'
                )
                st.download_button(
                    label="Download Comparison CSV",
                    data=convert_to_csv(comparison),
                    file_name='comparison_data.csv',
                    mime='text/csv'
                )
                st.download_button(
                    label="Download Comparison Excel",
                    data=convert_to_excel(comparison),
                    file_name='comparison_data.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                
                # New section for visualizing the scoring metrics
                st.header("Scoring Dashboard")
                
                score_data = {url: data["Score"] for url, data in scraped_data.items()}
                max_score = list(scraped_data.values())[0]["Max Score"]
                
                score_df = pd.DataFrame(list(score_data.items()), columns=['URL', 'Score'])
                score_df['Max Score'] = max_score
                
                fig = px.bar(score_df, x='URL', y='Score', title='Website Scores', range_y=[0, max_score])
                st.plotly_chart(fig)
                
                detailed_scores = {url: data for url, data in scraped_data.items()}
                detailed_score_df = pd.DataFrame(detailed_scores).T.reset_index()
                st.dataframe(detailed_score_df)

st.markdown(
    """
    ### Self-Hosting
    If you want to self-host this application or download the source code, please visit:  
    👉 [Download Source Code](https://dhruvbansal8.gumroad.com/l/hhwbm)
    """
)
