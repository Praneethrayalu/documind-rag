"""Local UI smoke test with real upload, question submission and screenshots."""
import os
import subprocess
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    log = open('/tmp/documind-streamlit.log', 'w')  # noqa: SIM115
    server = subprocess.Popen([str(ROOT / '.venv/bin/streamlit'), 'run', 'app.py', '--server.headless=true', '--browser.gatherUsageStats=false', '--server.maxUploadSize=25'], cwd=ROOT, stdout=log, stderr=log, env={**os.environ, 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'})
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=1)
                break
            except OSError:
                time.sleep(1)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1440, 'height': 1100})
            page.goto('http://127.0.0.1:8501')
            page.get_by_text('Upload a PDF to begin.', exact=False).wait_for(timeout=30000)
            page.get_by_text('FAISS + BM25', exact=True).wait_for()
            page.screenshot(path=str(ROOT / 'docs/ui-empty.png'), full_page=True)
            page.locator('input[type=file]').set_input_files(str(ROOT / 'data/sample/documind-handbook.pdf'))
            page.get_by_placeholder('What is the incident escalation procedure?').wait_for(timeout=90000)
            page.get_by_placeholder('What is the incident escalation procedure?').fill('How quickly must a critical incident be acknowledged?')
            page.get_by_placeholder('What is the incident escalation procedure?').press('Enter')
            page.get_by_role('button', name='Find evidence').click()
            page.get_by_text('Source evidence', exact=True).wait_for(timeout=30000)
            assert page.get_by_text('Critical incidents must be acknowledged within fifteen minutes. [1]', exact=False).count()
            page.screenshot(path=str(ROOT / 'docs/ui-answer.png'), full_page=True)
            print('UI passed: upload, real embedding index, query, answer, citations; screenshots saved')
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=20)
        log.close()


if __name__ == '__main__':
    main()
