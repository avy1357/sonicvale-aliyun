const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();

  const errors = [];
  page.on('pageerror', (err) => errors.push('PageError: ' + err.message));
  page.on('console', (msg) => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      errors.push('[' + msg.type() + '] ' + msg.text());
    }
  });

  await page.goto('http://localhost:5173', { waitUntil: 'networkidle0', timeout: 15000 });

  const title = await page.title();

  const navItems = await page.$$eval('a, .el-menu-item', (els) => els.map(e => e.textContent.trim()).filter(Boolean));

  await page.screenshot({ path: 'd:/aliyun-sonicvale/frontend_check.png', fullPage: true });

  const result = {
    page_title: title,
    screenshot: 'd:/aliyun-sonicvale/frontend_check.png',
    navigation_items: navItems.slice(0, 15),
    errors: errors.slice(0, 20),
    error_count: errors.length
  };

  console.log(JSON.stringify(result, null, 2));

  await browser.close();
})();
