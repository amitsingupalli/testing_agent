const test = require("node:test");
const assert = require("node:assert/strict");

const { Calculator } = require("../../src/calculator");

test("calculator chains operations end to end", () => {
  const result = new Calculator().press(10).plus(5).dividedBy(3).equals();
  assert.equal(result, 5);
});

test("calculator records division errors without crashing", () => {
  const calc = new Calculator().press(1).dividedBy(0);
  assert.equal(calc.lastError, "Cannot divide by zero");
  assert.equal(calc.equals(), 1);
});

test("calculator recovers after an error", () => {
  const result = new Calculator().press(4).dividedBy(0).plus(2).equals();
  assert.equal(result, 6);
  assert.equal(new Calculator().press(4).dividedBy(0).dividedBy(2).lastError, null);
});
