import { useState } from "react";
import { Loader2, Plus, RefreshCw, Trash2, Pencil } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
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
import { useAuth } from "@/contexts/AuthContext";
import {
  useActivateEmbeddingModel,
  useDeleteQA,
  useEmbeddingModels,
  useQACategories,
  useQAPairs,
  useRebuildEmbeddings,
  useUpdateQA,
  type QAPair,
} from "@/hooks/useChatAdmin";
import { QAEditDialog } from "@/components/chat/QAEditDialog";

const PAGE_SIZE = 20;
const ALL = "__all__";

function previewAnswer(answer: string): string {
  const flat = answer.replace(/\s+/g, " ").trim();
  return flat.length > 60 ? `${flat.slice(0, 60)}…` : flat;
}

export default function QAManagementPage() {
  const { isAdmin } = useAuth();
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editPair, setEditPair] = useState<QAPair | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<QAPair | null>(null);
  const [rebuildOpen, setRebuildOpen] = useState(false);
  const [modelChoice, setModelChoice] = useState<string | null>(null);
  const [switchOpen, setSwitchOpen] = useState(false);

  const { data: categories = [] } = useQACategories();
  const { data: models } = useEmbeddingModels();
  const { data, isLoading } = useQAPairs({ page, size: PAGE_SIZE, category });
  const deleteQA = useDeleteQA();
  const updateQA = useUpdateQA();
  const rebuild = useRebuildEmbeddings();
  const activateModel = useActivateEmbeddingModel();

  if (!isAdmin) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">无权访问此页面</div>
    );
  }

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // 向量模型选择器：选中项与生效项不同时才允许提交（提交即重建全部向量）
  const chosenModel = modelChoice ?? models?.active_model ?? "";
  const chosenOption = models?.items.find((o) => o.name === chosenModel);
  const targetOption = models?.items.find((o) => o.name === modelChoice);
  const pendingSwitch = Boolean(modelChoice) && modelChoice !== models?.active_model;
  const staleCount = models?.needs_rebuild ?? 0;

  function openCreate() {
    setEditPair(null);
    setDialogOpen(true);
  }
  function openEdit(pair: QAPair) {
    setEditPair(pair);
    setDialogOpen(true);
  }
  function changeCategory(v: string | null) {
    setCategory(!v || v === ALL ? null : v);
    setPage(1);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">问答管理</h1>
          <p className="mt-1 text-sm text-muted-foreground">维护智能问答助手使用的知识库</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => setRebuildOpen(true)}>
            <RefreshCw className="mr-2 h-4 w-4" />
            重建全部向量
          </Button>
          <Button onClick={openCreate} data-testid="create-qa-button">
            <Plus className="mr-2 h-4 w-4" />
            新建问答
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-lg border p-3">
        <div className="flex items-center gap-2">
          <Label className="text-sm text-muted-foreground">向量模型</Label>
          <Select value={chosenModel} onValueChange={(v) => setModelChoice(v)}>
            <SelectTrigger className="w-72">
              <SelectValue>{chosenOption?.label ?? "加载中…"}</SelectValue>
            </SelectTrigger>
            <SelectContent align="start" sideOffset={4} alignItemWithTrigger={false}>
              {(models?.items ?? []).map((o) => (
                <SelectItem key={o.name} value={o.name} title={o.note}>
                  {o.label}（{o.dims} 维）
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {pendingSwitch && (
            <Button size="sm" onClick={() => setSwitchOpen(true)} disabled={activateModel.isPending}>
              切换并重建向量
            </Button>
          )}
        </div>
        <p className="min-w-[240px] flex-1 text-xs text-muted-foreground" title={chosenOption?.note}>
          {chosenOption?.note ?? ""}
          {models && `（当前生效：${models.active_label}；阈值 ${models.threshold.toFixed(2)}）`}
        </p>
        {staleCount > 0 && (
          <Badge variant="destructive" title="这些问答的向量由其他模型生成，无法参与匹配">
            {staleCount} 条待重建
          </Badge>
        )}
      </div>

      <div className="flex items-center gap-2">
        <Label className="text-sm text-muted-foreground">分类筛选</Label>
        <Select value={category ?? ALL} onValueChange={changeCategory}>
          <SelectTrigger className="w-48">
            <SelectValue>{category ?? "全部"}</SelectValue>
          </SelectTrigger>
          <SelectContent align="start" sideOffset={4} alignItemWithTrigger={false}>
            <SelectItem value={ALL}>全部</SelectItem>
            {categories.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <div className="flex h-40 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-lg border py-16 text-center text-sm text-muted-foreground">
          暂无问答，点击右上角「新建问答」开始。
        </div>
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>问题</TableHead>
                <TableHead>答案预览</TableHead>
                <TableHead>分类</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>创建时间</TableHead>
                <TableHead className="text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="max-w-[280px] font-medium">
                    <span className="mr-2 inline-block align-middle">{p.question}</span>
                    {p.variant_count > 0 && (
                      <Badge variant="secondary" title={`包含 ${p.variant_count} 个相似问法`}>
                        +{p.variant_count}
                      </Badge>
                    )}
                    {p.needs_rebuild && (
                      <Badge
                        variant="destructive"
                        className="ml-1"
                        title={`向量由 ${(p.embedding_model ?? "其他模型").split("/").pop()} 生成，需重建`}
                      >
                        待重建
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="max-w-[260px] truncate text-muted-foreground" title={p.answer}>
                    {previewAnswer(p.answer)}
                  </TableCell>
                  <TableCell>{p.category ?? <span className="text-muted-foreground">—</span>}</TableCell>
                  <TableCell>
                    <button
                      type="button"
                      onClick={() => updateQA.mutate({ id: p.id, is_active: !p.is_active })}
                      className="touch-manipulation focus-visible:outline-none"
                      title={p.is_active ? "点击停用" : "点击启用"}
                    >
                      {p.is_active ? (
                        <Badge className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
                          启用
                        </Badge>
                      ) : (
                        <Badge variant="destructive">停用</Badge>
                      )}
                    </button>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(p.created_at).toLocaleString("zh-CN")}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Button variant="outline" size="sm" onClick={() => openEdit(p)}>
                        <Pencil className="mr-1 h-3.5 w-3.5" />
                        编辑
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => setDeleteTarget(p)}
                        disabled={deleteQA.isPending}
                      >
                        <Trash2 className="mr-1 h-3.5 w-3.5" />
                        删除
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>共 {total} 条</span>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((x) => x - 1)}>
              上一页
            </Button>
            <span>
              {page} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((x) => x + 1)}
            >
              下一页
            </Button>
          </div>
        </div>
      )}

      <QAEditDialog
        open={dialogOpen}
        pair={editPair}
        categories={categories}
        onClose={() => setDialogOpen(false)}
      />

      {/* Delete confirmation (soft delete) */}
      <Dialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="停用问答"
      >
        <p className="text-sm text-muted-foreground">
          确认停用「{deleteTarget?.question}」？停用后不再参与匹配，历史记录会保留。
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setDeleteTarget(null)}>
            取消
          </Button>
          <Button
            variant="destructive"
            disabled={deleteQA.isPending}
            onClick={() =>
              deleteTarget &&
              deleteQA.mutate(deleteTarget.id, { onSuccess: () => setDeleteTarget(null) })
            }
          >
            {deleteQA.isPending ? "停用中…" : "确认停用"}
          </Button>
        </div>
      </Dialog>

      {/* Rebuild confirmation */}
      <Dialog open={rebuildOpen} onClose={() => setRebuildOpen(false)} title="重建全部向量">
        <p className="text-sm text-muted-foreground">
          将为所有问答（含停用）按当前向量模型{models && `「${models.active_label}」`}重新计算向量。
          数据量较大时耗时较长。
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setRebuildOpen(false)}>
            取消
          </Button>
          <Button
            disabled={rebuild.isPending}
            onClick={() => rebuild.mutate(undefined, { onSuccess: () => setRebuildOpen(false) })}
          >
            {rebuild.isPending ? "重建中…" : "开始重建"}
          </Button>
        </div>
      </Dialog>

      {/* Encoder switch confirmation — the rebuild happens in the same action */}
      <Dialog open={switchOpen} onClose={() => setSwitchOpen(false)} title="切换向量模型">
        <p className="text-sm text-muted-foreground">
          将从「{models?.active_label}」切换为「{targetOption?.label}」，并为全部问答（含停用）重新计算向量。
          不同模型的向量不可互通，因此切换必须连同重建一起执行；切换后建议重新调优相似度阈值。
          首次使用某模型需服务器上已预置其权重。
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={() => setSwitchOpen(false)}>
            取消
          </Button>
          <Button
            disabled={activateModel.isPending || !modelChoice}
            onClick={() =>
              modelChoice &&
              activateModel.mutate(modelChoice, {
                onSuccess: () => {
                  setSwitchOpen(false);
                  setModelChoice(null);
                },
              })
            }
          >
            {activateModel.isPending ? "切换中…" : "确认切换并重建"}
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
