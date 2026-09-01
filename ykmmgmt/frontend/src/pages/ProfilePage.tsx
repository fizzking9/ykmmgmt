import { useState } from "react";
import { KeyRound, Loader2, UserRound } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ROLE_LABELS, useAuth } from "@/contexts/AuthContext";
import { useUpdateProfile } from "@/hooks/useProfile";

type Panel = "username" | "password";

const PANELS: { value: Panel; label: string; icon: React.ReactNode }[] = [
  { value: "username", label: "修改用户名", icon: <UserRound className="h-4 w-4" /> },
  { value: "password", label: "修改密码", icon: <KeyRound className="h-4 w-4" /> },
];

/** Personal settings — change the current account's username and password.
 *  Reachable from the sidebar nav entry or by clicking the user avatar.
 *  The two forms live in separate panels selected via the panel nav. */
export default function ProfilePage() {
  const { user, setUser } = useAuth();
  const updateProfile = useUpdateProfile();

  const [panel, setPanel] = useState<Panel>("username");

  // 修改用户名 form
  const [newUsername, setNewUsername] = useState("");

  // 修改密码 form
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  if (!user) return null;

  function handleChangeUsername() {
    if (!newUsername.trim()) return;
    updateProfile.mutate(
      { username: newUsername.trim() },
      {
        onSuccess: (profile) => {
          setUser(profile);
          setNewUsername("");
          toast.success("用户名已更新");
        },
        onError: (e: Error) => toast.error(e.message),
      },
    );
  }

  function handleChangePassword() {
    if (!currentPassword || !newPassword) return;
    if (newPassword !== confirmPassword) {
      toast.error("两次输入的新密码不一致");
      return;
    }
    updateProfile.mutate(
      { current_password: currentPassword, new_password: newPassword },
      {
        onSuccess: () => {
          setCurrentPassword("");
          setNewPassword("");
          setConfirmPassword("");
          toast.success("密码已更新");
        },
        onError: (e: Error) => toast.error(e.message),
      },
    );
  }

  const usernameChanged = newUsername.trim() !== "" && newUsername.trim() !== user.username;

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">个人设置</h1>
        <p className="mt-1 text-sm text-muted-foreground">管理当前账号的用户名与密码</p>
      </div>

      {/* Current account summary */}
      <Card>
        <CardContent className="flex items-center gap-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary/10 text-lg font-semibold text-primary">
            {user.username.charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="truncate text-base font-medium">{user.username}</p>
            <p className="text-sm text-muted-foreground">{ROLE_LABELS[user.role]}</p>
          </div>
        </CardContent>
      </Card>

      {/* Panel navigation */}
      <div className="flex gap-1 border-b" role="tablist">
        {PANELS.map((p) => (
          <button
            key={p.value}
            type="button"
            role="tab"
            aria-selected={panel === p.value}
            onClick={() => setPanel(p.value)}
            className={cn(
              "-mb-px flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              panel === p.value
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {p.icon}
            {p.label}
          </button>
        ))}
      </div>

      {/* 修改用户名 panel */}
      {panel === "username" && (
        <Card data-testid="username-panel">
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="current-username">当前用户名</Label>
              <Input id="current-username" value={user.username} disabled />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-username">新用户名</Label>
              <Input
                id="new-username"
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                placeholder="3-100 个字符"
                autoComplete="username"
              />
            </div>
            <div className="flex justify-end">
              <Button onClick={handleChangeUsername} disabled={updateProfile.isPending || !usernameChanged}>
                {updateProfile.isPending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
                保存用户名
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 修改密码 panel */}
      {panel === "password" && (
        <Card data-testid="password-panel">
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="current-password">当前密码</Label>
              <Input
                id="current-password"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-password">新密码</Label>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="至少 8 位"
                autoComplete="new-password"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">确认新密码</Label>
              <Input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
              />
              {confirmPassword.length > 0 && newPassword !== confirmPassword && (
                <p className="text-xs text-red-500">两次输入的新密码不一致</p>
              )}
            </div>
            <div className="flex justify-end">
              <Button
                onClick={handleChangePassword}
                disabled={
                  updateProfile.isPending ||
                  !currentPassword ||
                  newPassword.length < 8 ||
                  newPassword !== confirmPassword
                }
              >
                {updateProfile.isPending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
                保存密码
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
