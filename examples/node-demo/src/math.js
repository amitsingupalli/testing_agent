// Minimal arithmetic utilities used by the demo test suites.

function add(a, b) {
  return a + b;
}

function divide(a, b) {
  if (b === 0) {
    throw new Error("Cannot divide by zero");
  }
  return a / b;
}

function fibonacci(n) {
  if (!Number.isInteger(n) || n < 0) {
    throw new Error("n must be a non-negative integer");
  }
  let [a, b] = [0, 1];
  for (let i = 0; i < n; i += 1) {
    [a, b] = [b, a + b];
  }
  return a;
}

module.exports = { add, divide, fibonacci };
