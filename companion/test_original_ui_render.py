"""Headless original UI smoke; an optional standalone browser test."""
import json,unittest,os
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright=None

class OriginalRenderTests(unittest.TestCase):
    @unittest.skipUnless(sync_playwright is not None,'Playwright not installed in this venv; separate Edge smoke test available')
    def test_original_dashboard_renders(self):
        errors=[]
        with sync_playwright() as browser:
            b=browser.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=True)
            page=b.new_page(viewport={'width':1440,'height':900})
            page.on('pageerror',lambda exc:errors.append(str(exc)[:220]))
            resp=page.goto(os.environ.get('JARVIS_TEST_UI_URL','http://127.0.0.1:7430/'),wait_until='domcontentloaded',timeout=15000)
            page.wait_for_timeout(1800)
            text=page.locator('body').inner_text(timeout=8000)
            result={'http':resp.status if resp else None,'title':page.title(),'root_children':page.locator('#root > *').count(),'body_chars':len(text),'page_errors':errors[:7]}
            print(json.dumps(result,ensure_ascii=True))
            self.assertTrue(resp and resp.status==200 and result['root_children']>0 and len(text)>80 and not errors,result)
            b.close()

if __name__=='__main__':unittest.main(verbosity=2)

