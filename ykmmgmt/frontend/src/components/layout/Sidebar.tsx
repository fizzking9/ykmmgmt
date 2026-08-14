import { NavLink, Link, useLocation } from "react-router-dom";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { useDashboards } from "@/hooks/useDashboards";
import {
  Upload,
  History,
  ChevronDown,
  Database,
  BarChart3,
  Eye,
  LayoutGrid,
  LayoutDashboard,
  PieChart,
  Plus,
  Table2,
} from "lucide-react";
import { useState } from "react";

interface NavGroup {
  title: string;
  icon: React.ReactNode;
  links: { to: string; label: string; icon: React.ReactNode }[];
}

const groups: NavGroup[] = [
  {
    title: "数据管理",
    icon: <Upload className="h-4 w-4" />,
    links: [
      { to: "/upload", label: "上传数据", icon: <Upload className="h-4 w-4" /> },
      { to: "/data-browser", label: "数据浏览", icon: <Database className="h-4 w-4" /> },
      { to: "/imports", label: "导入历史", icon: <History className="h-4 w-4" /> },
      { to: "/schema", label: "数据表管理", icon: <Table2 className="h-4 w-4" /> },
      { to: "/schema/create", label: "新建数据表", icon: <Plus className="h-4 w-4" /> },
    ],
  },
  {
    title: "数据分析",
    icon: <BarChart3 className="h-4 w-4" />,
    links: [
      { to: "/views", label: "数据视图", icon: <LayoutGrid className="h-4 w-4" /> },
      { to: "/visualizations", label: "可视化", icon: <BarChart3 className="h-4 w-4" /> },
      { to: "/views/builder", label: "视图创建", icon: <Eye className="h-4 w-4" /> },
      {
        to: "/visualizations/builder",
        label: "可视化构建",
        icon: <PieChart className="h-4 w-4" />,
      },
    ],
  },
];

export function Sidebar({ onNavClick }: { onNavClick?: () => void }) {
  const location = useLocation();
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  const { data: dashboards } = useDashboards();

  const toggleGroup = (title: string) => {
    setOpenGroups((prev) => ({ ...prev, [title]: !prev[title] }));
  };

  const isActiveGroup = (group: NavGroup) =>
    group.links.some((link) => location.pathname.startsWith(link.to));

  // Explicit active logic: NavLink's default prefix matching would highlight
  // "可视化" (/visualizations) while on the builder (/visualizations/builder/*).
  const isLinkActive = (to: string) => {
    if (to === "/views") return location.pathname === "/views";
    if (to === "/schema") return location.pathname === "/schema";
    if (to === "/visualizations") {
      return (
        location.pathname === "/visualizations" ||
        (location.pathname.startsWith("/visualizations/") &&
          !location.pathname.startsWith("/visualizations/builder"))
      );
    }
    return location.pathname.startsWith(to);
  };

  // Dashboards parent: active on the list page or a display page, but NOT on
  // the builder (/dashboards/builder*) — explicit logic, no prefix matching.
  const isDashboardsParentActive =
    location.pathname === "/dashboards" ||
    (location.pathname.startsWith("/dashboards/") &&
      !location.pathname.startsWith("/dashboards/builder"));

  const dashboardsOpen = openGroups["数据看板"] ?? isDashboardsParentActive;

  return (
    <nav className="flex flex-col gap-2 p-4">
      {/* App title */}
      <Link to="/" className="mb-4 block px-2">
        <h1 className="text-lg font-semibold tracking-tight">云客猫管理平台</h1>
      </Link>

      {/* Nav groups */}
      {groups.map((group) => {
        const isOpen = openGroups[group.title] ?? false;
        const active = isActiveGroup(group);

        return (
          <Collapsible
            key={group.title}
            open={isOpen}
            onOpenChange={() => toggleGroup(group.title)}
          >
            <CollapsibleTrigger
              className={cn(
                "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm font-medium transition-colors hover:bg-muted",
                active && "text-primary",
              )}
            >
              {group.icon}
              <span className="flex-1 text-left">{group.title}</span>
              <ChevronDown
                className={cn(
                  "h-4 w-4 shrink-0 transition-transform duration-200",
                  isOpen && "rotate-180",
                )}
              />
            </CollapsibleTrigger>
            <CollapsibleContent className="space-y-1 pl-7 pt-1">
              {group.links.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  onClick={onNavClick}
                  className={() =>
                    cn(
                      "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-muted",
                      isLinkActive(link.to)
                        ? "bg-muted font-medium text-primary"
                        : "text-muted-foreground",
                    )
                  }
                >
                  {link.icon}
                  {link.label}
                </NavLink>
              ))}
            </CollapsibleContent>
          </Collapsible>
        );
      })}

      {/* Dynamic 仪表盘 section: parent links to the list page; each saved
          dashboard appears as a child nav item (by name). */}
      <Collapsible
        open={dashboardsOpen}
        // Toggle against the EFFECTIVE state — openGroups["数据看板"] may be
        // undefined while the group is open via the active-page fallback
        onOpenChange={() => setOpenGroups((prev) => ({ ...prev, ["数据看板"]: !dashboardsOpen }))}
      >
        <div
          className={cn(
            "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm font-medium transition-colors hover:bg-muted",
            isDashboardsParentActive && "text-primary",
          )}
        >
          {/* Label toggles the group only — no navigation (看板列表 below
              is the entry to the list page) */}
          <div
            onClick={() => {
              onNavClick?.();
              // Toggle on label click like the other groups (the chevron
              // still toggles without navigating)
              setOpenGroups((prev) => ({ ...prev, ["数据看板"]: !dashboardsOpen }));
            }}
            className="flex flex-1 cursor-pointer items-center gap-2 text-left"
          >
            <LayoutDashboard className="h-4 w-4" />
            <span className="flex-1">数据看板</span>
          </div>
          <CollapsibleTrigger className="shrink-0" title="展开/收起">
            <ChevronDown
              className={cn(
                "h-4 w-4 transition-transform duration-200",
                dashboardsOpen && "rotate-180",
              )}
            />
          </CollapsibleTrigger>
        </div>
        <CollapsibleContent className="space-y-1 pl-7 pt-1">
          <NavLink
            to="/dashboards"
            onClick={onNavClick}
            className={() =>
              cn(
                "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-muted",
                location.pathname === "/dashboards"
                  ? "bg-muted font-medium text-primary"
                  : "text-muted-foreground",
              )
            }
          >
            <LayoutGrid className="h-4 w-4" />
            看板列表
          </NavLink>
          <NavLink
            to="/dashboards/builder"
            onClick={onNavClick}
            className={() =>
              cn(
                "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-muted",
                location.pathname.startsWith("/dashboards/builder")
                  ? "bg-muted font-medium text-primary"
                  : "text-muted-foreground",
              )
            }
          >
            <Plus className="h-4 w-4" />
            看板创建
          </NavLink>
          {(dashboards ?? []).map((dash) => (
            <NavLink
              key={dash.id}
              to={`/dashboards/${dash.id}`}
              onClick={onNavClick}
              className={() =>
                cn(
                  "flex items-center gap-2 truncate rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-muted",
                  location.pathname === `/dashboards/${dash.id}`
                    ? "bg-muted font-medium text-primary"
                    : "text-muted-foreground",
                )
              }
              title={dash.name}
            >
              <LayoutDashboard className="h-4 w-4 shrink-0" />
              <span className="truncate">{dash.name}</span>
            </NavLink>
          ))}
        </CollapsibleContent>
      </Collapsible>
    </nav>
  );
}
