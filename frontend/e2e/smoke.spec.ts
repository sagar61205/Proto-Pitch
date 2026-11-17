import { expect, test } from "@playwright/test";

const HOSTILE = '<img src=x onerror="window.__xss = true">';

test("create a project, watch its set-up job finish, archive and restore it", async ({ page }) => {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(message.text());
  });
  page.on("pageerror", (error) => problems.push(error.message));

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
  await expect(page.getByText("No projects yet")).toBeVisible();
  await expect(page.getByTestId("generation-status")).toBeVisible();
  await expect(page.getByText("None configured — not needed")).toBeVisible();

  await page.getByRole("navigation").getByRole("link", { name: "New project" }).click();
  await page.getByLabel("Company").fill("Acme BV");
  await page.getByLabel("Role").fill("Senior Data Scientist");
  await page
    .getByLabel("Job description")
    .fill(`We need a Senior Data Scientist for recommendations.\n${HOSTILE}`);
  await page.getByRole("button", { name: "Create project" }).click();

  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { name: "Senior Data Scientist" })).toBeVisible();
  await expect(page.getByTestId("project-status")).toHaveText("Created");

  const job = page.getByTestId("job-project.bootstrap");
  await expect(job.getByTestId("job-status")).toHaveText("succeeded", { timeout: 30_000 });
  await expect(job.getByRole("log")).toContainText("Workspace initialised.");

  // Untrusted job-description text is shown as text and never becomes markup.
  await expect(page.getByText(HOSTILE)).toBeVisible();
  expect(await page.locator("img").count()).toBe(0);
  expect(await page.evaluate(() => "__xss" in window)).toBe(false);

  await page.getByRole("button", { name: "Archive" }).click();
  await expect(page.getByTestId("project-status")).toHaveText("Archived");
  await page.getByRole("button", { name: "Restore from archive" }).click();
  await expect(page.getByTestId("project-status")).toHaveText("Created");

  await page.getByRole("link", { name: "Dashboard" }).click();
  await expect(page.getByRole("link", { name: "Acme BV" })).toBeVisible();

  expect(problems, `browser errors: ${problems.join(" | ")}`).toEqual([]);
});

test("an unknown project shows a clear message", async ({ page }) => {
  await page.goto("/projects/00000000-0000-0000-0000-000000000000");
  await expect(page.getByRole("alert")).toContainText("does not exist");
});
