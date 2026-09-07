import { Link } from "react-router-dom";
import { buttonVariants } from "@/components/ui/button";

/** Catch-all route for unknown paths. */
export default function NotFoundPage() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 p-8 text-center">
      <h1 className="text-4xl font-bold text-muted-foreground">404</h1>
      <p className="text-muted-foreground">您访问的页面不存在或已被移除。</p>
      <Link to="/" className={buttonVariants()}>
        返回首页
      </Link>
    </div>
  );
}
