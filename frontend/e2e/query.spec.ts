import { test, expect } from "@playwright/test";
import { loginAs, logout } from "./helpers";

const VALID_USER = "000001";
const VALID_PASS = "admin123";

test.describe("Query & Library pages", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, VALID_USER, VALID_PASS);
    // Wait until we've left the login page
    await page.waitForURL(/\/(query|library)/, { timeout: 10000 });
  });

  test.afterEach(async ({ page }) => {
    await logout(page);
  });

  test("navigate to /query and see question input", async ({ page }) => {
    await page.goto("/query");
    // The query page should have an input or textarea for entering questions
    const inputLocator = page.locator(
      'textarea, input[type="text"], [placeholder*="问"], [placeholder*="输入"], [placeholder*="提问"]',
    );
    await expect(inputLocator.first()).toBeVisible({ timeout: 8000 });
  });

  test("submit a question and loading state appears", async ({ page }) => {
    await page.goto("/query");

    const inputLocator = page.locator(
      'textarea, input[type="text"], [placeholder*="问"], [placeholder*="输入"], [placeholder*="提问"]',
    );
    await inputLocator.first().fill("What is CPS1000?");

    // Click send button or press Enter
    const sendBtn = page.locator('button[type="submit"], button:has-text("发送"), button:has-text("搜索"), button:has-text("Send")');
    if (await sendBtn.count() > 0) {
      await sendBtn.first().click();
    } else {
      await inputLocator.first().press("Enter");
    }

    // Loading indicator should appear (spinner, "加载中", "思考中", etc.)
    const loadingLocator = page.locator(
      '[class*="spin"], [class*="loading"], [class*="animate"], text=/加载|思考|Loading|loading/i',
    );
    await expect(loadingLocator.first()).toBeVisible({ timeout: 8000 });
  });

  test("navigate to /library and see document list", async ({ page }) => {
    await page.goto("/library");
    // Library should show a list/table of documents
    const listLocator = page.locator(
      'table, [class*="list"], [class*="grid"], [role="list"], [role="row"]',
    );
    await expect(listLocator.first()).toBeVisible({ timeout: 10000 });
  });
});
