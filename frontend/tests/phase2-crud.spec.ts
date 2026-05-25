import { expect, test } from "@playwright/test";

test("manual graph maintenance flow", async ({ page }) => {
  const stamp = Date.now();
  const personName = `烟测人物${stamp}`;
  const otherName = `烟测朋友${stamp}`;
  const stageName = `烟测阶段${stamp}`;

  await page.goto("/people");
  await expect(page.getByRole("heading", { name: "人物" })).toBeVisible();
  await page.getByLabel("姓名").fill(personName);
  await page.getByLabel("别名").fill("烟测别名");
  await page.getByLabel("简介").fill("用于 Phase 2 浏览器验证");
  await page.getByRole("button", { name: "新建" }).click();
  await expect(page.getByRole("link", { name: personName })).toBeVisible();

  await page.getByLabel("姓名").fill(otherName);
  await page.getByRole("button", { name: "新建" }).click();
  await expect(page.getByRole("link", { name: otherName })).toBeVisible();

  await page.goto("/self");
  await expect(page.getByRole("heading", { name: "我的画像" })).toBeVisible();
  await page.getByLabel("沟通风格").fill("直接");
  await page.getByRole("button", { name: "保存" }).first().click();
  await expect(page.getByText("已保存我的画像")).toBeVisible();

  await page.getByLabel("名称").fill(stageName);
  await page.getByLabel("类型").fill("工作");
  await page.getByLabel("地点").fill("北京");
  await page.getByRole("button", { name: "添加" }).click();
  const stageNameInput = page.locator(`input[name="name"][value="${stageName}"]`);
  await expect(stageNameInput).toBeVisible();
  const stageRow = page.getByRole("row").filter({ has: stageNameInput });
  await stageRow.locator('input[name="location"]').fill("上海");
  await stageRow.getByRole("button", { name: "保存" }).click();
  await expect(stageRow.locator('input[name="location"][value="上海"]')).toBeVisible();

  await page.goto("/people");
  await page.getByRole("link", { name: personName }).click();
  await expect(page.getByRole("heading", { name: personName })).toBeVisible();
  await page.getByRole("button", { name: "关系" }).click();
  await page.locator('select[name="direction"]').selectOption("current_other");
  await page.locator('select[name="other_person_id"]').selectOption({ label: otherName });
  await page.getByLabel("关系类型").fill("朋友");
  await page.getByLabel("角色").fill("同事");
  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.getByText(`${personName} → ${otherName}`)).toBeVisible();

  await page.getByRole("button", { name: "阶段" }).click();
  await page.locator('select[name="stage_id"]').selectOption({ label: stageName });
  await page.getByLabel("阶段角色").fill("同事");
  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.locator("div.font-medium").filter({ hasText: stageName })).toBeVisible();

  await page.getByRole("button", { name: "事件" }).click();
  await page.getByLabel("标题").fill("完成一次烟测");
  await page.getByLabel("描述").fill("从人物到阶段的手工维护闭环");
  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.locator('input[name="title"][value="完成一次烟测"]')).toBeVisible();
});
