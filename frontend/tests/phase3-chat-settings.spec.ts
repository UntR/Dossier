import { expect, test } from "@playwright/test";

test.describe.configure({ mode: "serial" });

test("chat streams a reply and shows retrieved dossier context", async ({ page }) => {
  const stamp = Date.now();
  const personName = `阶段三老板${stamp}`;

  await page.goto("/people");
  await page.getByLabel("姓名").fill(personName);
  await page.getByLabel("别名").fill("张总");
  await page.getByLabel("简介").fill("直属上级，关注项目进度");
  await page.getByRole("button", { name: "新建" }).click();
  await expect(page.getByRole("link", { name: personName })).toBeVisible();

  await page.goto("/self");
  await page.getByLabel("沟通风格").fill("直接");
  await page.getByRole("button", { name: "保存" }).first().click();
  await expect(page.getByText("已保存我的画像")).toBeVisible();

  await page.goto("/chat");
  await expect(page.getByRole("heading", { name: "对话" })).toBeVisible();
  await page.getByLabel("消息").fill(`${personName} 说我最近进度有点慢，该怎么回？`);
  await page.getByRole("button", { name: "发送" }).click();

  await expect(page.getByText(`${personName} 说我最近进度有点慢，该怎么回？`)).toBeVisible();
  await expect(page.getByText("未配置可用模型")).toBeVisible();
  await expect(page.getByText("本次引用")).toBeVisible();
  await expect(page.getByText(personName).last()).toBeVisible();
  await expect(page.getByText("直属上级，关注项目进度")).toBeVisible();
});

test("settings saves model choices and shows provider status", async ({ page }) => {
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "设置" })).toBeVisible();

  await page.getByLabel("对话模型").selectOption("ollama/qwen2.5");
  await page.getByLabel("抽取模型").selectOption("anthropic/claude-haiku-4-5-20251001");
  await page.getByLabel("自动应用阈值").fill("0.7");
  await page.getByRole("button", { name: "保存" }).click();

  await expect(page.getByText("已保存设置")).toBeVisible();
  await expect(page.getByText("Anthropic", { exact: true })).toBeVisible();
  await expect(page.getByText("Ollama", { exact: true })).toBeVisible();

  await page.reload();
  await expect(page.getByLabel("对话模型")).toHaveValue("ollama/qwen2.5");
  await expect(page.getByLabel("自动应用阈值")).toHaveValue("0.7");
});

test("ending chat sends pending extractions to inbox review", async ({ page }) => {
  const stamp = Date.now();
  const personName = `阶段四老板${stamp}`;

  await page.goto("/people");
  await page.getByLabel("姓名").fill(personName);
  await page.getByLabel("别名").fill("老板");
  await page.getByLabel("简介").fill("直属上级");
  await page.getByRole("button", { name: "新建" }).click();
  await expect(page.getByRole("link", { name: personName })).toBeVisible();

  await page.goto("/self");
  await page.getByLabel("敏感点").fill("被否定");
  await page.getByRole("button", { name: "保存" }).first().click();
  await expect(page.getByText("已保存我的画像")).toBeVisible();

  await page.goto("/chat");
  await page.getByLabel("消息").fill("老板今天又说我加班不够，我其实很怕被催。");
  await page.getByRole("button", { name: "发送" }).click();
  await expect(page.getByText("未配置可用模型")).toBeVisible();

  await page.getByRole("button", { name: "结束会话" }).click();
  await expect(page.getByText(/抽取了 \d+ 项/)).toBeVisible();
  await page.getByRole("link", { name: "去审核" }).click();

  await expect(page.getByRole("heading", { name: "审核" })).toBeVisible();
  const relationshipRow = page.getByRole("row").filter({ hasText: "relationship_new" });
  const selfUpdateRow = page.getByRole("row").filter({ hasText: "self_update" }).filter({ hasText: "被催" });
  await expect(relationshipRow).toContainText(personName);
  await expect(selfUpdateRow).toContainText("sensitivities");
  await expect(selfUpdateRow).toContainText("现状");
  await expect(selfUpdateRow).toContainText("被否定");
  await expect(selfUpdateRow).toContainText("新值");
  await relationshipRow.getByRole("button", { name: "接受" }).click();
  await expect(page.getByText("已接受 1 条")).toBeVisible();
  await selfUpdateRow.getByRole("button", { name: "编辑" }).click();
  await selfUpdateRow.getByLabel("新值 sensitivities").fill('["被催","临时改需求"]');
  await selfUpdateRow.getByRole("button", { name: "保存并接受" }).click();
  await expect(page.getByText("已编辑并接受 1 条")).toBeVisible();
  await expect(selfUpdateRow).toHaveCount(0);

  await page.goto("/self");
  await expect(page.getByLabel("敏感点")).toHaveValue("被催，临时改需求");

  await page.goto("/people");
  await page.getByRole("link", { name: personName }).click();
  await page.getByRole("button", { name: "关系" }).click();
  await expect(page.locator("div.text-slate-500").filter({ hasText: `我 → ${personName}` })).toBeVisible();
  await expect(page.getByText("上下级")).toBeVisible();
});

test("inbox edits pending extraction and undoes auto applied event", async ({ page }) => {
  const stamp = Date.now();
  const personName = `审核编辑老板${stamp}`;
  const eventTitle = `${personName}提到加班不够`;

  await page.goto("/people");
  await page.getByLabel("姓名").fill(personName);
  await page.getByLabel("别名").fill("老板");
  await page.getByLabel("简介").fill("直属上级");
  await page.getByRole("button", { name: "新建" }).click();
  await expect(page.getByRole("link", { name: personName })).toBeVisible();

  await page.goto("/chat");
  await page.getByLabel("消息").fill("老板今天又说我加班不够，该怎么回？");
  await page.getByRole("button", { name: "发送" }).click();
  await expect(page.getByText("未配置可用模型")).toBeVisible();
  await page.getByRole("button", { name: "结束会话" }).click();
  await expect(page.getByText(/抽取了 \d+ 项/)).toBeVisible();
  await page.getByRole("link", { name: "去审核" }).click();

  const relationshipRow = page.getByRole("row").filter({ hasText: "relationship_new" }).filter({ hasText: personName });
  await relationshipRow.getByRole("button", { name: "编辑" }).click();
  const payloadInput = relationshipRow.getByLabel("Payload JSON");
  const payload = JSON.parse(await payloadInput.inputValue());
  await payloadInput.fill(JSON.stringify({ ...payload, relation_type: "协作", role: "项目负责人" }));
  await relationshipRow.getByRole("button", { name: "保存并接受" }).click();
  await expect(page.getByText("已编辑并接受 1 条")).toBeVisible();

  await page.goto("/people");
  await page.getByRole("link", { name: personName }).click();
  await page.getByRole("button", { name: "关系" }).click();
  await expect(page.getByText("协作")).toBeVisible();
  await expect(page.getByText("项目负责人")).toBeVisible();

  await page.goto("/inbox");
  await page.getByLabel("状态筛选").selectOption("auto_applied");
  const eventRow = page.getByRole("row").filter({ hasText: "event_new" }).filter({ hasText: eventTitle });
  await expect(eventRow).toBeVisible();
  await eventRow.getByRole("button", { name: "撤销" }).click();
  await expect(page.getByText("已撤销 1 条")).toBeVisible();

  await page.goto("/people");
  await page.getByRole("link", { name: personName }).click();
  await page.getByRole("button", { name: "事件" }).click();
  await expect(page.getByText(eventTitle)).toHaveCount(0);
});
