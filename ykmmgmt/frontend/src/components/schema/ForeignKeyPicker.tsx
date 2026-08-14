import { useFkOptions } from "@/hooks/useSchema";

interface ForeignKeyPickerProps {
  /** Current FK reference in the form "table.column"; empty/"" means none. */
  value: string | null | undefined;
  onChange: (value: string) => void;
  /** Prefix for the aria labels, e.g. "第1列" or "新列". */
  ariaPrefix: string;
}

/** Two-level dropdown picker for foreign-key targets (table → column).
 *  Only PK/unique columns are listed, so the choice is always valid. */
export function ForeignKeyPicker({ value, onChange, ariaPrefix }: ForeignKeyPickerProps) {
  const fkQuery = useFkOptions();
  const options = fkQuery.data ?? [];

  const [table = "", col = ""] = (value || "").split(".");
  const selectedTable = options.find((o) => o.table === table);

  const selectCls = "rounded-md border bg-background px-2 py-1 text-xs";

  return (
    <span className="inline-flex items-center gap-1">
      <span className="text-muted-foreground">外键:</span>
      <select
        aria-label={`${ariaPrefix}外键目标表`}
        className={selectCls}
        value={table}
        onChange={(e) => {
          const t = e.target.value;
          if (!t) {
            onChange("");
            return;
          }
          const cols = options.find((o) => o.table === t)?.columns ?? [];
          // Preselect the first eligible column (usually the primary key)
          onChange(cols.length > 0 ? `${t}.${cols[0].name}` : "");
        }}
      >
        <option value="">无外键</option>
        {options.map((o) => (
          <option key={o.table} value={o.table}>
            {o.chinese_name}（{o.table}）
          </option>
        ))}
      </select>
      <select
        aria-label={`${ariaPrefix}外键目标列`}
        className={selectCls}
        disabled={!selectedTable}
        value={col}
        onChange={(e) => onChange(`${table}.${e.target.value}`)}
      >
        {(selectedTable?.columns ?? []).map((c) => (
          <option key={c.name} value={c.name}>
            {c.label}（{c.name}）{c.primary_key ? "・主键" : c.unique ? "・唯一" : ""}
          </option>
        ))}
      </select>
    </span>
  );
}
