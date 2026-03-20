import { expect, test } from '@playwright/test';

test('live mode surfaces session bootstrap or a clear failure', async ({ page }) => {
  await page.goto('/#stage-1');
  await page.getByRole('button', { name: 'Live' }).click();
  await expect(page.locator('.mk-topbar__subtitle')).toContainText(/Status/);
});
