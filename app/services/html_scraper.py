import re
from typing import List, Optional
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from utils.logger import setup_logger
import os
from bs4 import BeautifulSoup
from selenium import webdriver


SELENIUM_REMOTE_URL = os.getenv("SELENIUM_REMOTE_URL")
STATE = os.getenv("STATE")
logger = setup_logger("scraper")
async def fetch_company_details(url: str) -> dict:
    driver = None
    try:
        options = webdriver.ChromeOptions()
        options.add_argument(f'--lang=en-US')
        options.add_argument("--start-maximized")
        options.add_argument("--disable-webrtc")
        options.add_argument("--disable-features=WebRtcHideLocalIpsWithMdns")
        options.add_argument("--force-webrtc-ip-handling-policy=default_public_interface_only")
        options.add_argument("--disable-features=DnsOverHttps")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--no-first-run")
        options.add_argument("--no-sandbox")
        options.add_argument("--test-type")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.set_capability("goog:loggingPrefs", {
            "performance": "ALL",
            "browser": "ALL"
        })
        driver = webdriver.Remote(
            command_executor=SELENIUM_REMOTE_URL,
            options=options
        )
        driver.set_page_load_timeout(30)
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, "body > form")))
        html = driver.page_source
        return await parse_html_details(html)
    except Exception as e:
        logger.error(f"Error fetching data for query '{url}': {e}")
        return {}
    finally:
        if driver:
            driver.quit()

async def fetch_company_data(query: str) -> list[dict]:
    driver = None
    url = f"https://egov.sos.state.or.us/br/pkg_web_name_srch_inq.do_name_srch?p_name={query}&p_regist_nbr=&p_srch=PHASE1&p_print=FALSE&p_entity_status=ACTINA"
    try:

        options = webdriver.ChromeOptions()
        options.add_argument(f'--lang=en-US')
        options.add_argument("--start-maximized")
        options.add_argument("--disable-webrtc")
        options.add_argument("--disable-features=WebRtcHideLocalIpsWithMdns")
        options.add_argument("--force-webrtc-ip-handling-policy=default_public_interface_only")
        options.add_argument("--disable-features=DnsOverHttps")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--no-first-run")
        options.add_argument("--no-sandbox")
        options.add_argument("--test-type")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.set_capability("goog:loggingPrefs", {
            "performance": "ALL",
            "browser": "ALL"
        })
        driver = webdriver.Remote(
            command_executor=SELENIUM_REMOTE_URL,
            options=options
        )
        driver.set_page_load_timeout(30)
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, "body > form > table:nth-child(3)")))
        html = driver.page_source
        return await parse_html_search(html)
    except Exception as e:
        logger.error(f"Error fetching data for query '{query}': {e}")
        return []
    finally:
        if driver:
            driver.quit()

async def parse_html_search(html: str) -> list[dict]:
    results = []
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("body > form > table:nth-child(3) > tbody > tr")[1:]
    for row in rows:
        cols = row.find_all("td")
        try:
            registry_link = cols[3].find("a")
            name_link = cols[5].find("a")
            result = {
                "state": STATE,
                "name": name_link.text.strip() if name_link else "",
                "status": cols[2].text.strip(),
                "id": registry_link.text.strip() if registry_link else "",
                "url": (
                    f"https://egov.sos.state.or.us/br/{registry_link['href']}"
                    if registry_link and "href" in registry_link.attrs else ""
                ),
            }
            results.append(result)
        except Exception as e:
            continue
    return results


