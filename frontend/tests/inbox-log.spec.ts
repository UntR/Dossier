import { expect, test } from "@playwright/test";

test("inbox keeps list visible and logs diff fetch failures", async ({ page }) => {
  await page.route("**/api/extractions?status=pending", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        data: {
          items: [
            {
              id: 9001,
              session_id: null,
              kind: "self_update",
              target_id: null,
              payload: { patches: { sensitivities: ["临时改需求"] } },
              confidence: 0.8,
              status: "pending",
              applied_at: null,
              created_at: "2026-05-24T11:00:00",
            },
          ],
        },
      }),
    });
  });
  await page.route("**/api/self", async (route) => {
    await route.abort("failed");
  });

  await page.goto("/inbox");

  await expect(page.getByRole("row").filter({ hasText: "self_update" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "日志" })).toBeVisible();
  await expect(page.getByText("/api/self").first()).toBeVisible();
  await expect(page.getByText(/失败|Failed to fetch/)).toBeVisible();
});

test("inbox repairs failed extraction and keeps it pending for review", async ({ page }) => {
  let item = {
    id: 42,
    session_id: null,
    kind: "event_new",
    target_id: null,
    payload: {
      occurred_at: "近期",
      title: "米饼事件",
      description: "户外散步时女儿想踩落地零食。",
      participants: [{ type: "name", name: "女儿" }],
      source: "llm_memory_import",
    },
    confidence: 0.8,
    status: "pending",
    applied_at: null,
    created_at: "2026-05-24T11:00:00",
  };

  await page.route("**/api/extractions?status=pending", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ ok: true, data: { items: [item] } }),
    });
  });
  await page.route("**/api/extractions/42/accept", async (route) => {
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({ ok: false, error: "Invalid isoformat string: '近期'" }),
    });
  });
  await page.route("**/api/extractions/42/repair", async (route) => {
    expect(route.request().method()).toBe("POST");
    const request = JSON.parse(route.request().postData() ?? "{}") as { error?: string };
    expect(request.error).toContain("Invalid isoformat string");
    item = { ...item, payload: { ...item.payload, occurred_at: null } };
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ ok: true, data: item }),
    });
  });

  await page.goto("/inbox");
  const row = page.getByRole("row").filter({ hasText: "event_new" });
  await row.getByRole("button", { name: "接受", exact: true }).click();
  await page.getByRole("button", { name: "修正格式" }).click();

  await expect(page.getByLabel("Payload JSON")).toHaveValue(/"occurred_at": null/);
  await expect(page.getByRole("button", { name: "保存并接受" })).toBeVisible();
  await expect(page.getByText("/api/extractions/42/repair")).toHaveCount(2);
});
