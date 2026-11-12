// Calculator composes the math utilities — exercised by the integration suite.

const { add, divide } = require("./math");

class Calculator {
  constructor() {
    this.value = 0;
    this.lastError = null;
  }

  press(a) {
    this.value = a;
    this.lastError = null;
    return this;
  }

  plus(b) {
    this.value = add(this.value, b);
    return this;
  }

  dividedBy(b) {
    try {
      this.value = divide(this.value, b);
      this.lastError = null;
    } catch (error) {
      this.lastError = error.message;
    }
    return this;
  }

  equals() {
    return this.value;
  }
}

module.exports = { Calculator };
