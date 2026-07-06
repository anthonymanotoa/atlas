import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Inbox } from "lucide-react";
import { describe, expect, it, vi } from "vitest";
import { EmptyState, ErrorState, LoadingState } from "./states";

describe("states compartidos", () => {
  it("LoadingState pinta N filas skeleton", () => {
    const { container } = render(<LoadingState rows={4} />);
    expect(container.querySelectorAll('[data-slot="skeleton"]')).toHaveLength(4);
  });

  it("ErrorState muestra mensaje accionable y dispara onRetry", async () => {
    const onRetry = vi.fn();
    render(<ErrorState onRetry={onRetry} />);
    expect(screen.getByText("No se pudo cargar")).toBeInTheDocument();
    expect(screen.getByText(/scripts\/run\.sh/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("EmptyState muestra título, descripción y acción", () => {
    render(
      <EmptyState
        icon={Inbox}
        title="Sin vacantes"
        description="Corre una búsqueda."
        action={<button type="button">Buscar</button>}
      />,
    );
    expect(screen.getByText("Sin vacantes")).toBeInTheDocument();
    expect(screen.getByText("Corre una búsqueda.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Buscar" })).toBeInTheDocument();
  });
});
