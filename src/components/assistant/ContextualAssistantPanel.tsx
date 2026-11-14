import React, { useEffect, useState, useRef } from "react";
import {
  Sparkles,
  Bot,
  User,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  X,
  Send,
  ClipboardCheck,
  RefreshCw,
  Info,
  ArrowRight,
  FolderLock,
  RotateCcw,
  Layers,
} from "lucide-react";
import { ApiService } from "@/services/api";
import type {
  AssistantActionProposal,
  AssistantExplainResponse,
  AssistantTargetType,
  ManagedFolder,
  QuickPromptItem,
} from "@/types";
import { cn } from "@/lib/utils";

interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text?: string;
  explanation?: AssistantExplainResponse;
  timestamp: string;
  isError?: boolean;
}

interface ContextualAssistantPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigateToReviewChanges?: () => void;
  initialFolderId?: string | null;
  initialTargetType?: AssistantTargetType;
  initialRelativePath?: string | null;
  initialEntityId?: string | null;
  autoPrompt?: string | null;
}

export const ContextualAssistantPanel: React.FC<ContextualAssistantPanelProps> = ({
  isOpen,
  onClose,
  onNavigateToReviewChanges,
  initialFolderId,
  initialTargetType = "general",
  initialRelativePath,
  initialEntityId,
  autoPrompt,
}) => {
  const [folders, setFolders] = useState<ManagedFolder[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<string>("");
  const [targetType, setTargetType] = useState<AssistantTargetType>(initialTargetType);
  const [relativePath, setRelativePath] = useState<string>(initialRelativePath || "");
  const [entityId, setEntityId] = useState<string>(initialEntityId || "");
  const [userQuery, setUserQuery] = useState<string>("");

  const [loading, setLoading] = useState<boolean>(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [quickPrompts, setQuickPrompts] = useState<QuickPromptItem[]>([]);
  const [creatingPlanId, setCreatingPlanId] = useState<string | null>(null);
  const [createdPlans, setCreatedPlans] = useState<Record<string, { planId: string; title: string }>>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const autoPromptHandled = useRef<string | null>(null);

  // Auto-scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // Load registered folders
  useEffect(() => {
    ApiService.listFolders()
      .then((data: ManagedFolder[]) => {
        setFolders(data);
        if (initialFolderId) {
          setSelectedFolderId(initialFolderId);
        } else if (data.length > 0 && !selectedFolderId) {
          setSelectedFolderId(data[0].id);
        }
      })
      .catch((err: unknown) => {
        console.error("Failed to load managed folders:", err);
      });
  }, [initialFolderId]);

  // Initialize messages if empty
  useEffect(() => {
    if (messages.length === 0) {
      setMessages([
        {
          id: "welcome",
          sender: "assistant",
          text: "Halo! Saya AI Assistant FileNest. Saya siap membantu Anda menganalisis berkas, merapikan struktur folder, memeriksa potensi risiko, dan membuat rekomendasi rencana penataan yang aman.",
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    }
  }, [messages.length]);

  // Load quick prompts when target type changes
  useEffect(() => {
    ApiService.getAssistantQuickPrompts(targetType)
      .then((prompts) => setQuickPrompts(prompts))
      .catch(() => setQuickPrompts([]));
  }, [targetType]);

  // Sync initial props
  useEffect(() => {
    if (initialFolderId) setSelectedFolderId(initialFolderId);
    if (initialTargetType) setTargetType(initialTargetType);
    if (initialRelativePath !== undefined) setRelativePath(initialRelativePath || "");
    if (initialEntityId !== undefined) setEntityId(initialEntityId || "");
  }, [initialFolderId, initialTargetType, initialRelativePath, initialEntityId]);

  // Handle autoPrompt if provided
  useEffect(() => {
    if (isOpen && autoPrompt && selectedFolderId && autoPromptHandled.current !== autoPrompt) {
      autoPromptHandled.current = autoPrompt;
      handleSendMessage(autoPrompt);
    }
  }, [isOpen, autoPrompt, selectedFolderId]);

  // Send message to assistant
  const handleSendMessage = async (queryText?: string) => {
    const textToSend = (queryText || userQuery).trim();
    if (!textToSend) return;

    if (!selectedFolderId) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          sender: "assistant",
          text: "Silakan pilih salah satu Managed Folder terlebih dahulu pada bagian atas.",
          isError: true,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
      return;
    }

    const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    // Append user message
    setMessages((prev) => [
      ...prev,
      {
        id: Date.now().toString(),
        sender: "user",
        text: textToSend,
        timestamp: timeStr,
      },
    ]);
    setUserQuery("");
    setLoading(true);

    try {
      const response = await ApiService.explainAssistant({
        managed_folder_id: selectedFolderId,
        target_type: targetType,
        relative_path: relativePath.trim() || undefined,
        entity_id: entityId.trim() || undefined,
        user_query: textToSend,
      });

      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: "assistant",
          text: response.summary,
          explanation: response,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "Gagal memperoleh penjelasan asisten.";
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: "assistant",
          text: errorMsg,
          isError: true,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // Convert proposal to a real draft Change Plan in Review Changes
  const handleCreatePlanFromProposal = async (proposal: AssistantActionProposal) => {
    if (!selectedFolderId) return;

    setCreatingPlanId(proposal.proposal_id);

    try {
      const result = await ApiService.suggestAssistantPlan({
        managed_folder_id: selectedFolderId,
        title: proposal.title,
        plan_type: proposal.plan_type,
        items: proposal.items,
      });

      setCreatedPlans((prev) => ({
        ...prev,
        [proposal.proposal_id]: { planId: result.plan_id, title: result.title },
      }));
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Gagal membuat proposal rencana perubahan.";
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          sender: "assistant",
          text: `Kesalahan saat membuat rencana: ${errMsg}`,
          isError: true,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setCreatingPlanId(null);
    }
  };

  const handleResetChat = () => {
    setMessages([
      {
        id: "welcome-reset",
        sender: "assistant",
        text: "Percakapan telah direset. Silakan ajukan pertanyaan atau pilih salah satu prompt rekomendasi di bawah.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);
  };

  if (!isOpen) return null;

  const activeFolderName =
    folders.find((f) => f.id === selectedFolderId)?.name || "Pilih Folder";

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-xl bg-card border-l border-border shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
      {/* Header */}
      <div className="h-14 border-b border-border px-4 flex items-center justify-between bg-card/70 backdrop-blur-xs shrink-0">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
            <Sparkles size={18} />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h2 className="font-semibold text-sm leading-tight text-foreground truncate">
                AI Assistant
              </h2>
              <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0">
                Hermes & Safe MCP
              </span>
            </div>
            <p className="text-[11px] text-muted-foreground truncate">
              Analisis cerdas & rencana aman via Transaction Manager
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={handleResetChat}
            className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            title="Reset Percakapan"
          >
            <RotateCcw size={15} />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            title="Tutup Panel"
          >
            <X size={17} />
          </button>
        </div>
      </div>

      {/* Context Scope Bar */}
      <div className="px-4 py-2.5 border-b border-border bg-muted/20 space-y-2 shrink-0">
        {/* Managed Folder Selector */}
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground font-medium flex items-center gap-1 w-24 shrink-0">
            <FolderLock size={13} /> Scope Folder:
          </span>
          <select
            value={selectedFolderId}
            onChange={(e) => setSelectedFolderId(e.target.value)}
            className="flex-1 bg-background border border-border rounded-md px-2.5 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary truncate font-medium"
          >
            {folders.length === 0 ? (
              <option value="">Belum ada Managed Folder terdaftar</option>
            ) : (
              folders.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name} ({f.root_path})
                </option>
              ))
            )}
          </select>
        </div>

        {/* Target Entity Selectors */}
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground font-medium flex items-center gap-1 w-24 shrink-0">
            <Info size={13} /> Target:
          </span>
          <div className="flex items-center gap-1 bg-background p-0.5 rounded-md border border-border text-[11px]">
            {(
              [
                { id: "general", label: "Folder Keseluruhan" },
                { id: "file", label: "Berkas" },
                { id: "folder", label: "Subfolder" },
                { id: "plan", label: "Rencana" },
              ] as const
            ).map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setTargetType(item.id)}
                className={cn(
                  "px-2 py-0.5 rounded text-[11px] font-medium transition-colors",
                  targetType === item.id
                    ? "bg-primary text-primary-foreground shadow-2xs font-semibold"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {/* Conditional Path Input */}
        {(targetType === "file" || targetType === "folder") && (
          <div className="flex items-center gap-2 text-xs animate-in fade-in">
            <span className="text-muted-foreground font-medium w-24 shrink-0">
              Path Relatif:
            </span>
            <input
              type="text"
              placeholder={targetType === "file" ? "e.g. Dokumen/laporan.pdf" : "e.g. Dokumen/2026"}
              value={relativePath}
              onChange={(e) => setRelativePath(e.target.value)}
              className="flex-1 bg-background border border-border rounded-md px-2.5 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary font-mono"
            />
          </div>
        )}

        {/* Conditional Plan ID Input */}
        {targetType === "plan" && (
          <div className="flex items-center gap-2 text-xs animate-in fade-in">
            <span className="text-muted-foreground font-medium w-24 shrink-0">
              ID Rencana:
            </span>
            <input
              type="text"
              placeholder="Masukkan ID Rencana Perubahan"
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              className="flex-1 bg-background border border-border rounded-md px-2.5 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary font-mono"
            />
          </div>
        )}
      </div>

      {/* Chat Messages Scroll Container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              "flex gap-3 max-w-[94%] animate-in fade-in",
              msg.sender === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
            )}
          >
            {/* Avatar */}
            <div
              className={cn(
                "w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-white shadow-2xs",
                msg.sender === "user" ? "bg-primary" : "bg-blue-600"
              )}
            >
              {msg.sender === "user" ? <User size={14} /> : <Bot size={14} />}
            </div>

            {/* Bubble */}
            <div
              className={cn(
                "rounded-xl p-3.5 space-y-2.5 shadow-2xs",
                msg.sender === "user"
                  ? "bg-primary text-primary-foreground rounded-tr-xs"
                  : msg.isError
                  ? "bg-destructive/10 border border-destructive/20 text-destructive rounded-tl-xs"
                  : "bg-muted/50 border border-border text-foreground rounded-tl-xs"
              )}
            >
              {/* Message Text */}
              <div className="leading-relaxed whitespace-pre-wrap flex items-start gap-1.5">
                {msg.isError && <AlertTriangle size={14} className="shrink-0 mt-0.5 text-destructive" />}
                <span>{msg.text}</span>
              </div>

              {/* Extended Explanation Details if provided */}
              {msg.explanation && (
                <div className="space-y-3 pt-2 border-t border-border/50 text-foreground">
                  {/* Key Insights List */}
                  {msg.explanation.key_insights.length > 0 && (
                    <div className="p-3 rounded-lg bg-card/90 border border-border space-y-1.5 shadow-2xs">
                      <div className="text-[11px] font-semibold text-muted-foreground flex items-center gap-1.5 uppercase tracking-wider">
                        <Info size={12} className="text-primary" />
                        <span>Wawasan Utama</span>
                      </div>
                      <ul className="space-y-1 pl-1">
                        {msg.explanation.key_insights.map((insight, idx) => (
                          <li key={idx} className="flex items-start gap-1.5 text-xs text-foreground/85">
                            <CheckCircle2 size={13} className="text-primary shrink-0 mt-0.5" />
                            <span>{insight}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Safety Assessment Badge */}
                  {msg.explanation.safety_assessment && (
                    <div className="p-2.5 rounded-lg border border-emerald-500/20 bg-emerald-500/5 text-emerald-800 dark:text-emerald-300 space-y-0.5">
                      <div className="font-semibold text-[11px] flex items-center gap-1.5">
                        <ShieldCheck size={14} className="text-emerald-600" />
                        <span>Jaminan Keamanan Transaksi</span>
                      </div>
                      <p className="text-[11px] text-emerald-700 dark:text-emerald-400 leading-snug">
                        {msg.explanation.safety_assessment}
                      </p>
                    </div>
                  )}

                  {/* Suggested Action Proposals */}
                  {msg.explanation.suggested_actions.length > 0 && (
                    <div className="space-y-2 pt-1">
                      <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                        <ClipboardCheck size={13} className="text-primary" />
                        <span>Usulan Rencana Penataan</span>
                      </div>

                      {msg.explanation.suggested_actions.map((proposal) => {
                        const createdInfo = createdPlans[proposal.proposal_id];
                        const isProcessing = creatingPlanId === proposal.proposal_id;

                        return (
                          <div
                            key={proposal.proposal_id}
                            className="p-3 rounded-xl border border-border bg-card shadow-xs space-y-2"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="font-semibold text-xs text-foreground truncate">
                                {proposal.title}
                              </span>
                              <span className="text-[10px] px-2 py-0.2 rounded font-mono font-medium bg-muted text-muted-foreground uppercase shrink-0">
                                {proposal.plan_type}
                              </span>
                            </div>
                            <p className="text-[11px] text-muted-foreground leading-relaxed">
                              {proposal.description}
                            </p>

                            <div className="pt-1 flex flex-wrap items-center justify-between gap-2 border-t border-border/50">
                              <span className="text-[11px] text-muted-foreground">
                                {proposal.items.length} operasi disiapkan
                              </span>

                              {createdInfo ? (
                                <div className="flex items-center gap-2">
                                  <span className="text-[11px] font-medium text-emerald-600 flex items-center gap-1">
                                    <CheckCircle2 size={13} />
                                    Terkirim ke Review
                                  </span>
                                  {onNavigateToReviewChanges && (
                                    <button
                                      type="button"
                                      onClick={() => {
                                        onNavigateToReviewChanges();
                                        onClose();
                                      }}
                                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-emerald-600 text-white font-medium hover:bg-emerald-700 transition-colors text-[11px] shadow-2xs"
                                    >
                                      <Layers size={11} />
                                      <span>Buka Review Changes</span>
                                      <ArrowRight size={11} />
                                    </button>
                                  )}
                                </div>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => handleCreatePlanFromProposal(proposal)}
                                  disabled={isProcessing}
                                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors text-xs shadow-2xs disabled:opacity-50"
                                >
                                  {isProcessing ? (
                                    <>
                                      <RefreshCw size={12} className="animate-spin" />
                                      <span>Membuat Rencana...</span>
                                    </>
                                  ) : (
                                    <>
                                      <Sparkles size={12} />
                                      <span>Buat Rencana di Review</span>
                                      <ArrowRight size={12} />
                                    </>
                                  )}
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Timestamp */}
              <div
                className={cn(
                  "text-[10px] text-right font-mono opacity-60",
                  msg.sender === "user" ? "text-primary-foreground" : "text-muted-foreground"
                )}
              >
                {msg.timestamp}
              </div>
            </div>
          </div>
        ))}

        {/* Loading Indicator */}
        {loading && (
          <div className="flex items-center gap-2.5 text-muted-foreground p-3 rounded-lg bg-muted/30 border border-border/50 animate-pulse max-w-sm">
            <RefreshCw size={15} className="animate-spin text-primary shrink-0" />
            <span className="text-xs">
              Mengevaluasi konteks terkelola & menghasilkan rekomendasi aman...
            </span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Quick Prompts Carousel / Pills */}
      <div className="px-4 py-2 border-t border-border bg-card/60 shrink-0">
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs no-scrollbar">
          {(quickPrompts.length > 0
            ? quickPrompts
            : [
                {
                  label: "Rapikan Berkas Lepas",
                  prompt: "Tolong rapikan dan kelompokkan berkas lepas di root folder ini ke dalam subfolder kategori.",
                  target_type: "general" as const,
                },
                {
                  label: "Analisis Ruang & Storage",
                  prompt: "Bagaimana ringkasan kapasitas dan pemakaian ruang di folder ini?",
                  target_type: "general" as const,
                },
                {
                  label: "Saran Standarisasi Nama",
                  prompt: "Bagaimana rekomendasi penamaan berkas agar konsisten dan rapi?",
                  target_type: "general" as const,
                },
                {
                  label: "Evaluasi Keamanan",
                  prompt: "Apakah seluruh berkas di folder ini aman untuk dikelola via Transaction Manager?",
                  target_type: "general" as const,
                },
              ]
          ).map((qp, idx) => (
            <button
              key={idx}
              type="button"
              disabled={loading || !selectedFolderId}
              onClick={() => handleSendMessage(qp.prompt)}
              className="text-[11px] px-2.5 py-1 rounded-full bg-secondary hover:bg-secondary/80 text-secondary-foreground font-medium transition-colors flex items-center gap-1 border border-border/60 shrink-0 disabled:opacity-40"
            >
              <Sparkles size={11} className="text-primary shrink-0" />
              <span>{qp.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Query Input Footer */}
      <div className="p-3.5 border-t border-border bg-card shrink-0">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            placeholder={
              selectedFolderId
                ? `Tanyakan analisis atau saran penataan untuk '${activeFolderName}'...`
                : "Pilih folder terkelola terlebih dahulu..."
            }
            value={userQuery}
            onChange={(e) => setUserQuery(e.target.value)}
            disabled={loading || !selectedFolderId}
            className="flex-1 bg-muted/60 border border-border rounded-lg px-3.5 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={loading || !selectedFolderId || !userQuery.trim()}
            className="px-3.5 py-2 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors disabled:opacity-40 flex items-center gap-1.5 text-xs shrink-0 shadow-2xs"
          >
            <Send size={13} />
            <span>Kirim</span>
          </button>
        </form>
      </div>
    </div>
  );
};