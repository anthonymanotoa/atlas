import { PortfolioViewer } from "../components/PortfolioViewer";
import { useProfiles } from "../hooks/useProfiles";

export function PortfolioPage() {
  const profilesQ = useProfiles();
  // key por perfil activo: al cambiar de perfil se refetchea portfolio/peers/research
  return <PortfolioViewer key={profilesQ.data?.active ?? ""} />;
}
