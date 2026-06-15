"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Upload, FileText, Users, Calendar, CheckCircle, AlertCircle,
  Loader2, Sparkles, Clock, Zap, Wifi, WifiOff, Play, CalendarClock,
  Save, ToggleLeft, ToggleRight, ChevronLeft, ChevronRight, X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────

type FileKey = "schedule" | "courses" | "students";

interface FileState {
  file: File | null;
  error: string;
}

interface SchedulerStatus {
  enabled: boolean;
  schedule_time: string;
  schedule_dates: string[];
  poll_interval: number;
  timezone: string;
  active_threads: string[];
  pipeline_running: boolean;
  recent_log: string[];
}

// ── Constants ─────────────────────────────────────────────────────────────────

const FILE_CONFIG: Record<FileKey, { label: string; description: string; formats: string; icon: React.ReactNode; color: string }> = {
  schedule: {
    label: "Schedule",
    description: "Course names, dates, times & durations",
    formats: "PDF, DOCX, CSV",
    icon: <Calendar className="w-5 h-5" />,
    color: "text-blue-600",
  },
  courses: {
    label: "Courses",
    description: "Course names and descriptions",
    formats: "PDF, DOCX, CSV",
    icon: <FileText className="w-5 h-5" />,
    color: "text-purple-600",
  },
  students: {
    label: "Students",
    description: "Student names and email addresses",
    formats: "CSV, DOCX",
    icon: <Users className="w-5 h-5" />,
    color: "text-green-600",
  },
};


// ── DropZone component ────────────────────────────────────────────────────────

