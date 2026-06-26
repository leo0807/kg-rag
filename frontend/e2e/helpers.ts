import type { Page } from "@playwright/test";

/**
 * Log in via the login form and wait for redirect.
 */
export async function loginAs(
  page: Page,
  username: string,
  password: string,
): Promise<void> {
  await page.goto("/login");
  await page.getByPlaceholder("请输入6位工号").fill(username);
  await page.getByPlaceholder("请输入密码").fill(password);
  await page.getByRole("button", { name: /登\s*录/ }).click();
}

/**
 * Clear stored auth token and navigate to /login.
 */
export async function logout(page: Page): Promise<void> {
  await page.evaluate(() => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  });
  await page.goto("/login");
}
