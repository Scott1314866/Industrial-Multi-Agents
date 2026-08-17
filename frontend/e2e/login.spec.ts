import { expect, test } from '@playwright/test'

test('renders the industrial login experience', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: '进入控制台' })).toBeVisible()
  await expect(page.getByText('让每一次')).toBeVisible()
  await expect(page.getByRole('button', { name: /安全登录/ })).toBeVisible()
})

