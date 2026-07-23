import type { Page } from "@playwright/test";

export async function registerSyntheticUiLoopMocks(page: Page): Promise<void> {
  await page.route("**/api/synthetic/orders", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: [] }),
    });
  });
}
