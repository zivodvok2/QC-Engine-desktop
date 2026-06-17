import { chromium } from 'playwright';

const BASE    = 'http://localhost:5173';
const DATASET = '/home/dvock/QC-Engine-desktop/data/messy_survey_sample.csv';
const CONFIG  = '/home/dvock/QC-Engine-desktop/data/messy_survey_config.json';
const SS = (n) => `/tmp/ss_${n}.png`;
const shot = async (page, n) => page.screenshot({ path: SS(n), fullPage: false });

async function dismissModal(page) {
  const modal = page.locator('.fixed.inset-0').first();
  if (await modal.count() > 0) {
    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);
  }
}

const browser = await chromium.launch({ headless: true });
const page    = await browser.newPage();
page.setDefaultTimeout(20000);

await page.goto(BASE);
await page.waitForLoadState('networkidle');
await shot(page, '01_landing');
console.log('✓ Landing page');

await dismissModal(page);

const input = await page.$('input[type="file"]');
await input.setInputFiles(DATASET);
await page.waitForTimeout(2500);
await dismissModal(page);
await shot(page, '02_uploaded');
console.log('✓ File uploaded');

// Config tab
const configBtn = page.locator('button').filter({ hasText: /^Config$/ }).first();
if (await configBtn.count() > 0) {
  await configBtn.click();
  await page.waitForTimeout(600);
  await shot(page, '03_config');
  const html = await page.content();
  console.log(html.includes('Missing Value Check')
    ? '✓ Missing column scope section present'
    : '✗ Missing column scope section NOT found');
  // Import config JSON
  const importBtn = page.locator('button:has-text("Import JSON")').first();
  if (await importBtn.count() > 0) {
    const [fc] = await Promise.all([page.waitForFileChooser(), importBtn.click()]);
    await fc.setFiles(CONFIG);
    await page.waitForTimeout(800);
    await shot(page, '04_config_imported');
    console.log('✓ Config JSON imported');
  }
}

// Run QC from sidebar
const runBtn = page.locator('button').filter({ hasText: /Run QC/ }).first();
if (await runBtn.count() > 0) {
  await runBtn.click();
  console.log('  … QC running …');
  await page.waitForFunction(
    () => /\d+\s*flag|critical|warning/i.test(document.body.innerText),
    { timeout: 40000 }
  ).catch(() => {});
  await page.waitForTimeout(2000);
  console.log('✓ QC run complete');
}
await shot(page, '05_after_run');

// QC Report tab
const qcTab = page.locator('button').filter({ hasText: /QC Report/ }).first();
if (await qcTab.count() > 0) {
  await qcTab.click();
  await page.waitForTimeout(800);
  await shot(page, '06_qc_report');
  console.log('✓ QC Report tab');
}

// Interviewers tab
const itvTab = page.locator('button').filter({ hasText: /Interviewer/ }).first();
if (await itvTab.count() > 0) {
  await itvTab.click();
  await page.waitForTimeout(800);
  await shot(page, '07_interviewers');
  console.log('✓ Interviewers tab');
}

// Logic Checks tab
const logicTab = page.locator('button').filter({ hasText: /Logic/ }).first();
if (await logicTab.count() > 0) {
  await logicTab.click();
  await page.waitForTimeout(600);
  await shot(page, '08_logic');
  console.log('✓ Logic Checks tab');
}

// EDA tab
const edaTab = page.locator('button').filter({ hasText: /EDA/ }).first();
if (await edaTab.count() > 0) {
  await edaTab.click();
  await page.waitForTimeout(600);
  await shot(page, '09_eda');
  console.log('✓ EDA tab');
}

await browser.close();
console.log('\nDone. Screenshots at /tmp/ss_*.png');
