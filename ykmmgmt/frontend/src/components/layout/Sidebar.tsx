import { NavLink, Link, useLocation, useNavigate } from "react-router-dom";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { useDashboards } from "@/hooks/useDashboards";
import { useAuth, ROLE_LABELS } from "@/contexts/AuthContext";
import {
  Upload,
  ChevronDown,
  Database,
  BarChart3,
  Eye,
  LayoutGrid,
  LayoutDashboard,
  LogOut,
  PieChart,
  Plus,
  Table2,
  UserRound,
  Users,
} from "lucide-react";
import { useState } from "react";

interface NavGroup {
  title: string;
  icon: React.ReactNode;
  links: { to: string; label: string; icon: React.ReactNode; adminOnly?: boolean }[];
}

const groups: NavGroup[] = [
  {
    title: "数据管理",
    icon: <Upload className="h-4 w-4" />,
    links: [
      { to: "/upload", label: "数据导入", icon: <Upload className="h-4 w-4" />, adminOnly: true },
      { to: "/data-browser", label: "数据浏览", icon: <Database className="h-4 w-4" /> },
      { to: "/schema", label: "数据表管理", icon: <Table2 className="h-4 w-4" />, adminOnly: true },
      { to: "/schema/create", label: "新建数据表", icon: <Plus className="h-4 w-4" />, adminOnly: true },
    ],
  },
  {
    title: "数据分析",
    icon: <BarChart3 className="h-4 w-4" />,
    links: [
      { to: "/views", label: "数据视图", icon: <LayoutGrid className="h-4 w-4" /> },
      { to: "/visualizations", label: "可视化", icon: <BarChart3 className="h-4 w-4" /> },
      { to: "/views/builder", label: "视图创建", icon: <Eye className="h-4 w-4" />, adminOnly: true },
      {
        to: "/visualizations/builder",
        label: "可视化构建",
        icon: <PieChart className="h-4 w-4" />,
        adminOnly: true,
      },
    ],
  },
];

export function Sidebar({ onNavClick }: { onNavClick?: () => void }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  const { data: dashboards } = useDashboards();
  const { user, isAdmin, logout } = useAuth();

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

  async function handleLogout() {
    await logout();
    onNavClick?.();
    navigate("/login", { replace: true });
  }

  return (
    <nav className="flex h-full flex-col gap-2 p-4">
      {/* App title */}
      <Link to="/" className="mb-4 block px-2">
        <h1 className="text-lg font-semibold tracking-tight">云客猫管理平台</h1>
      </Link>

      {/* Nav groups */}
      {groups.map((group) => {
        // Hide a whole group when every link is admin-only and the user is L3
        const visibleLinks = group.links.filter((link) => !link.adminOnly || isAdmin);
        if (visibleLinks.length === 0) return null;

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
              {visibleLinks.map((link) => (
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
          {isAdmin && (
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
          )}
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

      {/* 个人设置 — every role; also reachable by clicking the avatar */}
      <NavLink
        to="/profile"
        onClick={onNavClick}
        className={() =>
          cn(
            "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm font-medium transition-colors hover:bg-muted",
            location.pathname.startsWith("/profile")
              ? "bg-muted text-primary"
              : "text-muted-foreground",
          )
        }
      >
        <UserRound className="h-4 w-4" />
        个人设置
      </NavLink>

      {/* 用户管理 — admin and root only */}
      {isAdmin && (
        <NavLink
          to="/users"
          onClick={onNavClick}
          className={() =>
            cn(
              "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm font-medium transition-colors hover:bg-muted",
              location.pathname.startsWith("/users")
                ? "bg-muted text-primary"
                : "text-muted-foreground",
            )
          }
        >
          <Users className="h-4 w-4" />
          用户管理
        </NavLink>
      )}

      {/* Current user + logout — pinned to the bottom. The avatar/name
          block doubles as a shortcut to the profile page. */}
      {user && (
        <div className="mt-auto border-t pt-3">
          <button
            type="button"
            title="个人设置"
            onClick={() => {
              onNavClick?.();
              navigate("/profile");
            }}
            className="mb-2 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted"
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
              {user.username.charAt(0).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{user.username}</p>
              <p className="text-xs text-muted-foreground">{ROLE_LABELS[user.role]}</p>
            </div>
          </button>
          <button
            type="button"
            onClick={handleLogout}
            className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <LogOut className="h-4 w-4" />
            退出登录
          </button>
        </div>
      )}
    </nav>
  );
}
