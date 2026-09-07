import { useState } from "react";
import { UserPlus, KeyRound, ShieldCheck, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuth, ROLE_LABELS, type Role } from "@/contexts/AuthContext";
import {
  useCreateUser,
  useUpdateUser,
  useUpdateUserStatus,
  useUsers,
  type UserItem,
} from "@/hooks/useUsers";

type InputRole = "admin" | "user";

const ROLE_BADGE_CLASS: Record<Role, string> = {
  root: "bg-primary/15 text-primary",
  admin: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
  user: "bg-muted text-muted-foreground",
};

function RoleBadge({ role }: { role: Role }) {
  return <Badge className={ROLE_BADGE_CLASS[role]}>{ROLE_LABELS[role]}</Badge>;
}

/** Role options the current actor may assign (hierarchy-aware). */
function assignableRoles(myRole: Role): { value: InputRole; label: string }[] {
  const options: { value: InputRole; label: string }[] = [{ value: "user", label: "用户" }];
  if (myRole === "root") options.unshift({ value: "admin", label: "管理员" });
  return options;
}

export default function UsersPage() {
  const { user: me, isAdmin } = useAuth();
  const { data: users, isLoading } = useUsers(isAdmin);

  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const updateStatus = useUpdateUserStatus();

  // 新建用户 dialog
  const [createOpen, setCreateOpen] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<InputRole>("user");

  // 重置密码 dialog
  const [resetTarget, setResetTarget] = useState<UserItem | null>(null);
  const [resetPassword, setResetPassword] = useState("");

  // 修改角色 dialog
  const [roleTarget, setRoleTarget] = useState<UserItem | null>(null);
  const [roleValue, setRoleValue] = useState<InputRole>("user");

  // Non-admins never reach this page via the sidebar, but guard against
  // direct URL access — server-side 403 remains the authoritative check
  if (!me || !isAdmin) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        无权访问此页面
      </div>
    );
  }

  const roleOptions = assignableRoles(me.role);

  function handleCreate() {
    if (!newUsername.trim() || !newPassword) return;
    createUser.mutate(
      { username: newUsername.trim(), password: newPassword, role: newRole },
      {
        onSuccess: () => {
          setCreateOpen(false);
          setNewUsername("");
          setNewPassword("");
          setNewRole("user");
        },
      },
    );
  }

  function handleResetPassword() {
    if (!resetTarget || !resetPassword) return;
    updateUser.mutate(
      { id: resetTarget.id, password: resetPassword },
      {
        onSuccess: () => {
          setResetTarget(null);
          setResetPassword("");
        },
      },
    );
  }

  function handleChangeRole() {
    if (!roleTarget) return;
    updateUser.mutate(
      { id: roleTarget.id, role: roleValue },
      {
        onSuccess: () => setRoleTarget(null),
      },
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">用户管理</h1>
          <p className="mt-1 text-sm text-muted-foreground">管理系统账号与角色权限</p>
        </div>
        <Button onClick={() => setCreateOpen(true)} data-testid="create-user-button">
          <UserPlus className="mr-2 h-4 w-4" />
          新建用户
        </Button>
      </div>

      {isLoading ? (
        <div className="flex h-40 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>用户名</TableHead>
                <TableHead>角色</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(users ?? []).map((u) => {
                // The root account is immutable — render without actions
                const isSelf = u.id === me.id;
                const immutable = u.role === "root" || isSelf;
                // Admin may only manage plain users
                const manageable = !immutable && (me.role === "root" || u.role === "user");

                return (
                  <TableRow key={u.id}>
                    <TableCell className="font-medium">
                      {u.username}
                      {isSelf && (
                        <span className="ml-2 text-xs text-muted-foreground">（当前账号）</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <RoleBadge role={u.role} />
                    </TableCell>
                    <TableCell>
                      {u.is_active ? (
                        <Badge className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
                          启用
                        </Badge>
                      ) : (
                        <Badge variant="destructive">停用</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {new Date(u.created_at).toLocaleString("zh-CN")}
                    </TableCell>
                    <TableCell className="text-right">
                      {immutable ? (
                        <span className="text-xs text-muted-foreground">—</span>
                      ) : manageable ? (
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setResetTarget(u);
                              setResetPassword("");
                            }}
                          >
                            <KeyRound className="mr-1 h-3.5 w-3.5" />
                            重置密码
                          </Button>
                          {me.role === "root" && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setRoleTarget(u);
                                setRoleValue(u.role === "admin" ? "admin" : "user");
                              }}
                            >
                              <ShieldCheck className="mr-1 h-3.5 w-3.5" />
                              修改角色
                            </Button>
                          )}
                          <Button
                            variant={u.is_active ? "destructive" : "outline"}
                            size="sm"
                            disabled={updateStatus.isPending}
                            onClick={() =>
                              updateStatus.mutate({ id: u.id, is_active: !u.is_active })
                            }
                          >
                            {u.is_active ? "停用" : "启用"}
                          </Button>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">无权管理</span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {/* 新建用户 */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} title="新建用户">
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="new-username">用户名</Label>
            <Input
              id="new-username"
              value={newUsername}
              onChange={(e) => setNewUsername(e.target.value)}
              placeholder="3-100 个字符"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="new-password">初始密码</Label>
            <Input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="至少 8 位"
            />
          </div>
          <div className="space-y-2">
            <Label>角色</Label>
            <Select value={newRole} onValueChange={(v) => v && setNewRole(v as InputRole)}>
              <SelectTrigger className="w-full">
                <SelectValue>{roleOptions.find((r) => r.value === newRole)?.label}</SelectValue>
              </SelectTrigger>
              <SelectContent align="start" sideOffset={4} alignItemWithTrigger={false}>
                {roleOptions.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button
              onClick={handleCreate}
              disabled={
                createUser.isPending || newUsername.trim().length < 3 || newPassword.length < 8
              }
            >
              {createUser.isPending ? "创建中…" : "创建"}
            </Button>
          </div>
        </div>
      </Dialog>

      {/* 重置密码 */}
      <Dialog
        open={!!resetTarget}
        onClose={() => setResetTarget(null)}
        title={`重置密码 — ${resetTarget?.username ?? ""}`}
      >
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="reset-password">新密码</Label>
            <Input
              id="reset-password"
              type="password"
              value={resetPassword}
              onChange={(e) => setResetPassword(e.target.value)}
              placeholder="至少 8 位"
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setResetTarget(null)}>
              取消
            </Button>
            <Button
              onClick={handleResetPassword}
              disabled={updateUser.isPending || resetPassword.length < 8}
            >
              {updateUser.isPending ? "提交中…" : "确认重置"}
            </Button>
          </div>
        </div>
      </Dialog>

      {/* 修改角色（仅 root） */}
      <Dialog
        open={!!roleTarget}
        onClose={() => setRoleTarget(null)}
        title={`修改角色 — ${roleTarget?.username ?? ""}`}
      >
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>新角色</Label>
            <Select value={roleValue} onValueChange={(v) => v && setRoleValue(v as InputRole)}>
              <SelectTrigger className="w-full">
                <SelectValue>{roleOptions.find((r) => r.value === roleValue)?.label}</SelectValue>
              </SelectTrigger>
              <SelectContent align="start" sideOffset={4} alignItemWithTrigger={false}>
                {roleOptions.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setRoleTarget(null)}>
              取消
            </Button>
            <Button
              onClick={handleChangeRole}
              disabled={updateUser.isPending || (!!roleTarget && roleTarget.role === roleValue)}
            >
              {updateUser.isPending ? "提交中…" : "确认修改"}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
