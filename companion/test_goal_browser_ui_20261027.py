import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,
            executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
            args=['--autoplay-policy=no-user-gesture-required'])
        page=await browser.new_page(viewport={'width':1366,'height':860})
        events=[]
        page.on('request',lambda r:events.append(('request',r.url)) if '/api/tts' in r.url else None)
        page.on('console',lambda c:events.append(('console',c.text[:125])) if '[App:TTS]' in c.text else None)
        await page.goto('http://127.0.0.1:7353/',wait_until='domcontentloaded',timeout=23000)
        await page.wait_for_timeout(1700)
        fields=page.locator('input[placeholder],textarea[placeholder]')
        print('PAGE_TITLE',await page.title(),flush=True)
        print('INPUT_COUNT',await fields.count(),flush=True)
        for i in range(await fields.count()):
            print('FIELD',i,await fields.nth(i).get_attribute('placeholder'),flush=True)
        await browser.close()
asyncio.run(main())
