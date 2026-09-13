import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FormField } from "./FormField";

describe("FormField", () => {
  it("associates the label with the input", () => {
    render(
      <FormField id="test-field" label="Name">
        {(inputProps) => <input {...inputProps} />}
      </FormField>,
    );
    expect(screen.getByRole("textbox", { name: "Name" })).toBeInTheDocument();
  });

  it("points aria-describedby at the hint and error ids when present, and omits it otherwise", () => {
    const { rerender } = render(
      <FormField id="test-field" label="Name">
        {(inputProps) => <input {...inputProps} />}
      </FormField>,
    );
    expect(screen.getByRole("textbox", { name: "Name" })).not.toHaveAttribute("aria-describedby");

    rerender(
      <FormField id="test-field" label="Name" hint="A hint" error="An error">
        {(inputProps) => <input {...inputProps} />}
      </FormField>,
    );
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveAttribute(
      "aria-describedby",
      "test-field-hint test-field-error",
    );
  });

  it("sets aria-required when required is true", () => {
    render(
      <FormField id="test-field" label="Name" required>
        {(inputProps) => <input {...inputProps} />}
      </FormField>,
    );
    expect(screen.getByRole("textbox", { name: "Name" })).toHaveAttribute("aria-required", "true");
  });

  it("renders the error paragraph with role alert", () => {
    render(
      <FormField id="test-field" label="Name" error="Name is required.">
        {(inputProps) => <input {...inputProps} />}
      </FormField>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Name is required.");
  });
});
