import { Globe } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

/** Placeholder for the 数据抓取 import method — the scraping feature is
 *  deferred to a post-deployment phase (see specs/roadmap.md Phase 14). */
export function ScrapeComingSoon() {
  return (
    <Card>
      <CardContent className="flex flex-col items-center justify-center p-16 text-center">
        <Globe className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
        <p className="text-lg font-medium">功能开发中</p>
        <p className="mt-1 max-w-md text-sm text-muted-foreground">
          数据抓取功能即将上线，届时可从平台直接抓取数据并导入系统数据库。
        </p>
      </CardContent>
    </Card>
  );
}
