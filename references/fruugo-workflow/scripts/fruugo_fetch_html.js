const { chromium } = require('playwright');

const targetUrl = process.argv[2];
const waitMs = Number.parseInt(process.argv[3] || '4000', 10);
if (!targetUrl) {
  console.error('Usage: node fruugo_fetch_html.js <url> [waitMs]');
  process.exit(1);
}

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true, channel: 'chrome' });
  } catch (error) {
    return chromium.launch({ headless: true });
  }
}

(async () => {
  const browser = await launchBrowser();
  const page = await browser.newPage({
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ' +
      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
  });

  page.setDefaultTimeout(60000);
  await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(Number.isFinite(waitMs) && waitMs >= 0 ? waitMs : 4000);
  process.stdout.write(await page.content());
  await browser.close();
})().catch((error) => {
  console.error(String(error && error.stack ? error.stack : error));
  process.exit(1);
});
