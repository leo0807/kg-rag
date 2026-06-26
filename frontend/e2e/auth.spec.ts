import { test, expect } from "@playwright/test";
import { loginAs } from "./helpers";

const VALID_USER = "000001";
const VALID_PASS = "admin123";

test.describe("Authentication", () => {
  test("login with valid credentials redirects to /query or /library", async ({
    page,
  }) => {
    await loginAs(page, VALID_USER, VALID_PASS);

    // Wait for navigation away from /login
    await page.waitForURL(/\/(query|library)/, { timeout: 10000 });
    const url = page.url();
    expect(url).toMatch(/\/(query|library)/);
  });

  test("login with invalid credentials shows error message", async ({
    page,
  }) => {
    await loginAs(page, "000000", "wrongpassword");

    // Should remain on /login and show an error
    await expect(page).toHaveURL(/\/login/);
    const errorLocator = page.locator("text=/登录失败|用户名|密码|错误|invalid/i");
    await expect(errorLocator.first()).toBeVisible({ timeout: 8000 });
  });

  test("accessing /library without login redirects to /login", async ({
    page,
  }) => {
    // Clear any stored token first
    await page.goto("/login");
    await page.evaluate(() => {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
    });

    await page.goto("/library");
    await page.waitForURL(/\/login/, { timeout: 10000 });
    expect(page.url()).toContain("/login");
  });
});
