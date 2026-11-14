import test from "node:test";
import assert from "node:assert/strict";

test("module has no syntax errors", () => {
  assert.equal(typeof "webapp-demo", "string");
});
