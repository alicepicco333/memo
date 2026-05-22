import sys
sys.path.insert(0, '.')
from memescrape import make_session, fetch_html
from bs4 import BeautifulSoup

session = make_session()
html = fetch_html(session, 'https://knowyourmeme.com/memes/distracted-boyfriend/photos')
if not html:
    print('Failed')
    sys.exit(1)

soup = BeautifulSoup(html, 'html.parser')
import sys
sys.path.insert(0, '.')
from memescrape import make_session, fetch_html

session = make_session()
html = fetch_html(session, 'https://knowyourmeme.com/memes/distracted-boyfriend/photos')
if html:
    with open('_gallery_probe.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print('Saved', len(html), 'chars')
else:
    print('Failed')
