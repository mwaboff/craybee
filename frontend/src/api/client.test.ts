import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { server } from "@/test/server";

import { api, ApiError, parseErrorBody } from "./client";

describe("parseErrorBody", () => {
  it("uses a plain string detail as the message", () => {
    const result = parseErrorBody({ detail: "Not found" }, "fallback");
    expect(result).toEqual({ message: "Not found", fieldErrors: {} });
  });

  it("maps a list detail with a field loc into fieldErrors", () => {
    const result = parseErrorBody(
      { detail: [{ loc: ["body", "name"], msg: "String should have at least 1 character" }] },
      "fallback",
    );
    expect(result.fieldErrors).toEqual({ name: "String should have at least 1 character" });
    expect(result.message).toBe("fallback");
  });

  it("collects a list detail with only a body loc into the message", () => {
    const result = parseErrorBody(
      { detail: [{ loc: ["body"], msg: "Value error, base_url is required" }] },
      "fallback",
    );
    expect(result.fieldErrors).toEqual({});
    expect(result.message).toBe("Value error, base_url is required");
  });

  it("falls back for a non-object body", () => {
    const result = parseErrorBody(null, "Request failed");
    expect(result).toEqual({ message: "Request failed", fieldErrors: {} });
  });
});

describe("api()", () => {
  it("throws ApiError with statusText fallback when the body isn't JSON", async () => {
    server.use(
      http.get("/api/v1/thing", () => new HttpResponse("not json", { status: 500, statusText: "Server Error" })),
    );
    await expect(api("/thing")).rejects.toMatchObject({
      status: 500,
      message: "Server Error",
    });
  });

  it("throws ApiError with fieldErrors from a validation body", async () => {
    server.use(
      http.get(
        "/api/v1/thing",
        () =>
          HttpResponse.json(
            { detail: [{ loc: ["body", "name"], msg: "required" }] },
            { status: 422 },
          ),
      ),
    );
    try {
      await api("/thing");
      expect.unreachable();
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).fieldErrors).toEqual({ name: "required" });
    }
  });

  it("returns undefined for a 204 response", async () => {
    server.use(http.get("/api/v1/thing", () => new HttpResponse(null, { status: 204 })));
    await expect(api("/thing")).resolves.toBeUndefined();
  });
});
