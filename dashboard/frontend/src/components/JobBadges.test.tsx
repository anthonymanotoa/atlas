import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Job } from "../api";
import { GeoBadge, RepostBadge } from "./JobBadges";

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
