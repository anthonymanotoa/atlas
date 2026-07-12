import {
  AlarmClock,
  Banknote,
  Brain,
  Circle,
  FileWarning,
  Flag,
  GraduationCap,
  Handshake,
  type LucideIcon,
  MessageSquare,
  PartyPopper,
  Send,
  Target,
  TriangleAlert,
} from "lucide-react";

// Single source of truth for iconography. Rule: no raw emoji in the UI — add it here.

// Action-card icons, keyed by the action `type` (replaces ACTION_META emoji).
export const ACTION_ICONS: Record<string, LucideIcon> = {
  ask_referral: Handshake,
  send_application: Send,
  reply: MessageSquare,
  follow_up: AlarmClock,
};

export function actionIcon(type: string): LucideIcon {
  return ACTION_ICONS[type] ?? Circle;
}

// Inline-emoji replacements used across the app.
export const MatchIcon = Target; // 🎯 CV↔JD match
export const KnockoutIcon = Flag; // ⚑ knockout filters
export const ReferralIcon = Handshake; // 🤝 referral available
export const SalaryIcon = Banknote; // 💰 salary
export const InsightsIcon = Brain; // 🧠 company learnings
export const CelebrateIcon = PartyPopper; // 🎉 all-clear empty state
export const DowntimeIcon = TriangleAlert; // ⚠️ downtime warning
export const CvTemplateIcon = FileWarning; // ⚠️ master CV is still the template
export const UpskillIcon = GraduationCap; // 🎓 upskilling / gap analysis
