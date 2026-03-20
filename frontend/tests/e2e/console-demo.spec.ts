import { expect, test } from '@playwright/test';

test('demo boot renders the main McKAInsey screens', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.mk-topbar__title')).toHaveText('McKAInsey');
  await expect(page.getByRole('button', { name: 'Scenario Setup' })).toBeVisible();

  await page.getByRole('button', { name: 'Population Sampling' }).click();
  await expect(page.getByText('Document-Aware Sampling')).toBeVisible();

  await page.getByRole('button', { name: 'Simulation' }).click();
  await expect(page.getByText('Live Simulation Control')).toBeVisible();

  await page.getByRole('button', { name: 'Friction Map' }).click();
  await expect(page.getByText('Singapore Friction Map')).toBeVisible();

  await page.getByRole('button', { name: 'Interaction Hub' }).click();
  await expect(page.getByText('Unified Interaction Hub')).toBeVisible();
});
