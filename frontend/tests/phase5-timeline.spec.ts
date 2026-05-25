import { expect, test } from "@playwright/test";

test("timeline renders stages people events and filters", async ({ page }) => {
  const stamp = Date.now();
  const personName = `时间树人物${stamp}`;
  const stageName = `时间树阶段${stamp}`;
  const eventTitle = `时间树事件${stamp}`;

  await page.goto("/people");
  await page.getByLabel("姓名").fill(personName);
  await page.getByLabel("简介").fill("用于时间树验证");
  await page.getByRole("button", { name: "新建" }).click();
  await expect(page.getByRole("link", { name: personName })).toBeVisible();

  await page.goto("/self");
  await page.getByLabel("名称").fill(stageName);
  await page.getByLabel("类型").fill("工作");
  await page.getByLabel("开始").fill("2022-01-01");
  await page.getByRole("button", { name: "添加" }).click();
  await expect(page.locator(`input[name="name"][value="${stageName}"]`)).toBeVisible();

  await page.goto("/people");
  await page.getByRole("link", { name: personName }).click();
  await page.getByRole("button", { name: "关系" }).click();
  await page.getByLabel("关系类型").fill("朋友");
  await page.getByLabel("角色").fill("同事");
  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.getByText("朋友 · 同事")).toBeVisible();

  await page.getByRole("button", { name: "阶段" }).click();
  await page.locator('select[name="stage_id"]').selectOption({ label: stageName });
  await page.getByLabel("阶段角色").fill("项目同事");
  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.locator("div.font-medium").filter({ hasText: stageName })).toBeVisible();

  await page.getByRole("button", { name: "事件" }).click();
  await page.getByLabel("日期").fill("2024-03-10");
  await page.getByLabel("标题").fill(eventTitle);
  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.locator(`input[name="title"][value="${eventTitle}"]`)).toBeVisible();

  await page.goto("/timeline");
  await expect(page.getByRole("heading", { name: "时间树" })).toBeVisible();
  await page.getByLabel("阶段过滤").selectOption({ label: stageName });
  await page.getByLabel("关系类型过滤").selectOption("朋友");

  await expect(page.locator("div.text-base.font-semibold").filter({ hasText: stageName })).toBeVisible();
  await expect(page.getByText(personName)).toBeVisible();
  await expect(page.getByText("项目同事")).toBeVisible();
  await expect(page.getByText(eventTitle)).toBeVisible();

  await page.getByRole("link", { name: personName }).click();
  await expect(page.getByRole("heading", { name: personName })).toBeVisible();
});