async def parse_html_details(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    async def extract_registered_agent() -> dict[str, Optional[str]]:
        agent_data = {"agent_name": None, "agent_address": None}
        agent_type = soup.find("td", string=re.compile("REGISTERED AGENT", re.I))
        if agent_type:
            name_table = agent_type.find_parent("table")
            if name_table:
                name_row = name_table.find_next_sibling("table")
                if name_row:
                    name_parts = name_row.find_all("td")
                    if len(name_parts) > 0:
                        del name_parts[0]
                    if len(name_parts) > 3:
                        del name_parts[3:]
                    agent_data["agent_name"] = " ".join(part.get_text(strip=True) for part in name_parts if part)
                addr_tables = name_row.find_next_siblings("table", limit=3)
                addr_lines = []
                for table in addr_tables:
                    tds_b = table.find_all("td")
                    if len(tds_b) > 1:
                        tds = tds_b[1]
                    else:
                        tds = []
                    addr_lines.extend(td.get_text(" ", strip=True) for td in tds if td.get_text(strip=True))
                    break
                agent_data["agent_address"] = ", ".join(addr_lines).strip() if addr_lines else None
        return agent_data

    async def extract_mailing_address() -> Optional[str]:
        mailing_type = soup.find("td", string=re.compile("MAILING ADDRESS", re.I))
        indicator = soup.find("font",
                              string=re.compile("Authorized Representative address is the mailing address", re.I))
        if mailing_type and not indicator:
            addr_table = mailing_type.find_parent("table")
            if addr_table:
                addr_lines = []
                addr_table = addr_table.find_next_sibling("table")
                if not addr_table:
                    return None
                tds_b = addr_table.find_all("td")
                if len(tds_b) > 1:
                    tds = tds_b[1]
                else:
                    tds = []
                addr_lines.extend(td.get_text(" ", strip=True) for td in tds if td.get_text(strip=True))
                return ", ".join(addr_lines).strip() if addr_lines else None


        if indicator:
            rep_type = soup.find("td", string=re.compile("AUTHORIZED REPRESENTATIVE", re.I))
            if rep_type:
                addr_table = rep_type.find_parent("table")
                addr_table = addr_table.find_next_sibling("table")
                addr_table = addr_table.find_next_sibling("table")
                if addr_table:
                    addr_lines = []
                    addr_table = addr_table.find_next_sibling("table")
                    if not addr_table:
                        return None
                    tds_b = addr_table.find_all("td")
                    if len(tds_b) > 1:
                        tds = tds_b[1]
                    else:
                        tds = []
                    addr_lines.extend(td.get_text(" ", strip=True) for td in tds if td.get_text(strip=True))
                    return ", ".join(addr_lines).strip() if addr_lines else None
        return None

    async def extract_roles(role_code: str) -> list[dict[str, Optional[str]]]:
        roles = []
        role_labels = soup.find_all("td", string=re.compile(fr"^{re.escape(role_code)}$", re.I))
        for role_label in role_labels:
            entry = {"name": None, "address": None}
            role_table = role_label.find_parent("table")
            if not role_table:
                continue
            name_table = role_table.find_next_sibling("table")
            if name_table:
                name_parts = name_table.find_all("td")
                if len(name_parts) > 0:
                    del name_parts[0]
                entry["name"] = " ".join(td.get_text(strip=True) for td in name_parts if td.get_text(strip=True))
                addr_lines = []
                name_table = name_table.find_next_sibling("table")
                if name_table:
                    tds_b = name_table.find_all("td")
                    if len(tds_b) > 1:
                        tds = tds_b[1]
                    else:
                        tds = []
                    addr_lines.extend(td.get_text(" ", strip=True) for td in tds if td.get_text(strip=True))
                entry["address"] = ", ".join(addr_lines).strip() if addr_lines else None
                roles.append(entry)
        return roles

    async def extract_registry_info() -> dict:
        info = {}
        table = soup.find("td", string=re.compile("Registry Nbr", re.I))
        if table:
            row = table.find_parent("tr").find_next_sibling("tr")
            cells = row.find_all("td")
            if len(cells) >= 5:
                info["registration_number"] = cells[0].get_text(strip=True).split()[0]
                info["entity_type"] = cells[1].get_text(strip=True)
                info["status"] = cells[2].get_text(strip=True)
                info["date_registered"] = cells[4].get_text(strip=True)
        return info

    async def extract_documents() -> list[dict[str, str]]:
        docs = []
        doc_links = soup.find_all("a", href=re.compile(r"ORSOSWebDrawer/Recordhtml/(\d+)"))

        for link in doc_links:
            href = link.get("href")
            match = re.search(r"Recordhtml/(\d+)", href)
            if not match:
                continue

            doc_id = match.group(1)
            row = link.find_parent("tr")
            tds = row.find_all("td") if row else []

            doc_name = tds[1].get_text(strip=True) if len(tds) > 1 else ""
            doc_date = tds[2].get_text(strip=True) if len(tds) > 2 else ""

            docs.append({
                "name": doc_name,
                "date": doc_date,
                "url": f"https://records.sos.state.or.us/ORSOSWebDrawer/Record/{doc_id}/File/document"
            })

        return docs

    async def extract_entity_name() -> Optional[str]:
        cell = soup.find("td", string=re.compile("Entity Name", re.I))
        if cell:
            return cell.find_next_sibling("td").get_text(strip=True)
        return None

    registry_info = await extract_registry_info()
    agent_data = await extract_registered_agent()
    return {
        "state": STATE,
        "name": await extract_entity_name(),
        **registry_info,
        **agent_data,
        "mailing_address": await extract_mailing_address(),
        "presidents": await extract_roles("PRE"),
        "secretaries": await extract_roles("SEC"),
        "registrants": await extract_roles("REG"),
        "members": await extract_roles("MEM"),
        "managers": await extract_roles("MGR"),
        "documents": await extract_documents()
    }
