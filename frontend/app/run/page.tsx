"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  FileSearch, Brain, AlertTriangle, Video, CalendarDays, Mail, ClipboardList,
  CheckCircle2, XCircle, Loader2, Clock, Sparkles
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Step {
  id: string;
  label: string;
  status: "pending" | "running" | "done" | "error";
  message: string;
}

interface RunState {
  status: "idle" | "running" | "done" | "error";
  steps: Step[];
  report: unknown;
}

const STEP_ICONS: Record<string, React.ReactNode> = {
  extract:    <FileSearch className="w-5 h-5" />,
  ai_process: <Brain className="w-5 h-5" />,
  conflicts:  <AlertTriangle className="w-5 h-5" />,
  zoom:       <Video className="w-5 h-5" />,
  calendar:   <CalendarDays className="w-5 h-5" />,
  email:      <Mail className="w-5 h-5" />,
  report:     <ClipboardList className="w-5 h-5" />,
};

function StepRow({ step, index }: { step: Step; index: number }) {
  const isPending = step.status === "pending";
  const isRunning = step.status === "running";
  const isDone    = step.status === "done";
  const isError   = step.status === "error";

  return (
    <div className={cn(
      "flex items-start gap-4 p-4 rounded-lg transition-all duration-300",
      isRunning ? "bg-blue-50 border border-blue-200" : "",
      isDone    ? "bg-green-50 border border-green-100" : "",
      isError   ? "bg-red-50 border border-red-200" : "",
      isPending ? "opacity-50" : "",
    )}>
      {/* Step number / icon */}
      <div className={cn(
        "w-9 h-9 rounded-full flex items-center justify-center shrink-0 mt-0.5",
        isDone    ? "bg-green-500 text-white" : "",
        isRunning ? "bg-blue-500 text-white" : "",
        isError   ? "bg-red-500 text-white" : "",
        isPending ? "bg-slate-200 text-slate-400" : "",
      )}>
        {isRunning ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : isDone ? (
          <CheckCircle2 className="w-5 h-5" />
        ) : isError ? (
          <XCircle className="w-5 h-5" />
        ) : (
          <span className="text-xs font-bold">{index + 1}</span>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={cn(
            "font-medium text-sm",
            isDone    ? "text-green-800" : "",
            isRunning ? "text-blue-800" : "",
            isError   ? "text-red-800"  : "",
            isPending ? "text-slate-500" : "",
          )}>
            {step.label}
          </span>
          <Badge variant={
            isDone    ? "success" :
            isRunning ? "running" :
            isError   ? "destructive" : "pending"
          }>
            {step.status === "running" ? "In progress" :
             step.status === "done"    ? "Done" :
             step.status === "error"   ? "Failed" : "Waiting"}
          </Badge>
        </div>
        {step.message && (
          <p className={cn(
            "text-xs mt-1",
            isDone    ? "text-green-600" : "",
            isRunning ? "text-blue-600"  : "",
            isError   ? "text-red-600"   : "text-slate-500",
          )}>
            {step.message}
          </p>
        )}
      </div>

      {/* Right icon */}
      <div className={cn(
        "shrink-0",
        isDone    ? "text-green-400" : "",
        isRunning ? "text-blue-400"  : "",
        isError   ? "text-red-400"   : "text-slate-300",
      )}>
        {STEP_ICONS[step.id] ?? <Clock className="w-5 h-5" />}
      </div>
    </div>
  );
}

export default function RunPage() {
  const router = useRouter();
  const [state, setState] = useState<RunState | null>(null);
  const [dots, setDots] = useState(".");

  // Animate dots
  useEffect(() => {
    const t = setInterval(() => setDots((d) => (d.length >= 3 ? "." : d + ".")), 500);
    return () => clearInterval(t);
  }, []);

  // Poll status
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/status`, { credentials: "include" });
        if (!res.ok) return;
        const data: RunState = await res.json();
        setState(data);

        if (data.status === "done" || data.status === "error") {
          // Short delay then navigate to report
          setTimeout(() => router.push("/report"), 1500);
          return;
        }
      } catch (_) {
        // backend not ready yet, retry
      }
      timer = setTimeout(poll, 1000);
    };

    poll();
    return () => clearTimeout(timer);
  }, [router]);

  const steps = state?.steps ?? [];
  const doneCount = steps.filter((s) => s.status === "done").length;
  const totalCount = steps.length || 7;
  const progress = Math.round((doneCount / totalCount) * 100);
  const hasError = state?.status === "error";

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-6 py-4 flex items-center gap-3">
          <div className="w-9 h-9 bg-slate-900 rounded-lg flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-semibold text-slate-900 leading-none">AI Classroom Setup Agent</h1>
            <p className="text-xs text-slate-500 mt-0.5">Running automation pipeline</p>
          </div>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-6 py-10">
        {/* Status hero */}
        <div className="text-center mb-8">
          {state?.status === "done" ? (
            <>
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 className="w-8 h-8 text-green-600" />
              </div>
              <h2 className="text-2xl font-bold text-slate-900">All done!</h2>
              <p className="text-slate-500 mt-1">Redirecting to your report…</p>
            </>
          ) : hasError ? (
            <>
              <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <XCircle className="w-8 h-8 text-red-600" />
              </div>
              <h2 className="text-2xl font-bold text-slate-900">Something went wrong</h2>
              <p className="text-slate-500 mt-1">Check the error details below</p>
            </>
          ) : (
            <>
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Loader2 className="w-8 h-8 text-blue-600 animate-spin" />
              </div>
              <h2 className="text-2xl font-bold text-slate-900">
                Setting up your classroom{dots}
              </h2>
              <p className="text-slate-500 mt-1">This usually takes under 30 seconds</p>
            </>
          )}
        </div>

        {/* Progress bar */}
        <div className="mb-6">
          <div className="flex justify-between text-xs text-slate-500 mb-2">
            <span>{doneCount} of {totalCount} steps complete</span>
            <span>{progress}%</span>
          </div>
          <Progress value={progress} className={hasError ? "bg-red-100 [&>div]:bg-red-500" : ""} />
        </div>

        {/* Steps */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Pipeline Progress</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 pt-0">
            {steps.length === 0 ? (
              // Skeleton placeholders while loading
              Array.from({ length: 7 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4 p-4 opacity-30 animate-pulse">
                  <div className="w-9 h-9 rounded-full bg-slate-200" />
                  <div className="h-4 bg-slate-200 rounded w-40" />
                </div>
              ))
            ) : (
              steps.map((step, i) => (
                <StepRow key={step.id} step={step} index={i} />
              ))
            )}
          </CardContent>
        </Card>

        {/* Actions */}
        <div className="mt-6 flex justify-center gap-3">
          {(state?.status === "done" || hasError) && (
            <Button onClick={() => router.push("/report")}>
              View Report
            </Button>
          )}
          <Button variant="outline" onClick={() => router.push("/")}>
            ← Back to Upload
          </Button>
        </div>
      </main>
    </div>
  );
}
