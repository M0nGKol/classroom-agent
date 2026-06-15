"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CheckCircle2, XCircle, AlertTriangle, CalendarDays, Mail,
  Video, ExternalLink, RotateCcw, Sparkles, FileText
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface EventItem {
  course_name: string;
  start_time: string;
  duration_minutes: number;
  zoom_url: string;
  calendar_link: string;
}

interface Report {
  events_created: EventItem[];
  emails_sent: number;
  conflicts: string[];
  errors: string[];
}

function StatCard({ icon, label, value, color }: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  color: string;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
            {icon}
          </div>
          <div>
            <p className="text-2xl font-bold text-slate-900">{value}</p>
            <p className="text-xs text-slate-500">{label}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-US", {
      weekday: "short", year: "numeric", month: "short",
      day: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function ReportPage() {
  const router = useRouter();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/report`);
        const data = await res.json();
        if (data.error) {
          setError(data.error);
        } else {
          setReport(data);
        }
      } catch {
        setError("Could not connect to the backend server.");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleRunAgain = async () => {
    await fetch(`${API_BASE}/api/reset`, { method: "POST" });
    router.push("/");
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-10 h-10 border-2 border-slate-300 border-t-slate-700 rounded-full animate-spin mx-auto" />
          <p className="text-slate-500 text-sm">Loading report…</p>
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center px-6">
        <Card className="max-w-md w-full">
          <CardContent className="p-8 text-center space-y-4">
            <XCircle className="w-12 h-12 text-red-500 mx-auto" />
            <h2 className="text-lg font-semibold text-slate-900">Report not available</h2>
            <p className="text-sm text-slate-500">{error || "No report data found."}</p>
            <Button onClick={() => router.push("/")} className="mt-2">← Back to Upload</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const hasConflicts = report.conflicts.length > 0;
  const hasErrors = report.errors.length > 0;
  const success = !hasErrors;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-slate-900 rounded-lg flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-semibold text-slate-900 leading-none">AI Classroom Setup Agent</h1>
              <p className="text-xs text-slate-500 mt-0.5">Run report</p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={handleRunAgain} className="gap-1.5">
            <RotateCcw className="w-3.5 h-3.5" />
            Run Again
          </Button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-10 space-y-8">
        {/* Status banner */}
        <div className={`rounded-xl p-6 flex items-center gap-4 ${success ? "bg-green-50 border border-green-200" : "bg-amber-50 border border-amber-200"}`}>
          {success
            ? <CheckCircle2 className="w-10 h-10 text-green-600 shrink-0" />
            : <AlertTriangle className="w-10 h-10 text-amber-600 shrink-0" />}
          <div>
            <h2 className="text-xl font-bold text-slate-900">
              {success ? "Classroom setup complete!" : "Setup completed with some issues"}
            </h2>
            <p className="text-slate-600 text-sm mt-0.5">
              {success
                ? "All Zoom meetings, calendar events, and invitation emails have been handled."
                : `${report.errors.length} error(s) occurred. Review the details below.`}
            </p>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard
            icon={<CalendarDays className="w-5 h-5 text-blue-600" />}
            label="Events Created"
            value={report.events_created.length}
            color="bg-blue-50"
          />
          <StatCard
            icon={<Mail className="w-5 h-5 text-purple-600" />}
            label="Emails Sent"
            value={report.emails_sent}
            color="bg-purple-50"
          />
          <StatCard
            icon={<AlertTriangle className="w-5 h-5 text-amber-600" />}
            label="Conflicts"
            value={report.conflicts.length}
            color="bg-amber-50"
          />
          <StatCard
            icon={<XCircle className="w-5 h-5 text-red-500" />}
            label="Errors"
            value={report.errors.length}
            color="bg-red-50"
          />
        </div>

        {/* Events table */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CalendarDays className="w-5 h-5 text-blue-500" />
              Created Events ({report.events_created.length})
            </CardTitle>
            <CardDescription>Each event has a Zoom meeting and Google Calendar entry.</CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            {report.events_created.length === 0 ? (
              <p className="text-sm text-slate-500 italic py-4 text-center">No events were created.</p>
            ) : (
              <div className="space-y-3">
                {report.events_created.map((ev, i) => (
                  <div key={i} className="border border-slate-200 rounded-lg p-4 hover:bg-slate-50 transition-colors">
                    <div className="flex items-start justify-between gap-2 flex-wrap">
                      <div>
                        <h4 className="font-semibold text-slate-900 text-sm">{ev.course_name}</h4>
                        <p className="text-xs text-slate-500 mt-0.5">
                          {formatDateTime(ev.start_time)} · {ev.duration_minutes} min
                        </p>
                      </div>
                      <Badge variant="success">Created</Badge>
                    </div>
                    <Separator className="my-3" />
                    <div className="flex flex-wrap gap-3">
                      {ev.zoom_url && (
                        <a
                          href={ev.zoom_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-800 font-medium"
                        >
                          <Video className="w-3.5 h-3.5" />
                          Join Zoom
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                      {ev.calendar_link && (
                        <a
                          href={ev.calendar_link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 text-xs text-green-600 hover:text-green-800 font-medium"
                        >
                          <CalendarDays className="w-3.5 h-3.5" />
                          View Calendar
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Conflicts */}
        {hasConflicts && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-500" />
                Schedule Conflicts ({report.conflicts.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0 space-y-2">
              {report.conflicts.map((c, i) => (
                <Alert key={i} variant="warning">
                  <AlertTriangle className="w-4 h-4" />
                  <AlertDescription className="text-xs">{c}</AlertDescription>
                </Alert>
              ))}
            </CardContent>
          </Card>
        )}

        {/* Errors */}
        {hasErrors && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <XCircle className="w-5 h-5 text-red-500" />
                Errors ({report.errors.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0 space-y-2">
              {report.errors.map((e, i) => (
                <Alert key={i} variant="destructive">
                  <XCircle className="w-4 h-4" />
                  <AlertDescription className="text-xs">{e}</AlertDescription>
                </Alert>
              ))}
            </CardContent>
          </Card>
        )}

        {/* Footer actions */}
        <div className="flex flex-col sm:flex-row gap-3 pt-2">
          <Button onClick={handleRunAgain} className="gap-2">
            <RotateCcw className="w-4 h-4" />
            Run Again with New Files
          </Button>
          <Button variant="outline" onClick={() => router.push("/")} className="gap-2">
            <FileText className="w-4 h-4" />
            Back to Upload
          </Button>
        </div>
      </main>
    </div>
  );
}