function DropZone({ fileKey, fileState, onChange }: {
  fileKey: FileKey;
  fileState: FileState;
  onChange: (key: FileKey, file: File | null) => void;
}) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const config = FILE_CONFIG[fileKey];
  const hasFile = !!fileState.file;

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) onChange(fileKey, f);
  }, [fileKey, onChange]);

  return (
    <Card
      className={cn(
        "cursor-pointer transition-all duration-200 border-2",
        dragging ? "border-slate-400 bg-slate-50 scale-[1.01]" : "border-slate-200 hover:border-slate-300",
        hasFile ? "border-green-300 bg-green-50" : ""
      )}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <CardContent className="p-4">
        <div className="flex items-center gap-3">
          <div className={cn("shrink-0", hasFile ? "text-green-600" : config.color)}>
            {hasFile ? <CheckCircle className="w-5 h-5" /> : config.icon}
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-medium text-sm text-slate-800">{config.label}</p>
            {hasFile ? (
              <p className="text-xs text-green-700 truncate">{fileState.file!.name}</p>
            ) : (
              <p className="text-xs text-slate-400">{config.description}</p>
            )}
          </div>
          {hasFile ? (
            <button
              className="text-slate-300 hover:text-red-400 transition-colors text-xs shrink-0"
              onClick={(e) => { e.stopPropagation(); onChange(fileKey, null); }}
            >✕</button>
          ) : (
            <Upload className="w-4 h-4 text-slate-300 shrink-0" />
          )}
        </div>
        {fileState.error && (
          <p className="mt-2 text-xs text-red-500 flex items-center gap-1">
            <AlertCircle className="w-3 h-3" /> {fileState.error}
          </p>
        )}
        <input
          ref={inputRef} type="file" accept=".pdf,.docx,.csv" className="hidden"
          onChange={(e) => onChange(fileKey, e.target.files?.[0] ?? null)}
          onClick={(e) => e.stopPropagation()}
        />
      </CardContent>
    </Card>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function HomePage() {
  const router = useRouter();

  // ── Run Now state ──────────────────────────────────────────────────────────
  const [files, setFiles] = useState<Record<FileKey, FileState>>({
    schedule: { file: null, error: "" },
    courses:  { file: null, error: "" },
    students: { file: null, error: "" },
  });
  const [uploading, setUploading]   = useState(false);
  const [globalError, setGlobalError] = useState("");
  const allReady = (Object.keys(files) as FileKey[]).every((k) => !!files[k].file);

  const handleFileChange = useCallback((key: FileKey, file: File | null) => {
    setFiles((prev) => ({ ...prev, [key]: { file, error: "" } }));
    setGlobalError("");
  }, []);

  const handleRun = async () => {
    if (!allReady) return;
    setUploading(true);
    setGlobalError("");
    try {
      await fetch(`${API_BASE}/api/reset`, { method: "POST" });
      const form = new FormData();
      form.append("schedule", files.schedule.file!);
      form.append("courses",  files.courses.file!);
      form.append("students", files.students.file!);
      const uploadRes = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: form });
      if (!uploadRes.ok) throw new Error("File upload failed");
      const runRes = await fetch(`${API_BASE}/api/run`, { method: "POST" });
      if (!runRes.ok) throw new Error("Failed to start automation");
      router.push("/run");
    } catch (err: unknown) {
      setGlobalError(err instanceof Error ? err.message : "Something went wrong");
      setUploading(false);
    }
  };

  // ── Scheduler state ────────────────────────────────────────────────────────
  const [status, setStatus]         = useState<SchedulerStatus | null>(null);
  const [backendOnline, setBackendOnline] = useState(false);

  // Local editable copies of config
  const [editTime, setEditTime]         = useState("07:00");
  const [editDates, setEditDates]       = useState<string[]>([]);   // YYYY-MM-DD
  const [editEnabled, setEditEnabled]   = useState(true);
  const [editInterval, setEditInterval] = useState(60);
  const [dirty, setDirty]               = useState(false);
  const [saving, setSaving]             = useState(false);
  const [saveMsg, setSaveMsg]           = useState("");

  // Calendar navigation
  const [calView, setCalView] = useState<Date>(() => {
    const d = new Date(); d.setDate(1); return d;
  });

  // Trigger now
  const [triggering, setTriggering] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState("");

  // Poll scheduler status every 5 s
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/scheduler-status`);
        if (res.ok) {
          const data: SchedulerStatus = await res.json();
          setStatus(data);
          setBackendOnline(true);
          // Only sync local state if not currently editing (not dirty)
          setDirty((d) => {
            if (!d) {
              setEditTime(data.schedule_time);
              setEditDates(data.schedule_dates ?? []);
              setEditEnabled(data.enabled);
              setEditInterval(data.poll_interval);
            }
            return d;
          });
        }
      } catch {
        setBackendOnline(false);
      }
    };
    fetchStatus();
    const t = setInterval(fetchStatus, 5000);
    return () => clearInterval(t);
  }, []);

  // Today's date string for disabling past dates
  const todayStr = new Date().toISOString().split("T")[0];

  const toggleDate = (dateStr: string) => {
    if (dateStr < todayStr) return; // no past dates
    setEditDates((prev) =>
      prev.includes(dateStr) ? prev.filter((d) => d !== dateStr) : [...prev, dateStr].sort()
    );
    setDirty(true);
    setSaveMsg("");
  };

  const removeDate = (dateStr: string) => {
    setEditDates((prev) => prev.filter((d) => d !== dateStr));
    setDirty(true);
    setSaveMsg("");
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/scheduler-config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled:        editEnabled,
          schedule_time:  editTime,
          schedule_dates: editDates,
          poll_interval:  editInterval,
        }),
      });
      if (res.ok) {
        setSaveMsg("Schedule saved!");
        setDirty(false);
      } else {
        const err = await res.json();
        setSaveMsg("Error: " + (err.detail ?? "Could not save"));
      }
    } catch {
      setSaveMsg("Could not reach the backend.");
    } finally {
      setSaving(false);
    }
  };

  const handleTriggerNow = async () => {
    setTriggering(true);
    setTriggerMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/trigger-now`, { method: "POST" });
      if (res.ok) {
        setTriggerMsg("Triggered! Redirecting…");
        setTimeout(() => router.push("/run"), 1200);
      } else {
        setTriggerMsg("Failed to trigger.");
      }
    } catch {
      setTriggerMsg("Could not reach the backend.");
    } finally {
      setTriggering(false);
    }
  };

  const threadsOk = (status?.active_threads?.length ?? 0) >= 2;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-slate-50">

      {/* ── Header ── */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-slate-900 rounded-lg flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-semibold text-slate-900 leading-none">AI Classroom Setup Agent</h1>
              <p className="text-xs text-slate-500 mt-0.5">Automate your semester setup in seconds</p>
            </div>
          </div>

          {/* Backend status pill */}
          <span className={cn(
            "hidden sm:flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full",
            backendOnline ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"
          )}>
            {backendOnline
              ? <><Wifi className="w-3.5 h-3.5" /> Backend online</>
              : <><WifiOff className="w-3.5 h-3.5" /> Backend offline</>}
          </span>
        </div>
      </header>

      {/* ── Two-section layout ── */}
      <main className="max-w-5xl mx-auto px-6 py-10">

        {/* Section label row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

          {/* ══════════════════════════════════════════════════════
              SECTION 1 — RUN NOW
          ══════════════════════════════════════════════════════ */}
          <section className="flex flex-col gap-4">

            {/* Section header */}
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shrink-0">
                <Play className="w-4 h-4 text-white" />
              </div>
              <div>
                <h2 className="font-bold text-slate-900 text-lg leading-tight">Run Now</h2>
                <p className="text-xs text-slate-500">Upload files and start the automation immediately</p>
              </div>
            </div>

            {/* Upload dropzones */}
            <Card className="border-slate-200">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-slate-600">Upload your documents</CardTitle>
                <CardDescription className="text-xs">Drag & drop or click each card to browse</CardDescription>
              </CardHeader>
              <CardContent className="pt-0 flex flex-col gap-2">
                {(Object.keys(FILE_CONFIG) as FileKey[]).map((key) => (
                  <DropZone key={key} fileKey={key} fileState={files[key]} onChange={handleFileChange} />
                ))}
              </CardContent>
            </Card>

            {/* Error */}
            {globalError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 text-sm">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {globalError}
              </div>
            )}

            {/* Run button */}
            <Button
              size="lg"
              onClick={handleRun}
              disabled={!allReady || uploading}
              className="w-full gap-2"
            >
              {uploading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Uploading files…</>
              ) : (
                <><Play className="w-4 h-4" /> Run Automation Now</>
              )}
            </Button>
            {!allReady && (
              <p className="text-center text-xs text-slate-400">Upload all 3 files to continue</p>
            )}

            {/* Info chips */}
            <div className="grid grid-cols-2 gap-2 mt-1">
              <div className="rounded-lg bg-white border border-slate-100 p-3 text-xs text-slate-500 space-y-1">
                <p className="font-medium text-slate-600 text-[11px] uppercase tracking-wide">What it does</p>
                <p>✓ Creates Zoom meetings</p>
                <p>✓ Adds Google Calendar events</p>
                <p>✓ Emails every student</p>
                <p>✓ Detects schedule conflicts</p>
              </div>
              <div className="rounded-lg bg-white border border-slate-100 p-3 text-xs text-slate-500 space-y-1">
                <p className="font-medium text-slate-600 text-[11px] uppercase tracking-wide">File formats</p>
                <p>📄 PDF — any layout</p>
                <p>📝 DOCX — Word docs</p>
                <p>📊 CSV — spreadsheets</p>
                <p>🤖 Gemini AI parses all</p>
              </div>
            </div>
          </section>

          {/* ══════════════════════════════════════════════════════
              SECTION 2 — SET SCHEDULE
          ══════════════════════════════════════════════════════ */}
          <section className="flex flex-col gap-4">

            {/* Section header */}
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-violet-600 flex items-center justify-center shrink-0">
                <CalendarClock className="w-4 h-4 text-white" />
              </div>
              <div>
                <h2 className="font-bold text-slate-900 text-lg leading-tight">Set Schedule</h2>
                <p className="text-xs text-slate-500">Let the AI run automatically on a recurring schedule</p>
              </div>
            </div>

            {/* Config card */}
            <Card className={cn(
              "border-2 transition-colors",
              !backendOnline
                ? "border-slate-200"
                : threadsOk
                ? "border-violet-200"
                : "border-amber-200"
            )}>
              <CardHeader className="pb-4">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-medium text-slate-700 flex items-center gap-2">
                    <Clock className="w-4 h-4 text-slate-400" />
                    Auto-Scheduler Config
                  </CardTitle>
                  {backendOnline ? (
                    <span className={cn(
                      "flex items-center gap-1.5 text-xs font-medium",
                      threadsOk ? "text-green-600" : "text-amber-600"
                    )}>
                      {threadsOk
                        ? <><Wifi className="w-3.5 h-3.5" /> Active</>
                        : <><WifiOff className="w-3.5 h-3.5" /> Partial</>}
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400">Offline</span>
                  )}
                </div>
              </CardHeader>

              <CardContent className="space-y-5">

                {/* Enable toggle */}
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-700">Enable auto-schedule</p>
                    <p className="text-xs text-slate-400">Run automatically at the configured time</p>
                  </div>
                  <button
                    onClick={() => { setEditEnabled((v) => !v); setDirty(true); setSaveMsg(""); }}
                    className={cn(
                      "transition-colors",
                      editEnabled ? "text-violet-600" : "text-slate-300"
                    )}
                  >
                    {editEnabled
                      ? <ToggleRight className="w-9 h-9" />
                      : <ToggleLeft  className="w-9 h-9" />}
                  </button>
                </div>

                <div className={cn("space-y-5 transition-opacity", !editEnabled && "opacity-40 pointer-events-none")}>

                  {/* Time picker */}
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1.5">
                      Daily run time
                    </label>
                    <div className="flex items-center gap-3">
                      <input
                        type="time"
                        value={editTime}
                        onChange={(e) => { setEditTime(e.target.value); setDirty(true); setSaveMsg(""); }}
                        className="border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-violet-300 w-36"
                      />
                      <span className="text-xs text-slate-400">{status?.timezone ?? "Asia/Phnom_Penh"}</span>
                    </div>
                  </div>

                  {/* Calendar date picker */}
                  <div>
                    <p className="text-xs font-medium text-slate-600 mb-2">
                      Select execution dates
                      <span className="text-slate-400 font-normal ml-1">(click days to add/remove)</span>
                    </p>

                    {/* Calendar widget */}
                    <div className="border border-slate-200 rounded-xl bg-white overflow-hidden">
                      {/* Month nav */}
                      <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-100">
                        <button
                          onClick={() => setCalView((v) => { const d = new Date(v); d.setMonth(d.getMonth() - 1); return d; })}
                          className="w-7 h-7 rounded-lg hover:bg-slate-100 flex items-center justify-center text-slate-500 transition-colors"
                        >
                          <ChevronLeft className="w-4 h-4" />
                        </button>
                        <span className="text-sm font-semibold text-slate-700">
                          {calView.toLocaleDateString("en-US", { month: "long", year: "numeric" })}
                        </span>
                        <button
                          onClick={() => setCalView((v) => { const d = new Date(v); d.setMonth(d.getMonth() + 1); return d; })}
                          className="w-7 h-7 rounded-lg hover:bg-slate-100 flex items-center justify-center text-slate-500 transition-colors"
                        >
                          <ChevronRight className="w-4 h-4" />
                        </button>
                      </div>

                      {/* Day-of-week header */}
                      <div className="grid grid-cols-7 px-2 pt-2">
                        {["Mo","Tu","We","Th","Fr","Sa","Su"].map((d) => (
                          <div key={d} className="text-center text-[10px] font-semibold text-slate-400 py-1">{d}</div>
                        ))}
                      </div>

                      {/* Date grid */}
                      <div className="grid grid-cols-7 px-2 pb-3 gap-y-0.5">
                        {(() => {
                          const year  = calView.getFullYear();
                          const month = calView.getMonth();
                          const firstDay = new Date(year, month, 1);
                          // Monday-first: getDay() returns 0=Sun; shift so Mon=0
                          const startOffset = (firstDay.getDay() + 6) % 7;
                          const daysInMonth = new Date(year, month + 1, 0).getDate();
                          const cells: React.ReactNode[] = [];

                          // Leading blank cells
                          for (let i = 0; i < startOffset; i++) {
                            cells.push(<div key={`b${i}`} />);
                          }

                          for (let day = 1; day <= daysInMonth; day++) {
                            const dateStr = `${year}-${String(month + 1).padStart(2,"0")}-${String(day).padStart(2,"0")}`;
                            const isPast     = dateStr < todayStr;
                            const isToday    = dateStr === todayStr;
                            const isSelected = editDates.includes(dateStr);

                            cells.push(
                              <button
                                key={day}
                                onClick={() => toggleDate(dateStr)}
                                disabled={isPast}
                                className={cn(
                                  "w-full aspect-square rounded-lg text-xs font-medium transition-all flex items-center justify-center",
                                  isPast     && "text-slate-200 cursor-not-allowed",
                                  !isPast && !isSelected && !isToday && "text-slate-600 hover:bg-violet-50 hover:text-violet-600",
                                  isToday && !isSelected && "text-violet-600 font-bold ring-1 ring-violet-300",
                                  isSelected && "bg-violet-600 text-white shadow-sm hover:bg-violet-700",
                                )}
                              >
                                {day}
                              </button>
                            );
                          }
                          return cells;
                        })()}
                      </div>
                    </div>

                    {/* Selected date chips */}
                    {editDates.length > 0 ? (
                      <div className="mt-2.5 flex flex-wrap gap-1.5">
                        {editDates.map((d) => (
                          <span key={d} className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 font-medium">
                            {new Date(d + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                            <button onClick={() => removeDate(d)} className="ml-0.5 hover:text-violet-900 transition-colors">
                              <X className="w-3 h-3" />
                            </button>
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-400 mt-2 italic">No dates selected — pick dates above.</p>
                    )}
                  </div>

                  {/* File watcher interval */}
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1.5">
                      File-watcher interval (seconds)
                    </label>
                    <div className="flex items-center gap-3">
                      <input
                        type="number"
                        min={10}
                        max={3600}
                        value={editInterval}
                        onChange={(e) => { setEditInterval(Number(e.target.value)); setDirty(true); setSaveMsg(""); }}
                        className="border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-violet-300 w-28"
                      />
                      <p className="text-xs text-slate-400">
                        Auto-triggers when new files appear in uploads/
                      </p>
                    </div>
                  </div>

                </div>

                {/* Save button */}
                <div className="flex items-center gap-3 pt-1 border-t border-slate-100">
                  <Button
                    onClick={handleSave}
                    disabled={saving || !dirty || !backendOnline}
                    className="gap-1.5 bg-violet-600 hover:bg-violet-700"
                    size="sm"
                  >
                    {saving
                      ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Saving…</>
                      : <><Save className="w-3.5 h-3.5" /> Save Schedule</>}
                  </Button>
                  {saveMsg && (
                    <span className={cn(
                      "text-xs font-medium",
                      saveMsg.startsWith("Error") ? "text-red-600" : "text-green-600"
                    )}>
                      {saveMsg}
                    </span>
                  )}
                  {dirty && !saveMsg && (
                    <span className="text-xs text-amber-600">Unsaved changes</span>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Status + trigger card */}
            <Card className="border-slate-200">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-slate-600">Scheduler Status</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">

                {/* Thread badges */}
                <div className="flex gap-2 flex-wrap">
                  {["scheduler-daily", "scheduler-watcher"].map((name) => {
                    const alive = status?.active_threads?.includes(name) ?? false;
                    return (
                      <span key={name} className={cn(
                        "inline-flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-full font-medium",
                        alive ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-400"
                      )}>
                        {alive
                          ? <CheckCircle className="w-3 h-3" />
                          : <AlertCircle className="w-3 h-3" />}
                        {name === "scheduler-daily" ? "Daily trigger" : "File watcher"}
                      </span>
                    );
                  })}
                  {status?.pipeline_running && (
                    <span className="inline-flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-full font-medium bg-blue-100 text-blue-700">
                      <Loader2 className="w-3 h-3 animate-spin" /> Pipeline running
                    </span>
                  )}
                  {!backendOnline && (
                    <span className="inline-flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-full font-medium bg-slate-100 text-slate-400">
                      <WifiOff className="w-3 h-3" /> Backend offline
                    </span>
                  )}
                </div>

                {/* Trigger now */}
                <div className="flex items-center gap-3">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleTriggerNow}
                    disabled={triggering || (status?.pipeline_running ?? false) || !backendOnline}
                    className="gap-1.5 text-xs h-8 border-violet-200 text-violet-700 hover:bg-violet-50"
                  >
                    {triggering
                      ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Triggering…</>
                      : <><Zap className="w-3.5 h-3.5" /> Trigger Now</>}
                  </Button>
                  {triggerMsg && (
                    <p className="text-xs text-slate-600">{triggerMsg}</p>
                  )}
                </div>

                {/* Recent log */}
                {status?.recent_log && status.recent_log.length > 0 && (
                  <div className="mt-1">
                    <p className="text-[10px] font-medium text-slate-400 uppercase tracking-wide mb-1.5">Recent activity</p>
                    <div className="bg-slate-950 rounded-lg p-3 space-y-0.5 max-h-32 overflow-y-auto">
                      {status.recent_log.map((line, i) => (
                        <p key={i} className="text-[10px] text-slate-300 font-mono leading-relaxed">{line}</p>
                      ))}
                    </div>
                  </div>
                )}

                {!backendOnline && (
                  <p className="text-xs text-slate-400 italic">
                    Start the backend to see live status.
                  </p>
                )}
              </CardContent>
            </Card>

          </section>
        </div>
      </main>
    </div>
  );
}
