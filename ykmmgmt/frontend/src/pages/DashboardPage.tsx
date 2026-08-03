import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function DashboardPage() {
  return (
    <div className="flex items-center justify-center py-20">
      <Card className="w-full max-w-sm text-center">
        <CardHeader>
          <CardTitle className="text-muted-foreground">仪表盘</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">即将上线</p>
        </CardContent>
      </Card>
    </div>
  );
}
