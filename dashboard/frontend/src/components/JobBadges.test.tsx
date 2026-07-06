import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Job } from "../api";
import { GeoBadge, LegitimacyBadge, RepostBadge } from "./JobBadges";

const base: Job = { id: "j1", title: "DE", company: "Acme", state: "shortlisted" };

describe("GeoBadge", () => {
  it("shows the first scope token for a restricted remote job", () => {
    render(<GeoBadge job={{ ...base, geo_scope: "us", geo_restriction: "Remote — US only" }} />);
    expect(screen.getByText("us")).toBeInTheDocument();
    expect(screen.getByTitle(/Remote — US only/)).toBeInTheDocument();
  });

  it("uses only the first token when the scope lists several regions", () => {
    render(<GeoBadge job={{ ...base, geo_scope: "us,ca,latam" }} />);
    expect(screen.getByText("us")).toBeInTheDocument();
    expect(screen.queryByText("us,ca,latam")).not.toBeInTheDocument();
  });

  it("renders nothing for worldwide / unknown / empty scopes", () => {
    const { container } = render(
      <>
        <GeoBadge job={{ ...base, geo_scope: "worldwide" }} />
        <GeoBadge job={{ ...base, geo_scope: "unknown" }} />
        <GeoBadge job={{ ...base, geo_scope: "" }} />
        <GeoBadge job={base} />
      </>,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe("RepostBadge", () => {
  it("shows a repost chip when repost_count ≥ 1", () => {
    render(<RepostBadge job={{ ...base, repost_count: 2 }} />);
    expect(screen.getByText("repost")).toBeInTheDocument();
    expect(screen.getByTitle(/2/)).toBeInTheDocument();
  });

  it("renders nothing at repost_count 0 or undefined", () => {
    const { container } = render(
      <>
        <RepostBadge job={{ ...base, repost_count: 0 }} />
        <RepostBadge job={base} />
      </>,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe("LegitimacyBadge", () => {
  it("labels each tier in Spanish with the notes in the title", () => {
    render(
      <>
        <LegitimacyBadge job={{ ...base, legitimacy_tier: "high", legitimacy_notes: "reciente" }} />
        <LegitimacyBadge job={{ ...base, legitimacy_tier: "medium", legitimacy_notes: "mixto" }} />
        <LegitimacyBadge job={{ ...base, legitimacy_tier: "low", legitimacy_notes: "92 días" }} />
      </>,
    );
    expect(screen.getByText(/legitimidad: alta/)).toBeInTheDocument();
    expect(screen.getByText(/legitimidad: media/)).toBeInTheDocument();
    expect(screen.getByText(/legitimidad: baja/)).toBeInTheDocument();
    expect(screen.getByTitle("92 días")).toBeInTheDocument();
  });

  it("renders nothing when the tier is unrated (null/undefined)", () => {
    const { container } = render(
      <>
        <LegitimacyBadge job={{ ...base, legitimacy_tier: null }} />
        <LegitimacyBadge job={base} />
      </>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("compact mode shows ONLY the low-tier warning chip", () => {
    const { container: high } = render(
      <LegitimacyBadge job={{ ...base, legitimacy_tier: "high" }} compact />,
    );
    expect(high).toBeEmptyDOMElement();
    const { container: medium } = render(
      <LegitimacyBadge job={{ ...base, legitimacy_tier: "medium" }} compact />,
    );
    expect(medium).toBeEmptyDOMElement();
    render(
      <LegitimacyBadge
        job={{ ...base, legitimacy_tier: "low", legitimacy_notes: "señal" }}
        compact
      />,
    );
    expect(screen.getByText(/legitimidad baja/)).toBeInTheDocument();
    expect(screen.getByTitle("señal")).toBeInTheDocument();
  });
});
