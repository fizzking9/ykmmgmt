/** Referential actions offered for FK constraints (value = DDL spelling). */
export const FK_ACTION_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "无操作（拒绝）" },
  { value: "CASCADE", label: "级联删除" },
  { value: "RESTRICT", label: "限制删除" },
  { value: "SET NULL", label: "置空" },
  { value: "SET DEFAULT", label: "设为默认值" },
];

/** Chinese display name for a stored referential action (null = default). */
export function fkActionLabel(action: string | null | undefined): string {
  if (!action || action === "NO ACTION") return "无操作";
  return FK_ACTION_OPTIONS.find((o) => o.value === action)?.label ?? action;
}
