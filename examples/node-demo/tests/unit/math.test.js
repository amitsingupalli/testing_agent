const test = require("node:test");
const assert = require("node:assert/strict");

const { add, divide, fibonacci } = require("../../src/math");

test("add sums two numbers", () => {
  assert.equal(add(2, 3), 5);
  assert.equal(add(-1, 1), 0);
});

test("divide returns a quotient", () => {
  assert.equal(divide(10, 4), 2.5);
});

test("divide by zero throws", () => {
  assert.throws(() => divide(1, 0), /Cannot divide by zero/);
});

test("fibonacci returns sequence values", () => {
  assert.equal(fibonacci(0), 0);
  assert.equal(fibonacci(1), 1);
  assert.equal(fibonacci(10), 55);
});

test("fibonacci rejects negative input", () => {
  assert.throws(() => fibonacci(-2), /non-negative/);
});
