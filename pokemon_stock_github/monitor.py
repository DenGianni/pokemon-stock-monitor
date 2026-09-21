import asyncio
import json
import re
from pathlib import Path
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
STATE = ROOT / 'state.json'
BOL_URL = 'https://www.bol.com/be/nl/l/pokemon-trading-cards-engels/20303/4278866641%2B55042%2B38520/'
MM_URL = 'https://www.mediamarkt.be/nl/category/pokemon-kaarten-326.html'
VERSION = 'github-1.0'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0 Safari/537.36',
    'Accept-Language': 'nl-BE,nl;q=0.9,en;q=0.8'
}
BAD = ('acryl case','acrylbox','sleeve','sleeves','toploader','binder','verzamelmap',
       'portfolio','deckbox','deck box','opbergdoos','card case','display case','hoes')
NON_ENGLISH = ('frans','français','cartes à collectionner','coffret','boîte',
               'deutsch','duits','italiano','italiaans','español','spanish','german')
PRODUCT_WORDS = ('booster','etb','elite trainer','trading cards','trading card',
                 'booster box','booster pack','bundle','collection','premium','special box','tin','blister','box')


def load(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def text(x):
    return re.sub(r'\s+', ' ', x or '').strip()


def english_and_relevant(title, context=''):
    t = text(title).lower()
    c = text(context).lower()
    s = t + ' ' + c[:800]
    if 'pokemon' not in s and 'pokémon' not in s:
        return False
    if any(x in t for x in BAD):
        return False
    if any(x in t for x in NON_ENGLISH):
        return False
    if re.search(r'(^|[\s\-_])(fr|de|it|es)([\s\-_]|$)', t):
        return False
    return any(k in s for k in PRODUCT_WORDS)


def price(s):
    m = re.search(r'€\s*([0-9]{1,4}(?:[.,][0-9]{2})?)|([0-9]{1,4}(?:[.,][0-9]{2})?)\s*€', s)
    return (m.group(1) or m.group(2)).replace(',', '.') if m else ''


def seller_from(s):
    m = re.search(r'Verkoop door\s+(.+?)(?:\s+Wat je kan verwachten|\s+Prijsinformatie|$)', s, re.I)
    return m.group(1).strip()[:100] if m else ''


def nearest_context(a, levels=3):
    parent = a
    for _ in range(levels):
        parent = parent.parent or parent
    return text(parent.get_text(' ', strip=True))


def bol(html):
    soup = BeautifulSoup(html, 'html.parser')
    out = {}
    for a in soup.select('a[href*="/nl/p/"]'):
        title = text(a.get_text(' ', strip=True) or a.get('aria-label') or a.get('title'))
        if len(title) < 8:
            continue
        context = nearest_context(a, 3)
        if not english_and_relevant(title, context):
            continue
        url = requests.compat.urljoin('https://www.bol.com', a['href'].split('?')[0])
        out[url] = {
            'store': 'Bol.com', 'title': title[:180], 'url': url,
            'price': price(context),
            'stock': bool(re.search(r'op voorraad|bestelbaar|morgen in huis|leverbaar', context, re.I)),
            'seller': seller_from(context)
        }
    return list(out.values())


async def mediamarkt_playwright():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(locale='nl-BE', user_agent=HEADERS['User-Agent'])
        try:
            await page.goto(MM_URL, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(2500)
            for _ in range(6):
                buttons = page.get_by_role('button', name=re.compile(r'toon .*meer producten|show .*more products', re.I))
                if await buttons.count() == 0:
                    break
                try:
                    await buttons.last.click(timeout=5000)
                    await page.wait_for_timeout(1000)
                except Exception:
                    break
            anchors = await page.locator('a[href*="/product/"]').evaluate_all("""
                els => els.map(a => ({
                    href: a.href,
                    text: (a.innerText || a.getAttribute('aria-label') || a.getAttribute('title') || '').trim(),
                    parentText: (a.parentElement?.parentElement?.innerText || '').trim()
                }))
            """)
            out = {}
            for x in anchors:
                title = text(x.get('text',''))
                context = text(x.get('parentText',''))
                if len(title) < 8 or not english_and_relevant(title, context):
                    continue
                url = x['href'].split('?')[0]
                out[url] = {
                    'store': 'MediaMarkt België', 'title': title[:180], 'url': url,
                    'price': price(context),
                    'stock': bool(re.search(r'online op voorraad|op voorraad|in winkelwagen|bestel', context, re.I)),
                    'seller': 'MediaMarkt'
                }
            return list(out.values())
        finally:
            await browser.close()


def get(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def notify(webhook, item, event):
    emoji = '🟢' if event == 'NEW' else '♻️'
    label = 'NIEUW OP VOORRAAD' if event == 'NEW' else 'RESTOCK'
    fields = [
        {'name':'Winkel','value':item['store'],'inline':True},
        {'name':'Prijs','value':('€ '+item['price']) if item['price'] else 'Niet gevonden','inline':True},
    ]
    if item.get('seller'):
        fields.append({'name':'Verkoper','value':item['seller'],'inline':False})
    payload = {'username':'Pokémon Stock Monitor','embeds':[{
        'title':f'{emoji} {label}','description':item['title'],'url':item['url'],
        'fields':fields,'footer':{'text':'Pokémon Stock Monitor'},
        'timestamp':datetime.now(timezone.utc).isoformat()
    }]}
    r = requests.post(webhook, json=payload, timeout=20)
    r.raise_for_status()


async def scan():
    items = []
    try:
        html = await asyncio.to_thread(get, BOL_URL)
        found = bol(html); items += found
        print(f'[{datetime.now():%Y-%m-%d %H:%M:%S}] Bol.com: {len(found)} relevante producten')
    except Exception as e:
        print(f'[{datetime.now():%H:%M:%S}] Bol.com: fout: {e}')

    try:
        found = await mediamarkt_playwright()
        items += found
        print(f'[{datetime.now():%Y-%m-%d %H:%M:%S}] MediaMarkt België: {len(found)} relevante producten')
    except Exception as e:
        print(f'[{datetime.now():%H:%M:%S}] MediaMarkt België: fout: {e}')
    return {x['url']: x for x in items}


async def main():
    webhook = __import__('os').environ.get('DISCORD_WEBHOOK','').strip()
    if not webhook.startswith('https://discord.com/api/webhooks/'):
        raise SystemExit('DISCORD_WEBHOOK secret ontbreekt of is ongeldig.')

    state = load(STATE, {})
    current = await scan()
    changed = False

    # First run = baseline, no notification spam.
    if not state:
        for u, x in current.items():
            state[u] = {'stock': x['stock'], 'title': x['title'], 'store': x['store']}
        save(STATE, state)
        print('Beginstatus opgeslagen; bestaande voorraad geeft geen meldingen.')
        return

    for u, x in current.items():
        old = state.get(u)
        if x['stock'] and (old is None or not old.get('stock', False)):
            try:
                notify(webhook, x, 'NEW' if old is None else 'RESTOCK')
                print('  Discord ->', x['title'])
            except Exception as e:
                print('  Discord fout:', e)
        new_state = {'stock': x['stock'], 'title': x['title'], 'store': x['store']}
        if old != new_state:
            state[u] = new_state
            changed = True

    if changed:
        save(STATE, state)
    else:
        # Keep the file absent/unchanged when there is nothing new. This avoids commits every 5 minutes.
        print('Geen voorraadstatuswijzigingen.')


if __name__ == '__main__':
    asyncio.run(main())
