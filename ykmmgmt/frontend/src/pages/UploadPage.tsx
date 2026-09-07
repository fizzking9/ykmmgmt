import { useState } from "react";
import { FileUp, Globe, History } from "lucide-react";
import { FileUploadPanel } from "@/components/upload/FileUploadPanel";
import { ScrapeComingSoon } from "@/components/upload/ScrapeComingSoon";
import { ImportHistoryPanel } from "@/components/upload/ImportHistoryPanel";
import { cn } from "@/lib/utils";

type ImportTab = "file" | "scrape" | "history";

const TABS: { key: ImportTab; label: string; icon: React.ReactNode }[] = [
  { key: "file", label: "上传文件", icon: <FileUp className="h-4 w-4" /> },
  { key: "scrape", label: "数据抓取", icon: <Globe className="h-4 w-4" /> },
  { key: "history", label: "导入历史", icon: <History className="h-4 w-4" /> },
];

/** Generic 数据导入 page — a top panel switches the import method:
 *  上传文件 | 数据抓取 | 导入历史. */
export default function UploadPage() {
  const [activeTab, setActiveTab] = useState<ImportTab>("file");

  return (
    <div>
      <h2 className="mb-6 text-2xl font-bold tracking-tight">数据导入</h2>

      {/* Import method panel */}
      <div className="mb-6 inline-flex items-center gap-1 rounded-lg bg-muted p-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              "inline-flex items-center gap-2 rounded-md px-4 py-1.5 text-sm font-medium transition-colors",
              activeTab === tab.key
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "file" && <FileUploadPanel onViewHistory={() => setActiveTab("history")} />}
      {activeTab === "scrape" && <ScrapeComingSoon />}
      {activeTab === "history" && <ImportHistoryPanel />}
    </div>
  );
}
