import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { useCreateQA, useUpdateQA, type QAPair } from "@/hooks/useChatAdmin";
import { MarkdownAnswer } from "./MarkdownAnswer";

/** Create / edit a Q&A pair, incl. its dynamic list of similar phrasings. */
export function QAEditDialog({
  open,
  pair,
  categories,
  onClose,
}: {
  open: boolean;
  pair: QAPair | null;
  categories: string[];
  onClose: () => void;
}) {
  const [question, setQuestion] = useState("");
  const [variants, setVariants] = useState<string[]>([]);
  const [answer, setAnswer] = useState("");
  const [category, setCategory] = useState("");
  const [isActive, setIsActive] = useState(true);

  const createQA = useCreateQA();
  const updateQA = useUpdateQA();
  const saving = createQA.isPending || updateQA.isPending;

  // Reset the form whenever the dialog opens for a (new) target.
  useEffect(() => {
    if (!open) return;
    setQuestion(pair?.question ?? "");
    setVariants(pair ? [...pair.question_variants] : []);
    setAnswer(pair?.answer ?? "");
    setCategory(pair?.category ?? "");
    setIsActive(pair ? pair.is_active : true);
  }, [open, pair]);

  function addVariant() {
    setVariants((v) => [...v, ""]);
  }
  function setVariant(i: number, val: string) {
    setVariants((v) => v.map((x, idx) => (idx === i ? val : x)));
  }
  function removeVariant(i: number) {
    setVariants((v) => v.filter((_, idx) => idx !== i));
  }

  function handleSave() {
    const q = question.trim();
    const a = answer.trim();
    if (!q || !a) {
      toast.error("请填写标准问题和答案");
      return;
    }
    const payload = {
      question: q,
      question_variants: variants.map((s) => s.trim()).filter(Boolean),
      answer: a,
      category: category.trim() || null,
      is_active: isActive,
    };
    if (pair) {
      updateQA.mutate({ id: pair.id, ...payload }, { onSuccess: onClose });
    } else {
      createQA.mutate(payload, { onSuccess: onClose });
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={pair ? "编辑问答" : "新建问答"}
      className="max-w-2xl"
    >
      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="qa-question">标准问题</Label>
          <Textarea
            id="qa-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="用于展示的稳定问题表述"
            rows={2}
          />
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>相似问法</Label>
            <Button type="button" variant="outline" size="sm" onClick={addVariant}>
              <Plus className="mr-1 h-3.5 w-3.5" />
              添加相似问法
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            每个问法都会生成向量，命中任一问法都返回同一答案。
          </p>
          {variants.length === 0 && (
            <p className="rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
              暂无相似问法
            </p>
          )}
          <div className="space-y-2">
            {variants.map((v, i) => (
              <div key={i} className="flex items-center gap-2">
                <Input
                  value={v}
                  onChange={(e) => setVariant(i, e.target.value)}
                  placeholder={`相似问法 ${i + 1}`}
                  aria-label={`相似问法 ${i + 1}`}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => removeVariant(i)}
                  aria-label="删除该问法"
                >
                  <Trash2 className="h-4 w-4 text-muted-foreground" />
                </Button>
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="qa-answer">答案</Label>
            <Textarea
              id="qa-answer"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="支持 Markdown（标题、表格、列表、加粗等）"
              className="min-h-[180px] font-mono text-xs"
            />
            <p className="text-xs text-muted-foreground">支持 Markdown 语法</p>
          </div>
          <div className="space-y-2">
            <Label>预览</Label>
            <div className="max-h-[210px] min-h-[180px] overflow-y-auto rounded-md border bg-muted/30 p-2">
              {answer.trim() ? (
                <MarkdownAnswer content={answer} />
              ) : (
                <p className="text-sm text-muted-foreground">（预览区）</p>
              )}
            </div>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="qa-category">分类</Label>
            <Input
              id="qa-category"
              list="qa-category-options"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="如：数据导入"
            />
            <datalist id="qa-category-options">
              {categories.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
          </div>
          <div className="flex items-end">
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="h-4 w-4 rounded border-input accent-primary"
              />
              启用（在知识库中生效）
            </label>
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t pt-4">
          <Button variant="outline" onClick={onClose} disabled={saving}>
            取消
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "保存中…" : "保存"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
