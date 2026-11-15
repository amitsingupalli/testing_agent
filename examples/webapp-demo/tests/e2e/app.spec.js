import { test, expect } from "@playwright/test";

test("health endpoint responds", async ({ request }) => {
  const res = await request.get("/health");
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body.status).toBe("ok");
});

test("root serves the service banner", async ({ request }) => {
  const res = await request.get("/");
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body.service).toBe("webapp-demo");
});

test("unknown route is a 404", async ({ request }) => {
  const res = await request.get("/definitely-not-a-route");
  expect(res.status()).toBe(404);
});
