import { describe, expect, it } from "vitest";

import { ApiError } from "@/api/client";
import { toFormErrors } from "@/features/settings/formErrors";

describe("toFormErrors", () => {
  it("maps a 422 field error to fields.name", () => {
    const error = new ApiError(422, "Field required", { name: "Field required" });
    expect(toFormErrors(error)).toEqual({ fields: { name: "Field required" } });
  });

  it("maps a 422 model-validator message to the field it names", () => {
    const error = new ApiError(422, "Value error, base_url is required for openai_compatible servers");
    expect(toFormErrors(error)).toEqual({
      fields: { base_url: "base_url is required for openai_compatible servers" },
    });
  });

  it("maps a 400 patch rule message to the field it names", () => {
    const error = new ApiError(400, "api_key is required for anthropic servers");
    expect(toFormErrors(error)).toEqual({
      fields: { api_key: "api_key is required for anthropic servers" },
    });
  });

  it("puts a 409 conflict message in form", () => {
    const error = new ApiError(409, "An LLM server named 'Claude' already exists");
    expect(toFormErrors(error)).toEqual({
      form: "An LLM server named 'Claude' already exists",
      fields: {},
    });
  });

  it("puts a 502 upstream message in form", () => {
    const error = new ApiError(502, "Local (from env): boom");
    expect(toFormErrors(error)).toEqual({ form: "Local (from env): boom", fields: {} });
  });

  it("falls back to a generic message for a non-ApiError", () => {
    expect(toFormErrors(new Error("network down"))).toEqual({
      form: "Something went wrong. Please try again.",
      fields: {},
    });
  });
});
