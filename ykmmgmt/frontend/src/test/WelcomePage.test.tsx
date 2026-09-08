import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

// Hoisted flag so individual tests can flip WebGL availability. vi.mock is
// hoisted above imports, so the mutable state must be created via vi.hoisted.
const mocks = vi.hoisted(() => ({ webglAvailable: true }));

// Stub the WebGL probe — no real context creation in jsdom.
vi.mock("@/lib/particles/webgl", () => ({
  isWebGLAvailable: () => mocks.webglAvailable,
}));

// Mock the Three.js-backed field so the real `three` module graph is never
// loaded and no WebGL renderer / animation loop runs during the test. The real
// ParticleCanvas wrapper still renders (its container carries the test id).
vi.mock("@/lib/particles/pointsField", () => ({
  createPointsField: () =>
    Promise.resolve({
      render: () => {},
      resize: () => {},
      dispose: () => {},
    }),
}));

import WelcomePage from "@/pages/WelcomePage";

function renderWelcome() {
  return render(
    <MemoryRouter initialEntries={["/welcome"]}>
      <Routes>
        <Route path="/welcome" element={<WelcomePage />} />
        <Route path="/login" element={<div>LOGIN_PAGE_STUB</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  mocks.webglAvailable = true;
});

describe("WelcomePage — splash and CTA", () => {
  it("renders the 进入平台 CTA and the particle canvas when WebGL is available", () => {
    renderWelcome();
    expect(screen.getByRole("button", { name: /进入平台/ })).toBeInTheDocument();
    expect(screen.getByTestId("particle-canvas")).toBeInTheDocument();
    expect(screen.queryByTestId("welcome-static-splash")).not.toBeInTheDocument();
  });

  it("navigates to /login when the CTA is clicked", () => {
    renderWelcome();
    fireEvent.click(screen.getByRole("button", { name: /进入平台/ }));
    expect(screen.getByText("LOGIN_PAGE_STUB")).toBeInTheDocument();
  });

  it("renders the static fallback (and still the CTA) when WebGL is unavailable", () => {
    mocks.webglAvailable = false;
    renderWelcome();
    expect(screen.getByTestId("welcome-static-splash")).toBeInTheDocument();
    expect(screen.queryByTestId("particle-canvas")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /进入平台/ })).toBeInTheDocument();
  });

  it("has no headline or tagline text — the glyph carries the brand", () => {
    renderWelcome();
    // The only text-bearing interactive element is the CTA.
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  });
});
