import { NavLink, Link, useLocation } from "react-router-dom";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { Upload, History, ChevronDown, Database, BarChart3, Eye, LayoutGrid } from "lucide-react";
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
    ],
  },
  {
    title: "数据分析",
    icon: <BarChart3 className="h-4 w-4" />,
    links: [
      { to: "/views", label: "数据视图", icon: <LayoutGrid className="h-4 w-4" /> },
      { to: "/views/builder", label: "视图创建", icon: <Eye className="h-4 w-4" /> },
    ],
  },
];

export function Sidebar({ onNavClick }: { onNavClick?: () => void }) {
  const location = useLocation();
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});

  const toggleGroup = (title: string) => {
    setOpenGroups((prev) => ({ ...prev, [title]: !prev[title] }));
  };

  const isActiveGroup = (group: NavGroup) =>
    group.links.some((link) => location.pathname.startsWith(link.to));

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
                  end={link.to === "/views"}
                  onClick={onNavClick}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors hover:bg-muted",
                      isActive ? "bg-muted font-medium text-primary" : "text-muted-foreground",
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
    </nav>
  );
}
