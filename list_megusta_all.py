"""List ALL Me Gusta gallery items including blocked ones, to see what's available."""
import json, re, sys, time
sys.path.insert(0, ".")
from memescrape import make_session, fetch_html
from bs4 import BeautifulSoup

USED_IDS = {"1941912","3055187","2634604","2093625","2093626","1358553","1484749","1945179"}

session = make_session()

all_items = []
for pg in range(1, 6):
    url = "https://knowyourmeme.com/memes/me-gusta/photos" + (f"?page={pg}" if pg > 1 else "")
    html = fetch_html(session, url)
    if not html:
        break
    soup = BeautifulSoup(html, "html.parser")
    items_this_page = 0
    for a in soup.select("a.item"):
        img = a.find("img")
        if not img:
            continue
        orig = img.get("data-image","") or img.get("src","")
        href = a.get("href","")
        pid_m = re.search(r"/photos/(\d+)", href)
        pid = pid_m.group(1) if pid_m else "?"
        title = a.get("data-title","")
        alt = img.get("alt","")
        status = "USED" if pid in USED_IDS else "AVAILABLE"
        print(f"  pg{pg} pid={pid:>10} [{status}] title={title!r}  url_ext={orig[-10:]!r}")
        items_this_page += 1
        all_items.append({"pid": pid, "title": title, "url": orig, "alt": alt})
    print(f"  -- page {pg}: {items_this_page} items")
    if items_this_page == 0:
        break
    time.sleep(1.5)

print(f"\nTotal: {len(all_items)} items")
print(f"Available (not used): {sum(1 for i in all_items if i['pid'] not in USED_IDS)}")
