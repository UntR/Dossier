import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const root = "/Users/rzhang15/Documents/Dossier";

test.describe.configure({ mode: "serial" });

test("import page creates pending extractions from file text and llm memory", async ({ page }) => {
  const stamp = Date.now();
  const personName = `导入对象${stamp}`;
  const fileNote = `文件导入备注${stamp}`;
  const pastedNote = `粘贴导入备注${stamp}`;
  const llmPerson = `LLM导入人物${stamp}`;
  const skippedLlmPerson = `LLM跳过人物${stamp}`;
  const llmEvent = `LLM导入事件${stamp}`;

  await page.goto("/people");
  await page.getByLabel("姓名").fill(personName);
  await page.getByRole("button", { name: "新建" }).click();
  await expect(page.getByRole("link", { name: personName })).toBeVisible();

  await page.goto("/import");
  await expect(page.getByRole("heading", { name: "导入" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "文件" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "LLM 记忆" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "文本粘贴" })).toBeVisible();

  await page.getByRole("tab", { name: "文件" }).click();
  await page.getByLabel("关联人物").selectOption({ label: personName });
  await page.setInputFiles('input[name="file"]', {
    name: "memory.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(fileNote, "utf-8")
  });
  await page.getByRole("button", { name: "导入文件" }).click();
  await expect(page.getByText("已导入 1 条")).toBeVisible();

  await page.getByRole("tab", { name: "文本粘贴" }).click();
  await page.getByLabel("粘贴文本").fill(pastedNote);
  await page.getByRole("button", { name: "导入文本" }).click();
  await expect(page.getByText("已导入 1 条")).toBeVisible();

  await page.getByRole("tab", { name: "LLM 记忆" }).click();
  await expect(page.getByLabel("提示词模板")).toContainText("people");
  await page.getByLabel("LLM JSON").fill(JSON.stringify({
    people: [
      { name: llmPerson, aliases: ["导入别名"], bio: "来自外部 LLM 记忆" },
      { name: skippedLlmPerson, aliases: [], bio: "用户取消导入的人物" }
    ],
    events: [{ occurred_at: "2026-05-23", title: llmEvent, description: "来自导入测试", participants: [llmPerson] }],
    self: { communication_style: "直接" }
  }));
  await expect(page.getByRole("group", { name: "LLM JSON 结构化预览" })).toBeVisible();
  await expect(page.getByLabel(`导入人物 ${llmPerson}`)).toBeChecked();
  await expect(page.getByLabel(`导入人物 ${skippedLlmPerson}`)).toBeChecked();
  await expect(page.getByLabel(`导入事件 ${llmEvent}`)).toBeChecked();
  await expect(page.getByLabel("导入我的画像更新")).toBeChecked();
  await page.getByLabel(`导入人物 ${skippedLlmPerson}`).uncheck();
  await page.getByLabel("导入我的画像更新").uncheck();
  await expect(page.getByText("已选择 2 / 4 条")).toBeVisible();
  await page.getByRole("button", { name: "导入 LLM 记忆" }).click();
  await expect(page.getByText("已导入 2 条")).toBeVisible();

  await page.goto("/inbox");
  await expect(page.getByRole("row").filter({ hasText: "note_new" }).filter({ hasText: fileNote })).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "note_new" }).filter({ hasText: pastedNote })).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "person_new" }).filter({ hasText: llmPerson })).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "person_new" }).filter({ hasText: skippedLlmPerson })).toHaveCount(0);
  await expect(page.getByRole("row").filter({ hasText: "event_new" }).filter({ hasText: llmEvent })).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "self_update" }).filter({ hasText: "communication_style" })).toHaveCount(0);
});

test("file import shows batch progress while importing multiple files", async ({ page }) => {
  const stamp = Date.now();
  const firstNote = `批量文件一${stamp}`;
  const secondNote = `批量文件二${stamp}`;
  let requestCount = 0;
  let releaseFirstRequest: () => void = () => {};
  let releaseSecondRequest: () => void = () => {};
  const firstRequestPaused = new Promise<void>((resolve) => {
    releaseFirstRequest = resolve;
  });
  const secondRequestPaused = new Promise<void>((resolve) => {
    releaseSecondRequest = resolve;
  });

  await page.route("**/api/import/file", async (route) => {
    requestCount += 1;
    if (requestCount === 1) {
      await firstRequestPaused;
    }
    if (requestCount === 2) {
      await secondRequestPaused;
    }
    await route.continue();
  });

  await page.goto("/import");
  await page.setInputFiles('input[name="file"]', [
    {
      name: "first.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(firstNote, "utf-8")
    },
    {
      name: "second.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(secondNote, "utf-8")
    }
  ]);
  await page.getByRole("button", { name: "导入文件" }).click();
  await expect(page.getByRole("status", { name: "导入进度" })).toContainText("正在导入 1 / 2：first.txt");
  await expect(page.getByRole("button", { name: "导入文件" })).toBeDisabled();

  releaseFirstRequest();

  await expect(page.getByRole("status", { name: "导入进度" })).toContainText("正在导入 2 / 2：second.txt");
  releaseSecondRequest();
  await expect(page.getByText("已导入 2 条，处理 2 个文件")).toBeVisible();

  await page.goto("/inbox");
  await expect(page.getByRole("row").filter({ hasText: "note_new" }).filter({ hasText: firstNote })).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "note_new" }).filter({ hasText: secondNote })).toBeVisible();
});

test("settings exports dossier to obsidian path and downloads zip", async ({ page }) => {
  const stamp = Date.now();
  const personName = `导出对象${stamp}`;
  const exportPath = path.join(root, ".e2e-data", "exports", `ui-${stamp}`);

  fs.rmSync(exportPath, { force: true, recursive: true });

  await page.goto("/people");
  await page.getByLabel("姓名").fill(personName);
  await page.getByRole("button", { name: "新建" }).click();
  await expect(page.getByRole("link", { name: personName })).toBeVisible();

  await page.goto("/settings");
  await page.getByLabel("Obsidian 导出路径").fill(exportPath);
  await page.getByRole("button", { name: "保存" }).click();
  await expect(page.getByText("已保存设置")).toBeVisible();

  await page.getByRole("button", { name: "导出到 Obsidian" }).click();
  await expect(page.getByText(/已导出 \d+ 人/)).toBeVisible();
  expect(fs.existsSync(path.join(exportPath, "people", `${personName}.md`))).toBe(true);

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "下载 ZIP" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("dossier-export.zip");
});
